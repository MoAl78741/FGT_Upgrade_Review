# FortiGate Upgrade Review

A web dashboard for reviewing FortiOS release notes across upgrade paths. Scrapes Fortinet's documentation site (or parses uploaded PDFs) and presents the data in a structured, searchable UI.

## Features

- Compare new features, known issues, resolved issues, CLI changes, and default behavior changes across versions
- Upload FortiOS release note PDFs for offline analysis
- Live scrape from Fortinet's documentation site (requests or Selenium mode)
- Full-text searchable content — all PDF sections extracted as markdown, not images
- Special notices and upgrade information rendered with proper formatting

## Requirements

- Python 3.10+
- Node.js 18+

## Setup

### Backend

```bash
pip install -r requirements.txt

# Run from project root (required so fgt_upgrade/ is importable)
uvicorn backend.main:app --reload --port 8000
```

API available at `http://localhost:8000/api`. Interactive docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev        # dev server at http://localhost:5173
npm run build      # build to frontend/dist/ (served by FastAPI in production)
```

Vite proxies `/api/*` → `localhost:8000` in dev mode.

## Usage

### Web UI

1. Open `http://localhost:5173`
2. Either:
   - **Scrape**: enter a from-version and to-version (e.g. `7.2.8` → `7.4.11`)
   - **Upload PDF**: drag and drop one or more FortiOS release note PDFs (filename must contain the version, e.g. `fortios-v7.4.11-release-notes.pdf`)
3. The job runs in the background — progress is shown via live log polling
4. Once complete, the report opens with tabbed sections

### CLI (legacy)

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
| `main.py` | FastAPI app, CORS, router registration, serves built frontend |
| `database.py` | SQLAlchemy engine + `get_db()` dependency; DB at `fgt_upgrade.db` |
| `models.py` | `ScrapeJob` ORM model |
| `schemas.py` | Pydantic request/response schemas |
| `scrape_worker.py` | Background worker for web scrape jobs |
| `pdf_parser.py` | Parses FortiOS PDF release notes into structured data + markdown |
| `pdf_worker.py` | Background worker for PDF upload jobs |
| `routers/jobs.py` | API routes under `/api/jobs` |
| `routers/uploads.py` | PDF upload endpoint |

**API routes:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/jobs` | Create scrape job |
| `GET` | `/api/jobs` | List all jobs |
| `GET` | `/api/jobs/{id}` | Job status + log + full data |
| `DELETE` | `/api/jobs/{id}` | Delete job |
| `POST` | `/api/jobs/upload` | Upload PDF(s) and create job |

**Job lifecycle:** `pending → running → completed | failed`

### Frontend (`frontend/src/`)

| Path | Purpose |
|------|---------|
| `api.ts` | Typed fetch wrappers |
| `types/index.ts` | Shared TypeScript interfaces |
| `pages/Home.tsx` | Job list + new scrape/upload form |
| `pages/Report.tsx` | Full dashboard for a completed job |
| `components/JobCard.tsx` | Job row with live log polling |
| `components/dashboard/` | Tab components |

**Dashboard tabs:**

| Component | Tab | Data |
|-----------|-----|------|
| `Overview.tsx` | Overview | Per-version counts |
| `SimpleTable.tsx` | CLI Changes / Default Behavior / Table Size | `changes_cli`, `changes_default`, `changes_tablesize` |
| `NewFeatures.tsx` | New Features | `new_features` |
| `FeatureDiff.tsx` | Feature Diff | Cross-version comparison |
| `SpecialNotices.tsx` | Special Notices | `special_notices` |
| `KnownIssues.tsx` | Known Issues | `known_issues` |
| `ExtendedRich.tsx` | Upgrade Info / Product Integration / etc. | Rich markdown sections |

### PDF parsing (`backend/pdf_parser.py`)

PDFs are parsed in two stages:

1. **Structure extraction** (pdfplumber) — detects section headings and page boundaries, extracts tables for structured sections (new features, known/resolved issues, CLI changes)
2. **Markdown extraction** (pymupdf4llm) — converts rich prose sections (Upgrade Information, Product Integration & Support, Special Notices) to GFM markdown using PyMuPDF's layout engine

All content is stored as text — selectable, searchable, and renderable without images.

### Data flow

```
POST /api/jobs/upload
  → ScrapeJob row created (status=pending)
  → daemon thread: run_pdf_job()
      → pdfplumber: extract tables + detect section page ranges
      → pymupdf4llm: extract markdown for rich prose sections
      → versions_json / all_data_json / special_notices_json stored in DB
      → status=completed

GET /api/jobs/{id}   ← frontend polls every 2s while active
  → returns log + full data when done
```

## Key conventions

- **Run from project root** — `uvicorn backend.main:app` must be run from the project root so `import fgt_upgrade` resolves.
- **Polling, not WebSockets** — frontend polls `GET /api/jobs/{id}` every 2 seconds while active.
- **One DB file** — `fgt_upgrade.db` is created automatically in the project root on first run.
- **PDF filenames** — must contain the version string (e.g. `v7.4.11`) for auto-detection.
- Do not modify directories prefixed with `v#` (e.g. `v1/`) — these are legacy versions.
