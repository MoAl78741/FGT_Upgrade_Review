import sys
from pathlib import Path

# Ensure the project root (parent of backend/) is on sys.path so fgt_upgrade is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import engine, run_migrations
from . import models
from .routers.jobs import router as jobs_router
from .routers.uploads import router as uploads_router

# Run migrations first (adds missing columns to existing DB without wiping data),
# then create any brand-new tables.
run_migrations()
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FortiGate Upgrade Dashboard API",
    version="2.0.0",
    description="Scrapes Fortinet release notes and serves an interactive upgrade dashboard",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(uploads_router)

# Serve built React frontend if present
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    # Serve hashed static assets (JS/CSS/images) directly — these have exact filenames
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    # Catch-all: any path not matched by /api/* or /assets/* returns index.html
    # so React Router handles client-side navigation (including hard refresh on /reports/*)
    @app.get("/{full_path:path}")
    async def serve_spa(_full_path: str) -> FileResponse:
        return FileResponse(str(_frontend_dist / "index.html"))
