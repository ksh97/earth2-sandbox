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
of streaming large tar payloads directly to the mobile app.

## First API Contract

`GET /health`

Returns backend status.

`GET /api/v1/forecast/provider/status`

Returns the selected forecast provider, endpoint mode, readiness, and whether point-forecast responses are currently supported.

`POST /api/v1/forecast/fourcastnet/hosted/infer`

Runs a hosted NVIDIA FourCastNet inference request when `EARTH2_FORECAST_PROVIDER=fourcastnet`,
`EARTH2_FOURCASTNET_ENDPOINT_MODE=hosted`, and `EARTH2_NVIDIA_API_KEY` are configured. This is
an adapter smoke-test endpoint, not yet the mobile point-forecast endpoint.

`GET /api/v1/forecast/sample?latitude=37.5665&longitude=126.9780`

Returns a mobile-friendly forecast payload for UI prototyping:

- top-level summary metrics for the overview screen
- model metadata and forecast window information
- deterministic timeline steps for the detail screen
- signal levels for precipitation, wind, and model confidence

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

Production stage:

- Authentication.
- Rate limiting.
- Monitoring.
- Forecast cache invalidation.
- Store release pipelines for iOS and Android.
