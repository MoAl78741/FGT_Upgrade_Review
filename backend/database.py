import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

DB_PATH = Path(os.environ.get("DB_PATH", str(Path(__file__).parent.parent / "fgt_upgrade.db")))
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """
    Safe incremental migrations — adds missing columns to existing tables
    without ever dropping data.
    """
    insp = inspect(engine)
    if "scrape_jobs" not in insp.get_table_names():
        return  # Table doesn't exist yet; create_all() will handle it

    existing = {col["name"] for col in insp.get_columns("scrape_jobs")}
    pending = [
        ("grid_url", "VARCHAR(256)"),
        ("source",   "VARCHAR(20)"),
    ]
    with engine.begin() as conn:
        for col_name, col_type in pending:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE scrape_jobs ADD COLUMN {col_name} {col_type}"))
