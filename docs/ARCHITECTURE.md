# Architecture

## Why Backend First

FourCastNet produces global, multi-step weather forecasts and returns large numerical outputs. The mobile app should not handle raw model inputs, model credentials, GPU inference, or large array post-processing directly.

The first production-oriented architecture is:

```text
Mobile app
  -> Backend API
      -> Forecast service
          -> FourCastNet NIM or mock forecast provider
      -> Post-processing
      -> JSON summaries, map tiles, charts
```

## Components

### Mobile App

Current direction: React Native with Expo.

Responsibilities:

- Ask for a location.
- Show current forecast summaries.
- Show map or chart visualizations.
- Receive push notifications later.

Current prototype path: `apps/mobile`.

### Backend API

Recommended direction: Python FastAPI.

Responsibilities:

- Hide API keys and model endpoints.
- Call FourCastNet NIM.
- Convert large model outputs into smaller mobile-friendly responses.
- Cache forecasts to avoid repeated expensive inference.
- Provide stable API contracts for iOS and Android.

Current backend layout:

- `schemas/forecast.py`: API response models shared by routes and providers
- `providers/base.py`: forecast provider protocol and provider-level errors
- `providers/mock.py`: deterministic point forecast provider for app development
- `providers/fourcastnet.py`: FourCastNet readiness boundary for future inference
- `providers/factory.py`: environment-driven provider selection
- `clients/nim.py`: low-level self-hosted/hosted FourCastNet client helpers
- `postprocessing/fourcastnet.py`: backend-only tar/NumPy decoder and output metadata summarizer
- `services/jobs.py`: queued forecast job contract and process-local worker orchestration
- `storage/fourcastnet.py`: filesystem cache for hosted tar outputs, keyed by sanitized request payload

### FourCastNet NIM

FourCastNet NIM exposes an HTTP API for inference and health checks. The NVIDIA documentation describes `/v1/infer`, `/v1/health/live`, `/v1/health/ready`, and `/v1/metrics`.

The current codebase starts with a mock forecast provider so that mobile and API development can continue before GPU/NIM deployment is ready.

The backend selects a forecast provider with `EARTH2_FORECAST_PROVIDER`:

- `mock`: deterministic point forecasts used by the mobile prototype
- `fourcastnet`: readiness/client boundary for self-hosted NIM or the hosted NVIDIA API

The FourCastNet provider intentionally reports readiness separately from point-forecast support. Raw model inference still needs input preparation and post-processing before it can replace the mock mobile payload.

The first real inference path targets the hosted NVIDIA API because it avoids local GPU,
Docker, and ERA5 input preparation while the backend adapter contract is being tested.
The adapter posts documented hosted API parameters and returns response metadata instead
of streaming large tar payloads directly to the mobile app. A post-processing report is
attached to each hosted inference result so raw output decoding remains a backend-only
concern until it can produce the stable `ForecastSummary` contract.

When the hosted endpoint returns `application/x-tar`, the backend now decodes NumPy
members that follow NVIDIA's `000_000.npy`, `006_000.npy`, and later lead-time naming
pattern. The API response exposes only safe metadata such as lead times, batch indices,
array shape, dtype, and finite min/max/mean values; the raw array bytes remain excluded
from the JSON response.

The point forecast sampler uses the requested variable order to read `w10m`, `t2m`,
`msl`, and `tcwv` from 4D `(batch, variable, latitude, longitude)` or 5D
`(batch, time, variable, latitude, longitude)` arrays. It maps user coordinates to the
nearest global latitude/longitude grid cell, converts Kelvin to Celsius and Pa to hPa,
and derives a lightweight moisture/rain-risk proxy until richer precipitation variables
or calibrated post-processing are available.

The hosted API may run asynchronously or store large outputs outside the immediate response.
The backend client handles the current NVCF-oriented flow in three layers:

- `202 Accepted`: poll the configured NVCF status endpoint with the returned request id.
- `302 Location`: download the large result from the returned location without exposing the URL to mobile clients.
- JSON `responseReference`: download the referenced result when NVIDIA returns a direct response reference.

When tar bytes are available, the provider stores them in the local FourCastNet result cache
under `data/cache/fourcastnet` by default. The cache key is derived from the hosted request
payload and requested content type, not from API keys or presigned URLs. This allows point
forecast development to be replayed from local tar files without repeatedly calling hosted
inference.

The hosted API may still return a small JSON marker such as `{"message": "Large asset written"}`
without a downloadable `Location` or `responseReference`. The backend records the NVCF request id,
status, polling count, and response source for diagnostics, but point sampling still requires
actual tar bytes from a downloadable hosted result or a local sample file.

## First API Contract

`GET /health`

Returns backend status.

`GET /api/v1/forecast/provider/status`

Returns the selected forecast provider, endpoint mode, readiness, and whether point-forecast responses are currently supported.

`POST /api/v1/forecast/fourcastnet/hosted/infer`

Runs a hosted NVIDIA FourCastNet inference request when `EARTH2_FORECAST_PROVIDER=fourcastnet`,
`EARTH2_FOURCASTNET_ENDPOINT_MODE=hosted`, and `EARTH2_NVIDIA_API_KEY` are configured. This is
an adapter smoke-test endpoint, not yet the mobile point-forecast endpoint. The response includes
decoded tar metadata and a post-processing report with the remaining steps required to turn raw
FourCastNet output into mobile forecast summaries.

`GET /api/v1/forecast/point?latitude=37.5665&longitude=126.9780`

Returns a mobile-friendly forecast payload for UI prototyping:

- top-level summary metrics for the overview screen
- model metadata and forecast window information
- deterministic timeline steps for the detail screen
- signal levels for precipitation, wind, and model confidence

When `EARTH2_FORECAST_PROVIDER=fourcastnet`, `EARTH2_FOURCASTNET_ENDPOINT_MODE=hosted`,
and `EARTH2_NVIDIA_API_KEY` are configured, this same endpoint requests hosted
FourCastNet tar output, samples the nearest grid cell for the requested coordinates,
and returns the stable `ForecastSummary` shape used by the mobile app.

`POST /api/v1/forecast/jobs`

Creates a process-local queued forecast job for a point forecast request. This is the
first CQRS-friendly boundary: clients can command the backend to start a forecast job
without waiting for hosted inference, then query job state separately.

The job store is configurable:

- `memory`: process-local development default
- `file`: writes one JSON document per job under `EARTH2_FORECAST_JOB_STORE_DIR`

The file-backed store is not a distributed queue, but it keeps hosted-call diagnostics
across backend restarts and creates a simple migration path toward Redis, a database,
or a worker service.

`GET /api/v1/forecast/jobs?limit=20&status=succeeded`

Returns recent job summaries sorted by creation time. The optional `status` filter accepts
`queued`, `running`, `succeeded`, or `failed`. List responses intentionally omit the full
forecast payload so a UI can poll recent jobs cheaply.

`GET /api/v1/forecast/jobs/{job_id}`

Returns the job state:

- `queued`: accepted but not started
- `running`: provider request is executing
- `succeeded`: forecast summary is available
- `failed`: provider or post-processing failed
- `cancelled`: client requested cancellation before a terminal result was stored

The job response includes a `diagnostics` object. Mock providers return minimal provider
diagnostics. FourCastNet jobs can expose backend-only operational facts such as response
source, cache status, cache artifact id, polling count, NVCF request id/status, and byte length.
API keys, local filesystem paths, and download URLs are never exposed.

Full job responses also include an `events` array. Events record lifecycle transitions such as
accepted, provider request started, forecast summary ready, or failure. This is a small local
event-history boundary that can later move to durable event storage without changing the mobile
contract.

`GET /api/v1/forecast/jobs/{job_id}/poll`

Returns a lightweight polling document for mobile clients. It includes status, terminal flag,
forecast readiness, latest event, retry-after hint, and links, but intentionally excludes the
full forecast payload.

`POST /api/v1/forecast/jobs/{job_id}/cancel`

Transitions a `queued` or `running` job to `cancelled`. The current in-process worker cannot
abort an already-running provider request at the transport layer, but it checks the latest job
state before storing a provider result so a cancelled job is not overwritten as succeeded.

`POST /api/v1/forecast/jobs/{job_id}/retry`

Creates a new job for the same coordinates once the source job is terminal. The new job records
`parent_job_id` and increments `attempt`, which keeps retry history observable without mutating
the original job document.

`POST /api/v1/forecast/jobs/cleanup`

Deletes terminal jobs older than the configured retention window. `EARTH2_FORECAST_JOB_RETENTION_HOURS`
defaults to 168 hours and can be overridden per cleanup request. This keeps local job files bounded
while preserving active work and recent diagnostics.

`GET /api/v1/forecast/sample?latitude=37.5665&longitude=126.9780`

Compatibility alias for earlier mobile prototypes.

## Later API Contracts

- `POST /api/v1/forecast/fourcastnet`
- `GET /api/v1/forecast/{forecast_id}`
- `GET /api/v1/forecast/{forecast_id}/timeseries`
- `GET /api/v1/forecast/{forecast_id}/tiles/{z}/{x}/{y}.png`
- `POST /api/v1/alerts/subscriptions`

## Deployment Shape

Early stage:

- FastAPI backend on a small cloud server.
- Mock forecast data.
- Mobile app connected to backend.
- Expo app running on iOS Simulator, Android Emulator, or Expo Go.

Model integration stage:

- Backend calls a self-hosted FourCastNet NIM.
- Forecast jobs run asynchronously.
- Results are cached in object storage.
- The in-memory job store is replaced with a durable queue/store such as Redis, a database,
  or a dedicated worker service.

Production stage:

- Authentication.
- Rate limiting.
- Monitoring.
- Forecast cache invalidation.
- Store release pipelines for iOS and Android.
