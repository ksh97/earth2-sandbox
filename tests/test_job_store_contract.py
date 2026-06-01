import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from earth2_sandbox.application.errors import ForecastJobNotFoundError, ForecastJobTransitionError
from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.infrastructure.storage import FileForecastJobStore, InMemoryForecastJobStore


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
