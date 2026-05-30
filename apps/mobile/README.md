# Earth-2 Mobile Prototype

This is the first Expo mobile prototype for the Earth-2 weather forecast app. It calls the FastAPI backend mock forecast endpoint so the iOS and Android UI can evolve before FourCastNet NIM integration is ready.

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
npm run web
```

For Android Emulator, keep the default API URL as `http://10.0.2.2:8000`. For iOS Simulator, use `http://127.0.0.1:8000`. For a physical phone, set `EXPO_PUBLIC_API_BASE_URL` to the LAN address of the backend machine.

## Current Scope

- Location input using latitude and longitude.
- Forecast summary cards.
- Forecast detail view with timeline steps, model metadata, and signal levels.
- Mock backend API integration.
- Backend provider status panel.
- Runtime validation for backend forecast and provider status payloads.
- Loading and error states.

## Code Layout

- `App.tsx`: Expo entry point.
- `src/screens/ForecastScreen.tsx`: top-level forecast screen composition.
- `src/hooks/useForecast.ts`: forecast state, location selection, and backend requests.
- `src/components/`: reusable forecast UI panels.
- `src/api/forecast.ts`: backend forecast API types and request helper.

