from __future__ import annotations

from typing import Any, Protocol

from earth2_sandbox.application.errors import ForecastJobTransitionError
from earth2_sandbox.application.ports.clock import Clock
from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.ports.forecast_provider import (
    ForecastProvider,
    ForecastProviderResult,
    ForecastProviderUnavailableError,
)
from earth2_sandbox.application.services.forecast_job_view import append_job_event
from earth2_sandbox.observability.structured_logging import log_event
from earth2_sandbox.schemas.jobs import ForecastJob, ForecastJobDiagnostics


class DiagnosticForecastProvider(Protocol):
    async def get_point_forecast_with_diagnostics(
        self,
        latitude: float,
        longitude: float,
    ) -> ForecastProviderResult: ...


class RunForecastJob:
    def __init__(
        self,
        *,
        provider: ForecastProvider,
        store: ForecastJobStore,
        clock: Clock,
    ) -> None:
        self.provider = provider
        self.store = store
        self.clock = clock

    async def execute(self, job_id: str) -> None:
        job = await self.store.get(job_id)
        if job.status != "queued":
            return

        now = self.clock.now()
        running_job = append_job_event(
            job.model_copy(
                update={
                    "status": "running",
                    "started_at": now,
                    "diagnostics": ForecastJobDiagnostics(
                        provider=None,
                        message="Forecast provider request is running.",
                    ),
                    "error": None,
                }
            ),
            status="running",
            message="Forecast provider request started.",
            occurred_at=now,
        )
        try:
            await self.store.update_if_status(running_job, expected_statuses={"queued"})
        except ForecastJobTransitionError:
            return
        log_event(
            "forecast_job.started",
            job_id=job_id,
            status="running",
            latitude=job.latitude,
            longitude=job.longitude,
            attempt=job.attempt,
        )

        try:
            provider_result = await self._get_provider_result(job)
        except ForecastProviderUnavailableError as error:
            await self._mark_failed(
                job_id=job_id,
                error=str(error),
                diagnostics=error.diagnostics,
            )
        except Exception as error:  # pragma: no cover - defensive boundary
            await self._mark_failed(
                job_id=job_id,
                error=f"Unexpected forecast job error: {error}",
            )
        else:
            completed = self.clock.now()
            current = await self.store.get(job_id)
            if current.status != "running":
                return

            succeeded = append_job_event(
                current.model_copy(
                    update={
                        "status": "succeeded",
                        "completed_at": completed,
                        "forecast": provider_result.summary,
                        "diagnostics": ForecastJobDiagnostics(
                            **{
                                **provider_result.diagnostics,
                                "message": "Forecast summary is ready.",
                            }
                        ),
                        "error": None,
                    }
                ),
                status="succeeded",
                message="Forecast summary is ready.",
                occurred_at=completed,
            )
            try:
                updated = await self.store.update_if_status(
                    succeeded,
                    expected_statuses={"running"},
                )
            except ForecastJobTransitionError:
                return
            log_event(
                "forecast_job.succeeded",
                job_id=job_id,
                status=updated.status,
                provider=updated.diagnostics.provider if updated.diagnostics else None,
                response_source=(
                    updated.diagnostics.response_source if updated.diagnostics else None
                ),
                cache_status=updated.diagnostics.cache_status if updated.diagnostics else None,
                nvcf_request_id=(
                    updated.diagnostics.nvcf_request_id if updated.diagnostics else None
                ),
            )

    async def _get_provider_result(self, job: ForecastJob) -> ForecastProviderResult:
        diagnostic_method = getattr(self.provider, "get_point_forecast_with_diagnostics", None)
        if diagnostic_method is not None:
            return await diagnostic_method(latitude=job.latitude, longitude=job.longitude)

        summary = await self.provider.get_point_forecast(
            latitude=job.latitude,
            longitude=job.longitude,
        )
        return ForecastProviderResult(
            summary=summary,
            diagnostics={
                "provider": summary.provider,
                "message": "Provider did not return extended job diagnostics.",
            },
        )

    async def _mark_failed(
        self,
        *,
        job_id: str,
        error: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        job = await self.store.get(job_id)
        if job.status != "running":
            return

        failed_at = self.clock.now()
        diagnostic_payload = diagnostics or {}
        diagnostic_message = diagnostic_payload.get("message") or "Forecast job failed."
        failed = append_job_event(
            job.model_copy(
                update={
                    "status": "failed",
                    "completed_at": failed_at,
                    "error": error,
                    "diagnostics": ForecastJobDiagnostics(
                        **{
                            **diagnostic_payload,
                            "message": diagnostic_message,
                        }
                    ),
                }
            ),
            status="failed",
            message="Forecast job failed.",
            occurred_at=failed_at,
        )
        try:
            updated = await self.store.update_if_status(failed, expected_statuses={"running"})
        except ForecastJobTransitionError:
            return
        log_event(
            "forecast_job.failed",
            job_id=job_id,
            status=updated.status,
            provider=updated.diagnostics.provider if updated.diagnostics else None,
            response_source=updated.diagnostics.response_source if updated.diagnostics else None,
            cache_status=updated.diagnostics.cache_status if updated.diagnostics else None,
            nvcf_request_id=updated.diagnostics.nvcf_request_id if updated.diagnostics else None,
            message=diagnostic_message,
        )
