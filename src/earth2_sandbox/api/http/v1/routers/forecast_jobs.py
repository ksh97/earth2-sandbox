from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from earth2_sandbox.application.ports.forecast_queue import ForecastQueue
from earth2_sandbox.infrastructure.queue import QueuedDeferredForecastJobWorker
from earth2_sandbox.observability.structured_logging import log_event
from earth2_sandbox.schemas.jobs import (
    ForecastJob,
    ForecastJobCleanupRequest,
    ForecastJobCleanupResponse,
    ForecastJobCreateRequest,
    ForecastJobListResponse,
    ForecastJobPollResponse,
    ForecastJobStatus,
)
from earth2_sandbox.services.jobs import (
    ForecastJobConflictError,
    ForecastJobNotFoundError,
    ForecastJobService,
)


def create_forecast_jobs_router(
    *,
    forecast_job_service: ForecastJobService,
    forecast_queue: ForecastQueue,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/forecast/jobs", tags=["forecast-jobs"])

    def enqueue_job(background_tasks: BackgroundTasks, job_id: str) -> None:
        worker = QueuedDeferredForecastJobWorker(
            add_task=background_tasks.add_task,
            run_job=forecast_job_service.run_job,
            queue=forecast_queue,
        )
        worker.enqueue(job_id)

    @router.post("", response_model=ForecastJob, status_code=status.HTTP_202_ACCEPTED)
    async def create_forecast_job(
        request: ForecastJobCreateRequest,
        background_tasks: BackgroundTasks,
    ) -> ForecastJob:
        job = await forecast_job_service.create_job(
            latitude=request.latitude,
            longitude=request.longitude,
        )
        log_event(
            "forecast_job.accepted",
            job_id=job.id,
            status=job.status,
            latitude=job.latitude,
            longitude=job.longitude,
            attempt=job.attempt,
        )
        enqueue_job(background_tasks, job.id)
        return job

    @router.get("", response_model=ForecastJobListResponse)
    async def list_forecast_jobs(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        job_status: Annotated[ForecastJobStatus | None, Query(alias="status")] = None,
    ) -> ForecastJobListResponse:
        return await forecast_job_service.list_recent_jobs(
            limit=limit,
            status=job_status,
        )

    @router.post("/cleanup", response_model=ForecastJobCleanupResponse)
    async def cleanup_forecast_jobs(
        request: ForecastJobCleanupRequest | None = None,
    ) -> ForecastJobCleanupResponse:
        return await forecast_job_service.cleanup_jobs(
            older_than_hours=request.older_than_hours if request else None,
            statuses=request.statuses if request else None,
        )

    @router.get("/{job_id}", response_model=ForecastJob)
    async def get_forecast_job(job_id: str) -> ForecastJob:
        try:
            return await forecast_job_service.get_job(job_id)
        except ForecastJobNotFoundError as error:
            raise HTTPException(status_code=404, detail="Forecast job not found.") from error

    @router.get("/{job_id}/poll", response_model=ForecastJobPollResponse)
    async def poll_forecast_job(job_id: str) -> ForecastJobPollResponse:
        try:
            return await forecast_job_service.poll_job(job_id)
        except ForecastJobNotFoundError as error:
            raise HTTPException(status_code=404, detail="Forecast job not found.") from error

    @router.post("/{job_id}/cancel", response_model=ForecastJob)
    async def cancel_forecast_job(job_id: str) -> ForecastJob:
        try:
            job = await forecast_job_service.cancel_job(job_id)
        except ForecastJobNotFoundError as error:
            raise HTTPException(status_code=404, detail="Forecast job not found.") from error
        except ForecastJobConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        log_event(
            "forecast_job.cancelled",
            job_id=job.id,
            status=job.status,
            provider=job.diagnostics.provider if job.diagnostics else None,
        )
        return job

    @router.post(
        "/{job_id}/retry",
        response_model=ForecastJob,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def retry_forecast_job(
        job_id: str,
        background_tasks: BackgroundTasks,
    ) -> ForecastJob:
        try:
            job = await forecast_job_service.retry_job(job_id)
        except ForecastJobNotFoundError as error:
            raise HTTPException(status_code=404, detail="Forecast job not found.") from error
        except ForecastJobConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        enqueue_job(background_tasks, job.id)
        log_event(
            "forecast_job.retry_accepted",
            job_id=job.id,
            parent_job_id=job.parent_job_id,
            status=job.status,
            attempt=job.attempt,
        )
        return job

    return router
