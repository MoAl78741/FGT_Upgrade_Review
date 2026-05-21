"""
Background scraping worker.
Runs in a daemon thread; updates the ScrapeJob row in SQLite as it progresses.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure the project root is importable so fgt_upgrade can be found
sys.path.insert(0, str(Path(__file__).parent.parent))

from .database import SessionLocal
from .models import ScrapeJob


def _load_version_cache(db, versions: list) -> dict:
    """
    Query all completed jobs and return per-version data for any version
    in *versions* that has already been scraped.

    Returns {version_str: version_data_dict}.
    """
    cached: dict = {}
    try:
        completed = (
            db.query(ScrapeJob)
            .filter(ScrapeJob.status == "completed", ScrapeJob.all_data_json.isnot(None))
            .all()
        )
        want = set(versions)
        for job in completed:
            try:
                all_data = json.loads(job.all_data_json)
            except Exception:
                continue
            for ver in want:
                if ver in all_data and ver not in cached:
                    cached[ver] = all_data[ver]
            if cached.keys() >= want:
                break  # found everything we need
    except Exception:
        pass
    return cached


def _load_special_notices_cache(db, to_version: str) -> list | None:
    """Return special notices from any completed job that targeted the same version, or None."""
    try:
        job = (
            db.query(ScrapeJob)
            .filter(
                ScrapeJob.status == "completed",
                ScrapeJob.to_version == to_version,
                ScrapeJob.special_notices_json.isnot(None),
            )
            .first()
        )
        if job:
            return json.loads(job.special_notices_json)
    except Exception:
        pass
    return None


def _log(db, job_id: str, message: str) -> None:
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    if job is not None:
        job.log = (job.log or "") + message + "\n"
        db.commit()


def run_scrape(
    job_id: str,
    from_version: str,
    to_version: str,
    use_selenium: bool,
    grid_url: str | None = None,
    force_rescrape: bool = False,
) -> None:
    db = SessionLocal()
    try:
        job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
        if job is None:
            return
        job.status = "running"
        db.commit()

        _log(db, job_id, f"Starting scrape: {from_version} → {to_version}"
             + (" (cache bypassed)" if force_rescrape else ""))

        if use_selenium:
            _run_selenium(db, job_id, from_version, to_version, grid_url=grid_url,
                          force_rescrape=force_rescrape)
        else:
            _run_requests(db, job_id, from_version, to_version, force_rescrape=force_rescrape)

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


def _run_requests(db, job_id: str, from_version: str, to_version: str,
                  force_rescrape: bool = False) -> None:
    from fgt_upgrade.scraper_requests import (
        REQUESTS_AVAILABLE,
        discover_versions,
        make_session,
        scrape_all,
        scrape_target_extras,
    )

    if not REQUESTS_AVAILABLE:
        raise RuntimeError("requests / beautifulsoup4 not installed")

    _log(db, job_id, "Mode: requests (no browser)")
    session = make_session()

    _log(db, job_id, "Step 1/4 — Discovering versions...")
    versions = discover_versions(session, from_version, to_version)
    if not versions:
        raise RuntimeError("No versions found in range — check version numbers and connectivity")
    _log(db, job_id, f"  Found {len(versions)} versions: {', '.join(versions)}")

    # Check which versions are already cached in the DB (skipped when force_rescrape)
    cached_versions = {} if force_rescrape else _load_version_cache(db, versions)
    to_scrape = [v for v in versions if v not in cached_versions]
    if cached_versions:
        _log(db, job_id, f"  Cache hit for {len(cached_versions)} version(s): {', '.join(sorted(cached_versions))}")
    if to_scrape:
        _log(db, job_id, f"  Will scrape {len(to_scrape)} new version(s): {', '.join(to_scrape)}")

    _log(db, job_id, f"Step 2/4 — Scraping {len(to_scrape)} version(s) (parallel)...")
    if to_scrape:
        all_data = scrape_all(session, to_scrape, to_version)
        _log(db, job_id, "  Done scraping version data")
    else:
        all_data = {}
        _log(db, job_id, "  All versions served from cache — skipped")

    # Merge: cached data fills in any version not freshly scraped
    all_data = {**cached_versions, **all_data}

    _log(db, job_id, "Step 3/4 — Scraping full document (extended sections)...")
    from fgt_upgrade.scraper_full import scrape_all_extended
    if to_scrape:
        all_data = scrape_all_extended(session, to_scrape, all_data)
        _log(db, job_id, "  Done scraping extended sections")
    else:
        _log(db, job_id, "  Extended sections served from cache — skipped")

    _log(db, job_id, "Step 4/4 — Scraping special notices...")
    cached_notices = None if force_rescrape else _load_special_notices_cache(db, to_version)
    if cached_notices is not None:
        special_notices = cached_notices
        _log(db, job_id, f"  Special notices served from cache ({len(special_notices)} item(s))")
    else:
        special_notices = scrape_target_extras(session, to_version)
        _log(db, job_id, f"  Found {len(special_notices)} special notice(s)")

    _store_results(db, job_id, versions, all_data, special_notices)


def _run_selenium(
    db, job_id: str, from_version: str, to_version: str, grid_url: str | None = None,
    force_rescrape: bool = False,
) -> None:
    from fgt_upgrade.scraper_selenium import (
        SELENIUM_AVAILABLE,
        discover_versions,
        scrape_all,
        scrape_target_extras,
        setup_driver,
    )

    if not SELENIUM_AVAILABLE:
        raise RuntimeError("selenium package not installed — run: pip install selenium")

    _log(db, job_id, "Mode: Selenium (Chrome)")
    _log(db, job_id, "Step 1/4 — Setting up Chrome driver...")
    driver = setup_driver(grid_url=grid_url) if grid_url else setup_driver()

    try:
        _log(db, job_id, "Step 2/4 — Discovering versions...")
        versions = discover_versions(driver, from_version, to_version)
        if not versions:
            raise RuntimeError("No versions found in range — check version numbers and connectivity")
        _log(db, job_id, f"  Found {len(versions)} versions: {', '.join(versions)}")

        # Check which versions are already cached in the DB (skipped when force_rescrape)
        cached_versions = {} if force_rescrape else _load_version_cache(db, versions)
        to_scrape = [v for v in versions if v not in cached_versions]
        if cached_versions:
            _log(db, job_id, f"  Cache hit for {len(cached_versions)} version(s): {', '.join(sorted(cached_versions))}")
        if to_scrape:
            _log(db, job_id, f"  Will scrape {len(to_scrape)} new version(s): {', '.join(to_scrape)}")

        _log(db, job_id, f"Step 3/4 — Scraping {len(to_scrape)} version(s)...")
        if to_scrape:
            all_data = scrape_all(driver, to_scrape, to_version)
        else:
            all_data = {}
            _log(db, job_id, "  All versions served from cache — skipped")

        all_data = {**cached_versions, **all_data}

        _log(db, job_id, "Scraping special notices...")
        cached_notices = None if force_rescrape else _load_special_notices_cache(db, to_version)
        if cached_notices is not None:
            special_notices = cached_notices
            _log(db, job_id, f"  Special notices served from cache ({len(special_notices)} item(s))")
        else:
            special_notices = scrape_target_extras(driver, to_version)
            _log(db, job_id, f"  Found {len(special_notices)} special notice(s)")
    finally:
        driver.quit()
        _log(db, job_id, "Browser closed")

    import requests as _req_lib
    from fgt_upgrade.scraper_full import scrape_all_extended
    _session = _req_lib.Session()
    _log(db, job_id, "Step 4/4 — Scraping full document (extended sections)...")
    if to_scrape:
        all_data = scrape_all_extended(_session, to_scrape, all_data)
        _log(db, job_id, "  Done scraping extended sections")
    else:
        _log(db, job_id, "  Extended sections served from cache — skipped")

    _store_results(db, job_id, versions, all_data, special_notices)


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
    _log(db, job_id, f"Complete — {len(versions)} versions, {total_feat} features, {total_ki} known issues")
