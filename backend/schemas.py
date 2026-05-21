from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class CreateJobRequest(BaseModel):
    from_version: str
    to_version: str
    use_selenium: bool = False
    grid_url: Optional[str] = None
    force_rescrape: bool = False


class JobResponse(BaseModel):
    id: str
    from_version: str
    to_version: str
    status: str
    use_selenium: bool
    source: Optional[str] = "scrape"
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    log: Optional[str] = None

    model_config = {"from_attributes": True}


class JobDetailResponse(JobResponse):
    versions: Optional[list] = None
    all_data: Optional[dict[str, Any]] = None
    special_notices: Optional[list] = None
