from uuid import UUID

from earth2_sandbox.infrastructure.runtime import SystemClock, UuidIdGenerator


def test_system_clock_returns_timezone_aware_utc_datetime() -> None:
    now = SystemClock().now()

    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 0


def test_uuid_id_generator_returns_uuid4_string() -> None:
    generated = UuidIdGenerator().new_id()

    assert UUID(generated).version == 4
