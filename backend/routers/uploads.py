import re
import shutil
import threading
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ScrapeJob
from ..schemas import JobResponse
from ..pdf_worker import run_pdf_job
from ..pdf_parser import detect_version_from_filename

router = APIRouter(prefix="/api")

# Permanent uploads directory (relative to project root where uvicorn runs)
UPLOADS_DIR = Path("uploads")


def _parse_version(v: str) -> tuple:
    return tuple(int(x) for x in v.split("."))


@router.post("/jobs/upload", response_model=JobResponse, status_code=201)
async def upload_pdfs(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Accept one or more FortiGate release-notes PDFs and create a processing job.
    Versions are detected automatically from the PDF filenames
    (e.g. fortios-v7.4.11-release-notes.pdf).
    """
    if not files:
        raise HTTPException(status_code=422, detail="At least one PDF file is required")

    for f in files:
        name = (f.filename or "").lower()
        if not name.endswith(".pdf"):
            raise HTTPException(status_code=422, detail=f"Only PDF files are accepted, got: {f.filename!r}")

    # Save to temp first so we can detect versions before creating the DB row
    tmp_dir = Path(tempfile.mkdtemp(prefix="fgt_pdf_"))
    try:
        tmp_paths: list[Path] = []
        for upload in files:
            safe_name = Path(upload.filename).name  # strip any path traversal
            dest = tmp_dir / safe_name
            content = await upload.read()
            dest.write_bytes(content)
            tmp_paths.append(dest)

        # Derive from/to versions from filenames
        detected = sorted(
            {v for p in tmp_paths if (v := detect_version_from_filename(p.name))},
            key=_parse_version,
        )
        if not detected:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not detect a version number from any filename. "
                    "Rename your PDFs to include the version (e.g. fortios-v7.4.11-release-notes.pdf)."
                ),
            )

        from_version = detected[0]
        to_version = detected[-1]

        # Create the job row — SQLAlchemy assigns UUID immediately via default=_new_uuid
        job = ScrapeJob(
            from_version=from_version,
            to_version=to_version,
            use_selenium=False,
            source="pdf",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Move PDFs to permanent per-job directory
        job_dir = UPLOADS_DIR / job.id
        job_dir.mkdir(parents=True, exist_ok=True)
        pdf_paths: list[str] = []
        for tmp_path in tmp_paths:
            dest = job_dir / tmp_path.name
            shutil.move(str(tmp_path), str(dest))
            pdf_paths.append(str(dest))

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    t = threading.Thread(
        target=run_pdf_job,
        args=(job.id, pdf_paths),
        daemon=True,
        name=f"pdf-{job.id[:8]}",
    )
    t.start()

    return job
