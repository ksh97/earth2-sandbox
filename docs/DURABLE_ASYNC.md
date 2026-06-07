# Durable Async Queue and Store Plan

This plan covers the migration from the current queue-ready modular monolith to a
durable async backend. It is a hardening backlog item, not a runtime behavior
change for the current PR.

## Current State

The backend already has the right seams for async forecast jobs:

- `ForecastQueue` is an application port for enqueue, dequeue, complete, and
  fail/requeue operations.
- `InMemoryPriorityForecastQueue` is the current process-local queue adapter.
- `ForecastJobStore` is an application port for job state, events, retries,
  active-job recovery, and cleanup.
- The `memory` job store is development-only.
- The `file` job store persists local JSON job documents and hosted-provider
  diagnostics across backend restarts.
- The mobile contract already uses command/query separation:
  `POST /api/v1/forecast/jobs`, lightweight polling, terminal detail fetch,
  retry, cancel, history, and cleanup.

The current implementation is queue-ready, but it is not production durable.
The in-memory queue cannot survive a process exit, cannot coordinate multiple
backend replicas, and does not provide distributed visibility into queue depth,
leases, or dead-lettered work. The file-backed job store is useful for local
diagnostics and restart recovery, but it is not a multi-process authoritative
job database.

## Product Requirement

The durable backend must preserve the current public API contract while making
forecast execution reliable enough for:

- high-resolution risk alerts for saved coordinates and places
- outdoor decision support for hiking, camping, fishing, drones, and filming
- B2B operational weather-risk workflows for logistics, energy, agriculture,
  and construction sites

The user experience should still hide model latency behind a clear job state
flow. The mobile app should not need to know whether a job is handled by the
local in-process worker, a Redis queue, or a dedicated worker service.

## Target Runtime Shape

```text
Mobile / web clients
  -> FastAPI API process
      -> ForecastJobStore port
          -> PostgreSQL job database
      -> ForecastQueue port
          -> Redis-backed dispatch queue

forecast-worker process
  -> ForecastQueue port
  -> ForecastJobStore port
  -> ForecastProvider port
      -> mock provider or FourCastNet hosted/self-hosted provider
  -> ArtifactStore port
      -> local dev storage or cloud object storage
```

PostgreSQL should become the authoritative source for job state and event
history. Redis should dispatch job ids and support worker coordination. Object
storage should hold large model artifacts once hosted FourCastNet outputs are
available outside the current local cache.

## Proposed Storage Model

`forecast_jobs`

- `job_id` primary key
- `status`
- `latitude`, `longitude`
- `parent_job_id`
- `attempt`
- `priority`
- `idempotency_key`
- `forecast_json`
- `diagnostics_json`
- `created_at`, `updated_at`, `started_at`, `completed_at`
- `cancelled_at`, `failed_at`

`forecast_job_events`

- `event_id` primary key
- `job_id`
- `event_type`
- `message`
- `details_json`
- `created_at`

`forecast_artifacts`

- `artifact_id` primary key
- `job_id`
- `provider`
- `cache_key`
- `content_type`
- `sha256`
- `byte_length`
- `storage_backend`
- `storage_uri`
- `created_at`

Large artifact locations must stay backend-only. API responses may expose a
safe artifact id, but must not expose local filesystem paths, API keys,
presigned URLs, or raw object storage credentials.

## Queue Semantics

The first durable queue adapter should preserve the existing port behavior:

- enqueue by `job_id`
- honor priority where the queue backend supports it
- use `idempotency_key` to avoid duplicate dispatch
- dequeue work for a worker process
- mark completed after terminal job state is persisted
- mark failed with optional requeue outside locks/leases

The durable adapter should assume at-least-once delivery. Workers must therefore
be idempotent:

- A worker must read the latest job before running the provider.
- A cancelled or terminal job must not be overwritten.
- `update_if_status` remains the guard for state transitions.
- A retry creates a new attempt job instead of mutating the original terminal
  job into active work.

## Worker Semantics

The dedicated worker service should run the existing command use cases behind a
new process entrypoint. The API process should remain responsible for request
validation, API key checks, rate limiting, job creation, and polling responses.
The worker process should own provider calls, post-processing, artifact writes,
and final job state updates.

Worker health should be observable with:

- worker start/stop logs with `worker_id`
- queue depth
- active leases
- job run duration
- provider latency
- retry count
- dead-letter count
- stale active jobs recovered or failed

## Configuration Roadmap

Current supported values:

```text
EARTH2_FORECAST_QUEUE_BACKEND=memory|redis
EARTH2_FORECAST_JOB_STORE_BACKEND=memory|file
```

`memory` remains the local default. `redis` is selectable when a Redis server is
available, but it is still a queue-only hardening step; PostgreSQL job storage
and a separate worker process are not enabled yet.

Redis adapter settings:

```text
EARTH2_REDIS_URL=redis://localhost:6379/0
EARTH2_FORECAST_QUEUE_NAME=earth2:forecast-jobs
EARTH2_FORECAST_QUEUE_VISIBILITY_TIMEOUT_SECONDS=300
```

Future values:

```text
EARTH2_FORECAST_JOB_STORE_BACKEND=memory|file|postgres
EARTH2_FORECAST_QUEUE_BACKEND=memory|redis
EARTH2_FORECAST_WORKER_CONCURRENCY=1
EARTH2_DATABASE_URL=postgresql+asyncpg://...
EARTH2_ARTIFACT_STORE_BACKEND=local|s3|gcs|azure
```

These settings should be introduced only when their adapters exist. Until then,
they remain design targets and should not be required by local development.

## Migration Sequence

1. Keep the current public API and mobile polling contract unchanged.
2. Add a durable async design document and roadmap link. This is the current
   step.
3. Add a queue backend setting while keeping `memory` as the default.
4. Add Redis queue adapter contract tests using a real Redis service in CI or a
   narrowly scoped integration test job. This is now in place.
5. Add PostgreSQL job store adapter and migrations while keeping `file` useful
   for local hosted-provider diagnostics.
6. Add `forecast-worker` entrypoint and docker-compose worker service.
7. Move startup recovery from process-local assumptions to database-backed
   lease/stale-job recovery.
8. Add queue and worker metrics to `/metrics`.
9. Add object artifact storage after real FourCastNet hosted tar outputs are
   reliably available.
10. Add cloud deployment settings and secret-management documentation.

## Acceptance Criteria

The durable async implementation is not ready until all of these are true:

- OpenAPI snapshot remains stable unless an intentional contract change is made.
- Each queue adapter passes the shared `ForecastQueue` contract tests before it
  is selectable in production settings.
- Mobile generated API types still pass typecheck.
- `queued`, `running`, `succeeded`, `failed`, and `cancelled` semantics remain
  compatible with the existing prototype.
- Retry creates a new attempt job and preserves parent job diagnostics.
- Cancelled jobs are not overwritten by late provider results.
- Backend restarts do not lose accepted jobs.
- Multiple workers do not run the same active job concurrently.
- Provider failures are observable in job diagnostics.
- Queue depth, worker health, and job lifecycle metrics are exported.
- No secrets, local paths, presigned URLs, or large forecast artifacts are
  exposed in API responses or committed to GitHub.

## Non-Goals For The First Durable PR

- Do not replace the in-memory queue in the same PR that introduces the plan.
- Do not remove compatibility imports from `app.py`, `services/jobs.py`,
  `providers`, `clients`, or `postprocessing`.
- Do not change response field names.
- Do not make the mobile app depend on backend implementation details.
- Do not commit real hosted FourCastNet tar outputs.
