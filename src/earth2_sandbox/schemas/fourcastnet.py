from typing import Any, Literal

from pydantic import BaseModel, Field

HostedFourCastNetVariable = Literal["w10m", "t2m", "msl", "tcwv", "z500"]
HostedFourCastNetAccept = Literal["application/json", "application/x-tar"]
FourCastNetResponseSource = Literal["inline", "poll", "redirect", "response_reference", "cache"]
FourCastNetCacheStatus = Literal["disabled", "hit", "miss", "stored"]


class FourCastNetHostedInferenceRequest(BaseModel):
    input_id: int = Field(default=0, ge=0, le=3)
    variables: list[HostedFourCastNetVariable] = Field(
        default_factory=lambda: ["w10m", "t2m", "msl", "tcwv", "z500"]
    )
    simulation_length: int = Field(default=4, ge=1, le=40)
    ensemble_size: int = Field(default=1, ge=1, le=4)
    noise_amplitude: float = Field(default=0, ge=0, le=0.1)
    accept: HostedFourCastNetAccept = "application/x-tar"
    poll_seconds: int = Field(default=5, ge=1, le=120)


class FourCastNetHostedInferenceResult(BaseModel):
    endpoint: str
    status_code: int
    content_type: str
    byte_length: int
    sha256: str
    request_payload: dict[str, int | float | str]
    json_preview: Any | None = None
    decoded_tar: "FourCastNetDecodedTarSummary | None" = None
    post_processing: "FourCastNetPostProcessingReport | None" = None
    nvcf_request_id: str | None = None
    nvcf_status: str | None = None
    large_asset_message: str | None = None
    poll_attempts: int = 0
    response_source: FourCastNetResponseSource = "inline"
    response_reference_present: bool = False
    cache_status: FourCastNetCacheStatus = "disabled"
    cached_artifact_id: str | None = None
    raw_content: bytes | None = Field(default=None, exclude=True, repr=False)


class FourCastNetPostProcessingReport(BaseModel):
    mobile_summary_ready: bool
    detected_format: Literal["tar", "json", "unknown"]
    required_steps: list[str]
    notes: list[str]


class FourCastNetDecodedArray(BaseModel):
    filename: str
    lead_time_hours: int
    batch_index: int
    shape: list[int]
    dtype: str
    finite_count: int
    min_value: float | None
    max_value: float | None
    mean_value: float | None


class FourCastNetDecodedTarSummary(BaseModel):
    member_count: int
    arrays: list[FourCastNetDecodedArray]
    lead_time_hours: list[int]
    batch_indices: list[int]
    warnings: list[str]
