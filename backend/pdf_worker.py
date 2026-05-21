"""
Background worker for PDF-upload jobs.
Mirrors the structure of scrape_worker.py so that the same _store_results
helper can be reused and the job lifecycle is identical.
"""

import json
from datetime import datetime
from pathlib import Path

from .database import SessionLocal
from .models import ScrapeJob

# Permanent uploads directory (must match routers/uploads.py)
UPLOADS_DIR = Path("uploads")


# ── shared log helper (copy of scrape_worker._log) ───────────────────────────

def _log(db, job_id: str, message: str) -> None:
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    if job is not None:
        job.log = (job.log or "") + message + "\n"
        db.commit()


def _store_results(db, job_id: str, versions: list, all_data: dict, special_notices: list) -> None:
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    if job is None:
        return
    job.versions_json = json.dumps(versions)
    job.all_data_json = json.dumps(all_data)
    job.special_notices_json = json.dumps(special_notices)
    job.status = "completed"
    job.completed_at = datetime.utcnow()
    db.commit()

    total_ki = sum(len(all_data.get(v, {}).get("known_issues", [])) for v in versions)
    total_feat = sum(len(all_data.get(v, {}).get("new_features", [])) for v in versions)
    _log(db, job_id, f"Complete — {len(versions)} version(s), {total_feat} features, {total_ki} known issues")


# ── version sort helper ───────────────────────────────────────────────────────

def _ver_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0, 0, 0)


# ── main worker ───────────────────────────────────────────────────────────────

def run_pdf_job(job_id: str, pdf_paths: list[str]) -> None:
    """
    Parse each uploaded PDF, render page images, accumulate version data,
    then store in DB.  PDFs are kept in uploads/{job_id}/ — do not delete.
    """
    db = SessionLocal()
    try:
        job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
        if job is None:
            return
        job.status = "running"
        db.commit()

        from .pdf_parser import PDF_AVAILABLE, parse_pdf

        if not PDF_AVAILABLE:
            raise RuntimeError("pdfplumber not installed — run: pip install pdfplumber")

        out_dir = UPLOADS_DIR / job_id
        out_dir.mkdir(parents=True, exist_ok=True)

        total = len(pdf_paths)
        _log(db, job_id, f"Parsing {total} PDF file(s)...")

        all_data: dict = {}
        all_notices: list = []
        detected_versions: list[str] = []

        for i, pdf_path in enumerate(pdf_paths, 1):
            filename = Path(pdf_path).name
            _log(db, job_id, f"  [{i}/{total}] {filename}")

            try:
                version, version_data, notices, section_pages, notice_pages = parse_pdf(pdf_path)
            except Exception as exc:
                _log(db, job_id, f"    ERROR: {exc}")
                continue

            if not version:
                _log(db, job_id, f"    WARNING: could not detect version — skipping")
                continue

            _log(db, job_id, f"    → v{version}: "
                             f"{len(version_data.get('new_features', []))} features, "
                             f"{len(version_data.get('known_issues', []))} known issues, "
                             f"{len(version_data.get('resolved-issues', []))} resolved issues")

            detected_versions.append(version)
            all_data[version] = version_data
            all_notices.extend(notices)

        if not detected_versions:
            raise RuntimeError(
                "No versions could be detected from the uploaded PDFs. "
                "Ensure filenames contain the version number (e.g. fortios-v7.4.11-release-notes.pdf)."
            )

        # Sort versions in ascending order
        detected_versions.sort(key=_ver_tuple)

        # Deduplicate special notices by title
        _log(db, job_id, f"Finalising {len(detected_versions)} version(s)...")
        seen: set[str] = set()
        unique_notices: list[dict] = []
        for n in all_notices:
            key = n.get("title", "")
            if key not in seen:
                seen.add(key)
                unique_notices.append(n)

        _store_results(db, job_id, detected_versions, all_data, unique_notices)

    except Exception as exc:
        try:
            db.rollback()
            job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                job.completed_at = datetime.utcnow()
                db.commit()
            _log(db, job_id, f"ERROR: {exc}")
        except Exception:
            pass
    finally:
        db.close()
