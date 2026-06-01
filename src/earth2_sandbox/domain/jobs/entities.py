from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


class InvalidForecastJobIdentityError(ValueError):
    """Raised when a forecast job id is not a canonical UUID value."""


class InvalidForecastJobCoordinatesError(ValueError):
    """Raised when forecast job coordinates are outside supported bounds."""


class InvalidForecastJobAttemptError(ValueError):
    """Raised when a forecast job attempt value is invalid."""


@dataclass(frozen=True, slots=True)
class ForecastJobIdentity:
    value: str

    @classmethod
    def parse(cls, value: str) -> ForecastJobIdentity:
        try:
            parsed = UUID(value)
        except (TypeError, ValueError) as error:
            raise InvalidForecastJobIdentityError(str(value)) from error
        return cls(value=str(parsed))


@dataclass(frozen=True, slots=True)
class ForecastJobCoordinates:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise InvalidForecastJobCoordinatesError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise InvalidForecastJobCoordinatesError("longitude must be between -180 and 180")


@dataclass(frozen=True, slots=True)
class ForecastJobAttempt:
    value: int
    parent_job_id: ForecastJobIdentity | None = None

    def __post_init__(self) -> None:
        if self.value < 1:
            raise InvalidForecastJobAttemptError("attempt must be greater than or equal to 1")
        if self.value == 1 and self.parent_job_id is not None:
            raise InvalidForecastJobAttemptError("first attempts cannot reference a parent job")
        if self.value > 1 and self.parent_job_id is None:
            raise InvalidForecastJobAttemptError("retry attempts must reference a parent job")
