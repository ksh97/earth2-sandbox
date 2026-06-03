# Earth-2 Mobile Prototype

This is the first Expo mobile prototype for the Earth-2 weather forecast app. It creates queued forecast jobs through the FastAPI backend, polls lightweight job status, and fetches the completed forecast payload once the backend marks the job terminal.

## Requirements

- Node.js 22.13 or newer for Expo SDK 56.
- The backend running at `http://127.0.0.1:8000`.

## Setup

```powershell
cd apps/mobile
npm install
Copy-Item .env.example .env
npm run start
```

For browser preview:

```powershell
$env:EXPO_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npm run web
```

For Android Emulator, keep the default API URL as `http://10.0.2.2:8000`. For iOS Simulator, use `http://127.0.0.1:8000`. For a physical phone, set `EXPO_PUBLIC_API_BASE_URL` to the LAN address of the backend machine.

## Current Scope

- Location input using latitude and longitude.
- Forecast summary cards.
- Forecast detail view with timeline steps, model metadata, and signal levels.
- Mock backend API integration.
- Backend provider status panel.
- Queued forecast job status panel.
- Recent forecast job history with status filters.
- Retry and cancel controls for forecast job lifecycle testing.
- Runtime validation for backend forecast and provider status payloads.
- Loading and error states.

## Code Layout

- `App.tsx`: Expo entry point.
- `src/screens/ForecastScreen.tsx`: top-level forecast screen composition.
- `src/hooks/useForecast.ts`: forecast state, location selection, and backend requests.
- `src/components/`: reusable forecast UI panels.
- `src/generated/earth2-api/schema.ts`: TypeScript types generated from the committed OpenAPI snapshot.
- `src/api/forecast.ts`: thin backend forecast API request helper and runtime payload validation.

## API Types

Regenerate the mobile API types after an intentional backend contract change:

```powershell
npm run generate:api
npm run check:api
```

The source contract is `../../contracts/openapi/earth2-api.v1.yaml`. The generated file is committed so the prototype can typecheck without calling the backend at build time.
