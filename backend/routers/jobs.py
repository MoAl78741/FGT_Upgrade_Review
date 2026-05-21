import json
import re
import shutil
import threading
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ScrapeJob
from ..schemas import CreateJobRequest, JobDetailResponse, JobResponse
from ..scrape_worker import run_scrape

router = APIRouter(prefix="/api")

_VER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _parse_version(v: str) -> tuple:
    return tuple(int(x) for x in v.split("."))


def _start_scrape_thread(
    job_id: str, from_version: str, to_version: str, use_selenium: bool, grid_url: str | None,
    force_rescrape: bool = False,
) -> None:
    t = threading.Thread(
        target=run_scrape,
        args=(job_id, from_version, to_version, use_selenium, grid_url, force_rescrape),
        daemon=True,
        name=f"scrape-{job_id[:8]}",
    )
    t.start()


@router.post("/jobs", response_model=JobResponse, status_code=201)
def create_job(
    req: CreateJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Validate versions
    if not _VER_RE.match(req.from_version):
        raise HTTPException(status_code=422, detail=f"Invalid from_version: '{req.from_version}'")
    if not _VER_RE.match(req.to_version):
        raise HTTPException(status_code=422, detail=f"Invalid to_version: '{req.to_version}'")
    if _parse_version(req.from_version) >= _parse_version(req.to_version):
        raise HTTPException(status_code=422, detail="from_version must be strictly less than to_version")

    # Create new job and start scraping in background
    job = ScrapeJob(
        from_version=req.from_version,
        to_version=req.to_version,
        use_selenium=req.use_selenium,
        grid_url=req.grid_url,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        _start_scrape_thread,
        job.id,
        req.from_version,
        req.to_version,
        req.use_selenium,
        req.grid_url,
        req.force_rescrape,
    )
    return job


@router.get("/jobs", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db)):
    return db.query(ScrapeJob).order_by(ScrapeJob.created_at.desc()).all()


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    detail = JobDetailResponse.model_validate(job)
    if job.versions_json:
        detail.versions = json.loads(job.versions_json)
    if job.all_data_json:
        detail.all_data = json.loads(job.all_data_json)
    if job.special_notices_json:
        detail.special_notices = json.loads(job.special_notices_json)
    return detail


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    # Clean up uploaded PDFs and rendered page images for PDF jobs
    shutil.rmtree(Path("uploads") / job_id, ignore_errors=True)
