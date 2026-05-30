# Roadmap

## Phase 0: Project Foundation

- Create a clean Python backend package.
- Add FastAPI health and mock forecast endpoints.
- Document the high-level architecture.
- Keep secrets and large data out of GitHub.

## Phase 1: API Contract

- Decide the first user story: "Show a simple forecast for my selected location."
- Add request/response schemas.
- Add a stable mock forecast provider.
- Add tests for API responses.

## Phase 2: Mobile Prototype

- Use React Native/Expo for the first iOS and Android prototype.
- Build one screen:
  - Location input
  - Forecast summary
  - Simple chart
- Connect it to the backend mock API.

## Phase 3: FourCastNet Integration

- Add a backend forecast provider boundary for mock vs. FourCastNet modes.
- Run or access FourCastNet NIM.
- Add NIM readiness checks.
- Implement an inference request path.
- Store raw output outside GitHub.
- Convert outputs into mobile-friendly summaries.

## Phase 4: Productization

- Add authentication and basic abuse protection.
- Add caching.
- Add observability and error reporting.
- Add privacy policy and terms links.
- Prepare App Store and Google Play metadata.

## Phase 5: Launch

- Create production backend environment.
- Submit iOS build to App Store Connect.
- Submit Android build to Google Play Console.
- Monitor crashes, latency, and forecast errors.
