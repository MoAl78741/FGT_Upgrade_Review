import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.sql import func

from .database import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    from_version = Column(String(20), nullable=False)
    to_version = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    use_selenium = Column(Boolean, default=False)
    grid_url = Column(String(256), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    log = Column(Text, nullable=False, default="")

    # "scrape" (default) or "pdf"
    source = Column(String(20), nullable=True, default="scrape")

    # Populated on completion
    versions_json = Column(Text, nullable=True)
    all_data_json = Column(Text, nullable=True)
    special_notices_json = Column(Text, nullable=True)
