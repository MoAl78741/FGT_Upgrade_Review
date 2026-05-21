# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the web application (v2)

### Backend (FastAPI + SQLite)

```bash
pip install -r requirements.txt

# Run from project root — must be project root so fgt_upgrade/ is importable
uvicorn backend.main:app --reload --port 8000
```

API available at `http://localhost:8000/api`. Interactive docs at `http://localhost:8000/docs`.

### Frontend (React + Vite + Tailwind)

```bash
cd frontend
npm install
npm run dev        # dev server at http://localhost:5173 (proxies /api → :8000)
npm run build      # build to frontend/dist/ (served by FastAPI in production)
```

### CLI (legacy — still works)

```bash
python fortigate_dashboard.py 7.2.8 7.4.11
python fortigate_dashboard.py 7.2.8 7.4.11 --save-data ./data/
python fortigate_dashboard.py 7.2.8 7.4.11 --load-data ./data/scraped_7.2.8_to_7.4.11.json
python fortigate_dashboard.py 7.2.8 7.4.11 --selenium
```

## Architecture

### Backend (`backend/`)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, CORS, router registration, serves built frontend from `frontend/dist/` |
| `database.py` | SQLAlchemy engine + `get_db()` dependency; DB file at `fgt_upgrade.db` in project root |
| `models.py` | `ScrapeJob` ORM model — one row per scrape; stores status, log, and result JSON blobs |
| `schemas.py` | Pydantic `CreateJobRequest`, `JobResponse`, `JobDetailResponse` |
| `scrape_worker.py` | `run_scrape()` — runs in a daemon thread; calls existing `fgt_upgrade` scrapers and writes progress to the `log` column |
| `routers/jobs.py` | All API routes under `/api/jobs` |

**API routes:**
- `POST /api/jobs` — create job, starts background daemon thread
- `GET /api/jobs` — list all jobs (newest first)
- `GET /api/jobs/{id}` — job status + log + full data (when completed)
- `DELETE /api/jobs/{id}` — delete job

**Job lifecycle:** `pending → running → completed | failed`

Scraping runs in a `threading.Thread(daemon=True)` started by FastAPI's `BackgroundTasks`. The worker appends progress lines to `ScrapeJob.log` in SQLite so the frontend can poll for live output. On completion, `versions_json`, `all_data_json`, and `special_notices_json` are populated.

### Frontend (`frontend/src/`)

| Path | Purpose |
|------|---------|
| `api.ts` | Typed fetch wrappers for all backend endpoints |
| `types/index.ts` | Shared TypeScript interfaces (`Job`, `JobDetail`, `VersionData`, etc.) |
| `pages/Home.tsx` | Job list + new scrape form |
| `pages/Report.tsx` | Full dashboard for a completed job; polls backend while running |
| `components/JobCard.tsx` | Single job row; auto-polls while active, shows live log |
| `components/NewScrapeForm.tsx` | Version input form; calls `POST /api/jobs` |
| `components/dashboard/` | All tab components (see below) |

**Dashboard tabs:**

| Component | Tab | Data key |
|-----------|-----|----------|
| `Overview.tsx` | Overview | all sections, per-version counts |
| `SimpleTable.tsx` | CLI Changes / Default Behavior / Table Size | `changes_cli`, `changes_default`, `changes_tablesize` |
| `NewFeatures.tsx` | New Features | `new_features` |
| `FeatureDiff.tsx` | Feature Diff | compares any two versions |
| `SpecialNotices.tsx` | Special Notices | `special_notices` |
| `KnownIssues.tsx` | Known Issues | `known_issues` |

Vite dev server proxies `/api/*` → `localhost:8000` so no CORS issues in development.

### Scraping package (`fgt_upgrade/`)

Unchanged from v1. `backend/scrape_worker.py` imports directly:
- `fgt_upgrade.scraper_requests` — default mode (requests + BeautifulSoup + ThreadPoolExecutor)
- `fgt_upgrade.scraper_selenium` — optional Selenium mode

`backend/main.py` adds the project root to `sys.path` so the package is always findable regardless of working directory.

### Data flow

```
POST /api/jobs
  → ScrapeJob row created (status=pending)
  → daemon thread starts run_scrape()
      → status=running; log updated incrementally
      → fgt_upgrade scrapers run (same code as CLI)
      → versions_json / all_data_json / special_notices_json stored
      → status=completed (or failed)

GET /api/jobs/{id}   ← frontend polls every 2s while active
  → returns log (for live progress) + full data (when done)
```

## Key conventions

- **Run from project root** — `uvicorn backend.main:app` must be run from the project root so that `import fgt_upgrade` resolves correctly.
- **Polling, not WebSockets** — frontend polls `GET /api/jobs/{id}` every 2 seconds while a job is active. This is intentional simplicity; do not add WebSocket complexity.
- **One DB file** — `fgt_upgrade.db` is created automatically in the project root on first run.
- The scraping JS in `SCRAPING_HELPERS_JS` uses JavaScript regex syntax inside a Python string — backslashes need doubling. Prefer `includes()` over regex where possible.

Dont touch any folder in this directory that start with v#. Example: v1.
