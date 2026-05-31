from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from earth2_sandbox.schemas.forecast import ForecastSummary

ForecastJobStatus = Literal["queued", "running", "succeeded", "failed"]


class ForecastJobCreateRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ForecastJobDiagnostics(BaseModel):
    provider: str | None = None
    response_source: str | None = None
    cache_status: str | None = None
    cached_tar_path: str | None = None
    nvcf_request_id: str | None = None
    nvcf_status: str | None = None
    poll_attempts: int = 0
    response_reference_present: bool = False
    byte_length: int | None = None
    sha256: str | None = None
    message: str | None = None


class ForecastJob(BaseModel):
    id: str
    status: ForecastJobStatus
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    forecast: ForecastSummary | None = None
    diagnostics: ForecastJobDiagnostics | None = None
    error: str | None = None
    links: dict[str, str] = Field(default_factory=dict)
