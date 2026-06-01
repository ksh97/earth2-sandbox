from datetime import UTC, datetime, timedelta

import pytest

from earth2_sandbox.domain.jobs.entities import (
    ForecastJobAttempt,
    ForecastJobCoordinates,
    ForecastJobIdentity,
    InvalidForecastJobAttemptError,
    InvalidForecastJobCoordinatesError,
    InvalidForecastJobIdentityError,
)
from earth2_sandbox.domain.jobs.events import record_forecast_job_event
from earth2_sandbox.domain.jobs.policies import (
    can_transition_from,
    should_cleanup_job,
    should_mark_job_stale,
)
from earth2_sandbox.domain.jobs.priority import (
    DEFAULT_FORECAST_JOB_PRIORITY,
    FORECAST_JOB_PRIORITY_RANK,
    priority_rank,
)
from earth2_sandbox.domain.jobs.status import (
    ACTIVE_JOB_STATUSES,
    TERMINAL_JOB_STATUSES,
    is_active_job_status,
    is_terminal_job_status,
)


def test_job_status_groups_are_explicit() -> None:
    assert TERMINAL_JOB_STATUSES == frozenset({"succeeded", "failed", "cancelled"})
    assert ACTIVE_JOB_STATUSES == frozenset({"queued", "running"})
    assert is_terminal_job_status("succeeded")
    assert not is_terminal_job_status("running")
    assert is_active_job_status("queued")
    assert not is_active_job_status("failed")


def test_transition_policy_uses_expected_current_statuses() -> None:
    assert can_transition_from(current_status="queued", expected_statuses={"queued"})
    assert can_transition_from(current_status="running", expected_statuses={"queued", "running"})
    assert not can_transition_from(current_status="cancelled", expected_statuses={"running"})


def test_job_identity_normalizes_uuid_values() -> None:
    identity = ForecastJobIdentity.parse("A49B28EA-C6E3-462D-FE2A-098C5A4E49A8")

    assert identity.value == "a49b28ea-c6e3-462d-fe2a-098c5a4e49a8"


def test_job_identity_rejects_path_like_values() -> None:
    with pytest.raises(InvalidForecastJobIdentityError):
        ForecastJobIdentity.parse("../a49b28ea-c6e3-462d-fe2a-098c5a4e49a8")


def test_job_coordinates_enforce_forecast_bounds() -> None:
    coordinates = ForecastJobCoordinates(latitude=37.5665, longitude=126.978)

    assert coordinates.latitude == 37.5665
    assert coordinates.longitude == 126.978

    with pytest.raises(InvalidForecastJobCoordinatesError):
        ForecastJobCoordinates(latitude=91, longitude=126.978)


def test_job_attempt_enforces_positive_attempts() -> None:
    parent = ForecastJobIdentity.parse("a49b28ea-c6e3-462d-fe2a-098c5a4e49a8")
    attempt = ForecastJobAttempt(value=2, parent_job_id=parent)

    assert attempt.value == 2
    assert attempt.parent_job_id == parent

    with pytest.raises(InvalidForecastJobAttemptError):
        ForecastJobAttempt(value=0)
    with pytest.raises(InvalidForecastJobAttemptError):
        ForecastJobAttempt(value=1, parent_job_id=parent)
    with pytest.raises(InvalidForecastJobAttemptError):
        ForecastJobAttempt(value=2)


def test_job_priority_ranks_are_queue_ready_without_creating_a_queue() -> None:
    assert DEFAULT_FORECAST_JOB_PRIORITY == "normal"
    assert FORECAST_JOB_PRIORITY_RANK == {"high": 0, "normal": 10, "low": 20}
    assert priority_rank("high") < priority_rank("normal") < priority_rank("low")


def test_job_event_record_defaults_to_current_utc_timestamp() -> None:
    before = datetime.now(UTC)
    event = record_forecast_job_event(status="queued", message="Forecast job accepted.")
    after = datetime.now(UTC)

    assert before <= event.occurred_at <= after
    assert event.status == "queued"
    assert event.message == "Forecast job accepted."


def test_stale_policy_is_inclusive_at_timeout_boundary() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    assert should_mark_job_stale(
        updated_at=now - timedelta(seconds=60),
        now=now,
        timeout_seconds=60,
    )
    assert not should_mark_job_stale(
        updated_at=now - timedelta(seconds=59),
        now=now,
        timeout_seconds=60,
    )


def test_cleanup_policy_uses_terminal_status_and_reference_time() -> None:
    cutoff = datetime(2026, 1, 2, tzinfo=UTC)
    before_cutoff = cutoff - timedelta(seconds=1)
    after_cutoff = cutoff + timedelta(seconds=1)

    assert should_cleanup_job(
        status="succeeded",
        completed_at=before_cutoff,
        updated_at=after_cutoff,
        cutoff=cutoff,
        statuses={"succeeded"},
    )
    assert should_cleanup_job(
        status="failed",
        completed_at=None,
        updated_at=before_cutoff,
        cutoff=cutoff,
        statuses={"failed"},
    )
    assert not should_cleanup_job(
        status="running",
        completed_at=None,
        updated_at=before_cutoff,
        cutoff=cutoff,
        statuses={"succeeded", "failed", "cancelled"},
    )
    assert not should_cleanup_job(
        status="cancelled",
        completed_at=after_cutoff,
        updated_at=before_cutoff,
        cutoff=cutoff,
        statuses={"cancelled"},
    )
