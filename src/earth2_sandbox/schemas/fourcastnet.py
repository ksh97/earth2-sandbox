from typing import Any, Literal

from pydantic import BaseModel, Field

HostedFourCastNetVariable = Literal["w10m", "t2m", "msl", "tcwv", "z500"]
HostedFourCastNetAccept = Literal["application/json", "application/x-tar"]


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
