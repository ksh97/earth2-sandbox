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

### FourCastNet NIM

FourCastNet NIM exposes an HTTP API for inference and health checks. The NVIDIA documentation describes `/v1/infer`, `/v1/health/live`, `/v1/health/ready`, and `/v1/metrics`.

The current codebase starts with a mock forecast provider so that mobile and API development can continue before GPU/NIM deployment is ready.

## First API Contract

`GET /health`

Returns backend status.

`GET /api/v1/forecast/sample?latitude=37.5665&longitude=126.9780`

Returns a small forecast summary for UI prototyping.

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
