import tarfile
from datetime import UTC, datetime, timedelta
from io import BytesIO

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from earth2_sandbox.app import create_app
from earth2_sandbox.clients.nim import FourCastNetNimClient
from earth2_sandbox.config import Settings
from earth2_sandbox.providers import FourCastNetForecastProvider, MockForecastProvider
from earth2_sandbox.schemas.jobs import ForecastJobDiagnostics, ForecastJobEvent
from earth2_sandbox.services import (
    FileForecastJobStore,
    ForecastJobConflictError,
    ForecastJobNotFoundError,
    ForecastJobService,
    ForecastJobTransitionError,
    InMemoryForecastJobStore,
)


def test_fourcastnet_job_exposes_asset_and_cache_diagnostics(tmp_path) -> None:
    content = _build_tar_bytes(
        {
            "000_000.npy": _build_point_array(
                wind_speed_ms=7,
                temperature_k=292.15,
                pressure_pa=101100,
                tcwv=36,
            ),
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=content,
            headers={"content-type": "application/x-tar"},
        )

    settings = Settings(
        forecast_provider="fourcastnet",
        fourcastnet_endpoint_mode="hosted",
        nvidia_api_key="test-key",
        fourcastnet_cache_dir=str(tmp_path),
    )
    provider = FourCastNetForecastProvider(
        client=FourCastNetNimClient(
            base_url="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
            mode="hosted",
            api_key="test-key",
            transport=httpx.MockTransport(handler),
        )
    )
    api_client = TestClient(create_app(settings=settings, forecast_provider_override=provider))

    response = api_client.post(
        "/api/v1/forecast/jobs",
        json={"latitude": 0, "longitude": 90},
    )

    assert response.status_code == 202
    job_url = response.json()["links"]["self"]
    job = api_client.get(job_url).json()

    assert job["status"] == "succeeded"
    assert job["forecast"]["provider"] == "fourcastnet"
    assert [event["status"] for event in job["events"]] == ["queued", "running", "succeeded"]
    assert job["diagnostics"]["provider"] == "fourcastnet"
    assert job["diagnostics"]["response_source"] == "inline"
    assert job["diagnostics"]["cache_status"] == "disabled"
    assert job["diagnostics"]["cached_artifact_id"] is None
    assert "cached_tar_path" not in job["diagnostics"]
    assert job["diagnostics"]["byte_length"] == len(content)


def test_forecast_job_records_provider_failures() -> None:
    class FailingProvider:
        async def get_status(self):
            raise AssertionError("not used")

        async def get_point_forecast(self, *, latitude: float, longitude: float):
            raise RuntimeError("boom")

    api_client = TestClient(
        create_app(
            settings=Settings(forecast_provider="mock"),
            forecast_provider_override=FailingProvider(),
        )
    )

    response = api_client.post(
        "/api/v1/forecast/jobs",
        json={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert response.status_code == 202
    job = api_client.get(response.json()["links"]["self"]).json()

    assert job["status"] == "failed"
    assert [event["status"] for event in job["events"]] == ["queued", "running", "failed"]
    assert "Unexpected forecast job error" in job["error"]


def test_file_forecast_job_store_persists_job_state(tmp_path) -> None:
    import asyncio

    async def scenario():
        first_store = FileForecastJobStore(tmp_path)
        job = await first_store.create(latitude=37.5665, longitude=126.9780)
        await first_store.update(job.model_copy(update={"status": "running"}))

        second_store = FileForecastJobStore(tmp_path)
        return await second_store.get(job.id)

    loaded = asyncio.run(scenario())

    assert loaded.status == "running"
    assert [event.status for event in loaded.events] == ["queued"]
    assert loaded.latitude == 37.5665
    assert loaded.longitude == 126.9780
    assert (tmp_path / f"{loaded.id}.json").exists()


def test_file_forecast_job_store_rejects_path_like_job_ids(tmp_path) -> None:
    import asyncio

    async def scenario():
        store = FileForecastJobStore(tmp_path)
        for job_id in ("../outside", "..\\outside", "not-a-uuid"):
            with pytest.raises(ForecastJobNotFoundError):
                await store.get(job_id)

    asyncio.run(scenario())
    assert not (tmp_path.parent / "outside.json").exists()


def test_file_forecast_job_store_rejects_stale_status_transition(tmp_path) -> None:
    import asyncio

    async def scenario():
        store = FileForecastJobStore(tmp_path)
        queued = await store.create(latitude=37.5665, longitude=126.9780)
        running = await store.update_if_status(
            queued.model_copy(update={"status": "running"}),
            expected_statuses={"queued"},
        )
        cancelled = await store.update_if_status(
            running.model_copy(update={"status": "cancelled"}),
            expected_statuses={"running"},
        )

        with pytest.raises(ForecastJobTransitionError) as error:
            await store.update_if_status(
                running.model_copy(update={"status": "succeeded"}),
                expected_statuses={"running"},
            )

        return cancelled, error.value

    cancelled, error = asyncio.run(scenario())

    assert cancelled.status == "cancelled"
    assert error.current_status == "cancelled"
    assert error.expected_statuses == frozenset({"running"})


def test_api_can_use_file_backed_job_store(tmp_path) -> None:
    api_client = TestClient(
        create_app(
            settings=Settings(
                forecast_provider="mock",
                forecast_job_store_backend="file",
                forecast_job_store_dir=str(tmp_path),
            )
        )
    )

    response = api_client.post(
        "/api/v1/forecast/jobs",
        json={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert response.status_code == 202
    job = api_client.get(response.json()["links"]["self"]).json()
    assert job["status"] == "succeeded"
    assert job["forecast"]["provider"] == "mock"
    assert [event["status"] for event in job["events"]] == ["queued", "running", "succeeded"]
    assert (tmp_path / f"{job['id']}.json").exists()

    list_response = api_client.get("/api/v1/forecast/jobs", params={"limit": 5})
    assert list_response.status_code == 200
    assert list_response.json()["jobs"][0]["id"] == job["id"]


def test_file_forecast_job_store_lists_recent_jobs(tmp_path) -> None:
    import asyncio

    async def scenario():
        store = FileForecastJobStore(tmp_path)
        first = await store.create(latitude=37.5665, longitude=126.9780)
        await store.create(latitude=35.6762, longitude=139.6503)
        await store.update(first.model_copy(update={"status": "failed"}))
        return await store.list_recent(limit=10), await store.list_recent(limit=10, status="failed")

    all_jobs, failed_jobs = asyncio.run(scenario())

    assert [job.latitude for job in all_jobs] == [35.6762, 37.5665]
    assert [job.id for job in failed_jobs] == [all_jobs[1].id]


def test_forecast_job_service_cancels_queued_job() -> None:
    import asyncio

    async def scenario():
        service = ForecastJobService(provider=MockForecastProvider())
        job = await service.create_job(latitude=37.5665, longitude=126.9780)
        cancelled = await service.cancel_job(job.id)
        await service.run_job(job.id)
        loaded = await service.get_job(job.id)
        return cancelled, loaded

    cancelled, loaded = asyncio.run(scenario())

    assert cancelled.status == "cancelled"
    assert loaded.status == "cancelled"
    assert loaded.forecast is None
    assert [event.status for event in loaded.events] == ["queued", "cancelled"]


def test_forecast_job_service_does_not_overwrite_concurrent_cancel() -> None:
    import asyncio

    class CancelBeforeSuccessStore:
        def __init__(self) -> None:
            self.inner = InMemoryForecastJobStore()
            self.cancelled = False

        def __getattr__(self, name: str):
            return getattr(self.inner, name)

        async def update_if_status(self, job, *, expected_statuses):
            if job.status == "succeeded" and not self.cancelled:
                self.cancelled = True
                current = await self.inner.get(job.id)
                now = datetime.now(UTC)
                cancelled = current.model_copy(
                    update={
                        "status": "cancelled",
                        "completed_at": now,
                        "diagnostics": ForecastJobDiagnostics(
                            message="Simulated concurrent cancellation."
                        ),
                        "error": None,
                        "events": [
                            *current.events,
                            ForecastJobEvent(
                                occurred_at=now,
                                status="cancelled",
                                message="Simulated concurrent cancellation.",
                            ),
                        ],
                    }
                )
                await self.inner.update_if_status(cancelled, expected_statuses={"running"})

            return await self.inner.update_if_status(
                job,
                expected_statuses=expected_statuses,
            )

    async def scenario():
        service = ForecastJobService(
            provider=MockForecastProvider(),
            store=CancelBeforeSuccessStore(),
        )
        job = await service.create_job(latitude=37.5665, longitude=126.9780)
        await service.run_job(job.id)
        return await service.get_job(job.id)

    loaded = asyncio.run(scenario())

    assert loaded.status == "cancelled"
    assert loaded.forecast is None
    assert [event.status for event in loaded.events] == ["queued", "running", "cancelled"]


def test_forecast_job_service_recovers_interrupted_active_jobs(tmp_path) -> None:
    import asyncio

    class RecordingWorker:
        def __init__(self) -> None:
            self.job_ids: list[str] = []

        def enqueue(self, job_id: str) -> None:
            self.job_ids.append(job_id)

    async def scenario():
        store = FileForecastJobStore(tmp_path)
        service = ForecastJobService(
            provider=MockForecastProvider(),
            store=store,
            default_stale_timeout_seconds=3600,
        )
        queued = await store.create(latitude=37.5665, longitude=126.9780)
        running = await store.create(latitude=35.6762, longitude=139.6503)
        await store.update_if_status(
            running.model_copy(update={"status": "running"}),
            expected_statuses={"queued"},
        )
        worker = RecordingWorker()

        report = await service.recover_interrupted_jobs(worker=worker)
        loaded_running = await store.get(running.id)
        return report, worker.job_ids, queued, loaded_running

    report, job_ids, queued, loaded_running = asyncio.run(scenario())

    assert report.scanned_count == 2
    assert report.requeued_count == 2
    assert report.timed_out_count == 0
    assert set(job_ids) == {queued.id, loaded_running.id}
    assert loaded_running.status == "queued"
    assert loaded_running.started_at is None
    assert loaded_running.events[-1].status == "queued"
    assert loaded_running.events[-1].message == "Forecast job recovered for worker retry."


def test_forecast_job_service_times_out_stale_active_jobs(tmp_path) -> None:
    import asyncio

    class RecordingWorker:
        def __init__(self) -> None:
            self.job_ids: list[str] = []

        def enqueue(self, job_id: str) -> None:
            self.job_ids.append(job_id)

    async def scenario():
        store = FileForecastJobStore(tmp_path)
        service = ForecastJobService(
            provider=MockForecastProvider(),
            store=store,
            default_stale_timeout_seconds=60,
        )
        job = await store.create(latitude=37.5665, longitude=126.9780)
        old_time = datetime.now(UTC) - timedelta(minutes=10)
        stale_running = job.model_copy(
            update={
                "status": "running",
                "started_at": old_time,
                "updated_at": old_time,
            }
        )
        (tmp_path / f"{job.id}.json").write_text(
            stale_running.model_dump_json(indent=2),
            encoding="utf-8",
        )
        worker = RecordingWorker()

        report = await service.recover_interrupted_jobs(worker=worker)
        loaded = await store.get(job.id)
        return report, worker.job_ids, loaded

    report, job_ids, loaded = asyncio.run(scenario())

    assert report.scanned_count == 1
    assert report.requeued_count == 0
    assert report.timed_out_count == 1
    assert job_ids == []
    assert loaded.status == "failed"
    assert loaded.completed_at is not None
    assert loaded.error == "Forecast worker timed out after 60 seconds without progress."
    assert loaded.events[-1].status == "failed"
    assert loaded.events[-1].message == "Forecast worker timed out."


def test_forecast_job_service_rejects_retry_for_active_job() -> None:
    import asyncio

    async def scenario():
        service = ForecastJobService(provider=MockForecastProvider())
        job = await service.create_job(latitude=37.5665, longitude=126.9780)
        with pytest.raises(ForecastJobConflictError):
            await service.retry_job(job.id)

    asyncio.run(scenario())


def test_file_forecast_job_store_cleans_up_old_terminal_jobs(tmp_path) -> None:
    import asyncio

    async def scenario():
        store = FileForecastJobStore(tmp_path)
        service = ForecastJobService(provider=MockForecastProvider(), store=store)
        old_job = await store.create(latitude=37.5665, longitude=126.9780)
        fresh_job = await store.create(latitude=35.6762, longitude=139.6503)

        old_time = datetime.now(UTC) - timedelta(hours=200)
        old_terminal = old_job.model_copy(
            update={
                "status": "succeeded",
                "updated_at": old_time,
                "completed_at": old_time,
            }
        )
        (tmp_path / f"{old_job.id}.json").write_text(
            old_terminal.model_dump_json(indent=2),
            encoding="utf-8",
        )
        await store.update(fresh_job.model_copy(update={"status": "succeeded"}))

        cleanup = await service.cleanup_jobs(older_than_hours=168)
        remaining = await store.list_recent(limit=10)
        return cleanup, remaining

    cleanup, remaining = asyncio.run(scenario())

    assert cleanup.deleted_count == 1
    assert [job.latitude for job in remaining] == [35.6762]


def _build_tar_bytes(entries: dict[str, np.ndarray]) -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for filename, array in entries.items():
            array_buffer = BytesIO()
            np.save(array_buffer, array)
            data = array_buffer.getvalue()
            info = tarfile.TarInfo(filename)
            info.size = len(data)
            archive.addfile(info, BytesIO(data))

    return buffer.getvalue()


def _build_point_array(
    *,
    wind_speed_ms: float,
    temperature_k: float,
    pressure_pa: float,
    tcwv: float,
) -> np.ndarray:
    array = np.zeros((1, 5, 3, 4), dtype=np.float32)
    latitude_index = 1
    longitude_index = 1
    array[0, 0, latitude_index, longitude_index] = wind_speed_ms
    array[0, 1, latitude_index, longitude_index] = temperature_k
    array[0, 2, latitude_index, longitude_index] = pressure_pa
    array[0, 3, latitude_index, longitude_index] = tcwv
    array[0, 4, latitude_index, longitude_index] = 5500
    return array
