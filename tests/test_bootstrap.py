from earth2_sandbox.app import create_app
from earth2_sandbox.bootstrap.app_factory import create_app as bootstrap_create_app
from earth2_sandbox.bootstrap.container import build_container
from earth2_sandbox.bootstrap.settings import Settings
from earth2_sandbox.config import Settings as CompatibilitySettings
from earth2_sandbox.infrastructure.queue import InMemoryPriorityForecastQueue
from earth2_sandbox.services import FileForecastJobStore, InMemoryForecastJobStore


def test_app_factory_keeps_compatibility_export() -> None:
    assert create_app is bootstrap_create_app


def test_settings_keep_compatibility_export() -> None:
    assert CompatibilitySettings is Settings


def test_container_selects_memory_job_store_by_default() -> None:
    container = build_container(settings=Settings(forecast_provider="mock"))

    assert isinstance(container.forecast_job_store, InMemoryForecastJobStore)
    assert isinstance(container.forecast_queue, InMemoryPriorityForecastQueue)


def test_container_selects_file_job_store(tmp_path) -> None:
    container = build_container(
        settings=Settings(
            forecast_provider="mock",
            forecast_job_store_backend="file",
            forecast_job_store_dir=str(tmp_path),
        )
    )

    assert isinstance(container.forecast_job_store, FileForecastJobStore)
