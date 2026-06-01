import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from earth2_sandbox.application.errors import ForecastJobNotFoundError, ForecastJobTransitionError
from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.infrastructure.storage import FileForecastJobStore, InMemoryForecastJobStore

FIXED_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
FIXED_JOB_ID = "00000000-0000-4000-8000-000000000001"


class FixedClock:
    def now(self) -> datetime:
        return FIXED_NOW


class FixedIdGenerator:
    def new_id(self) -> str:
        return FIXED_JOB_ID


@pytest.mark.parametrize(
    "store_factory",
    [
        lambda: InMemoryForecastJobStore(),
        lambda path: FileForecastJobStore(path),
    ],
)
def test_forecast_job_store_contract_create_update_list_and_cleanup(
    tmp_path,
    store_factory: Callable[..., ForecastJobStore],
) -> None:
    async def scenario() -> None:
        store = store_factory(tmp_path) if store_factory.__code__.co_argcount else store_factory()
        first = await store.create(latitude=37.5665, longitude=126.9780)
        second = await store.create(latitude=35.6762, longitude=139.6503)

        running = await store.update_if_status(
            first.model_copy(update={"status": "running"}),
            expected_statuses={"queued"},
        )
        with pytest.raises(ForecastJobTransitionError):
            await store.update_if_status(
                running.model_copy(update={"status": "cancelled"}),
                expected_statuses={"queued"},
            )

        completed_at = datetime.now(UTC) - timedelta(days=8)
        await store.update_if_status(
            running.model_copy(update={"status": "succeeded", "completed_at": completed_at}),
            expected_statuses={"running"},
        )

        active_jobs = await store.list_active()
        recent_jobs = await store.list_recent(limit=10)
        deleted_count = await store.delete_older_than(
            cutoff=datetime.now(UTC) - timedelta(days=7),
            statuses={"succeeded"},
        )

        assert [job.id for job in active_jobs] == [second.id]
        assert {job.id for job in recent_jobs} == {first.id, second.id}
        assert deleted_count == 1
        with pytest.raises(ForecastJobNotFoundError):
            await store.get(first.id)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "store_factory",
    [
        lambda path, clock, id_generator: InMemoryForecastJobStore(
            clock=clock,
            id_generator=id_generator,
        ),
        lambda path, clock, id_generator: FileForecastJobStore(
            path,
            clock=clock,
            id_generator=id_generator,
        ),
    ],
)
def test_forecast_job_store_uses_clock_and_id_generator_ports(
    tmp_path,
    store_factory: Callable[..., ForecastJobStore],
) -> None:
    async def scenario() -> None:
        store = store_factory(tmp_path, FixedClock(), FixedIdGenerator())
        job = await store.create(latitude=37.5665, longitude=126.9780)
        running = await store.update_if_status(
            job.model_copy(update={"status": "running"}),
            expected_statuses={"queued"},
        )

        assert job.id == FIXED_JOB_ID
        assert job.created_at == FIXED_NOW
        assert job.updated_at == FIXED_NOW
        assert running.updated_at == FIXED_NOW

    asyncio.run(scenario())
