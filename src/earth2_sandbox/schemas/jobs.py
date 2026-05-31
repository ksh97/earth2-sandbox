from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from earth2_sandbox.schemas.forecast import ForecastSummary

ForecastJobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
ForecastJobTerminalStatus = Literal["succeeded", "failed", "cancelled"]


class ForecastJobCreateRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ForecastJobDiagnostics(BaseModel):
    provider: str | None = None
    response_source: str | None = None
    cache_status: str | None = None
    cached_artifact_id: str | None = None
    nvcf_request_id: str | None = None
    nvcf_status: str | None = None
    poll_attempts: int = 0
    response_reference_present: bool = False
    byte_length: int | None = None
    sha256: str | None = None
    message: str | None = None


class ForecastJobEvent(BaseModel):
    occurred_at: datetime
    status: ForecastJobStatus
    message: str


class ForecastJobSummary(BaseModel):
    id: str
    status: ForecastJobStatus
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    parent_job_id: str | None = None
    attempt: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    diagnostics: ForecastJobDiagnostics | None = None
    error: str | None = None
    links: dict[str, str] = Field(default_factory=dict)


class ForecastJobListResponse(BaseModel):
    count: int
    jobs: list[ForecastJobSummary]


class ForecastJobPollResponse(BaseModel):
    id: str
    status: ForecastJobStatus
    terminal: bool
    forecast_ready: bool
    updated_at: datetime
    retry_after_seconds: int | None = None
    event_count: int
    latest_event: ForecastJobEvent | None = None
    links: dict[str, str] = Field(default_factory=dict)


class ForecastJobCleanupRequest(BaseModel):
    older_than_hours: int = Field(default=168, ge=1, le=8760)
    statuses: list[ForecastJobTerminalStatus] = Field(
        default_factory=lambda: ["succeeded", "failed", "cancelled"]
    )


class ForecastJobCleanupResponse(BaseModel):
    deleted_count: int
    cutoff: datetime
    statuses: list[ForecastJobTerminalStatus]


class ForecastJob(BaseModel):
    id: str
    status: ForecastJobStatus
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    parent_job_id: str | None = None
    attempt: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    forecast: ForecastSummary | None = None
    diagnostics: ForecastJobDiagnostics | None = None
    events: list[ForecastJobEvent] = Field(default_factory=list)
    error: str | None = None
    links: dict[str, str] = Field(default_factory=dict)
