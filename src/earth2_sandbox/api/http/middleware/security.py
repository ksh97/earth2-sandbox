from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import ceil
from threading import Lock
from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from earth2_sandbox.bootstrap.settings import Settings

API_KEY_HEADER = "X-API-Key"
PUBLIC_PATHS = frozenset({"/", "/health", "/metrics", "/openapi.json", "/favicon.ico"})
PUBLIC_PATH_PREFIXES = ("/docs", "/redoc")


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int


class InMemoryFixedWindowRateLimiter:
    def __init__(self, *, capacity: int, window_seconds: int) -> None:
        self.capacity = capacity
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._windows: dict[tuple[str, str], tuple[float, int]] = {}

    def check(self, *, identity: str, route: str) -> RateLimitDecision:
        now = monotonic()
        key = (identity, route)
        with self._lock:
            window_start, count = self._windows.get(key, (now, 0))
            elapsed = now - window_start
            if elapsed >= self.window_seconds:
                self._windows[key] = (now, 1)
                return RateLimitDecision(allowed=True, retry_after_seconds=0)

            if count >= self.capacity:
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=max(1, ceil(self.window_seconds - elapsed)),
                )

            self._windows[key] = (window_start, count + 1)
            return RateLimitDecision(allowed=True, retry_after_seconds=0)


class ApiAccessControlMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, settings: Settings) -> None:
        super().__init__(app)
        self.api_key_required = settings.api_key_required
        self.api_keys = _configured_api_keys(settings)
        self.rate_limit_enabled = settings.rate_limit_enabled
        self.rate_limit_routes = _parse_route_specs(settings.rate_limit_routes)
        self.rate_limiter = InMemoryFixedWindowRateLimiter(
            capacity=settings.rate_limit_capacity,
            window_seconds=settings.rate_limit_window_seconds,
        )

    async def dispatch(self, request: Request, call_next):
        if _is_public_request(request):
            return await call_next(request)

        api_key = request.headers.get(API_KEY_HEADER, "").strip()
        if self.api_key_required and api_key not in self.api_keys:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid API key."},
            )

        route = _route_spec(request)
        if self.rate_limit_enabled and route in self.rate_limit_routes:
            decision = self.rate_limiter.check(
                identity=_rate_limit_identity(request, api_key),
                route=route,
            )
            if not decision.allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded."},
                    headers={"Retry-After": str(decision.retry_after_seconds)},
                )

        return await call_next(request)


def _configured_api_keys(settings: Settings) -> frozenset[str]:
    values: list[str] = []
    if settings.api_key is not None:
        values.append(settings.api_key.get_secret_value())
    if settings.api_keys is not None:
        values.extend(settings.api_keys.get_secret_value().split(","))
    return frozenset(value.strip() for value in values if value.strip())


def _is_public_request(request: Request) -> bool:
    path = request.url.path
    return (
        request.method == "OPTIONS"
        or path in PUBLIC_PATHS
        or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)
    )


def _parse_route_specs(value: str) -> frozenset[str]:
    return frozenset(route.strip() for route in value.split(",") if route.strip())


def _route_spec(request: Request) -> str:
    return f"{request.method.upper()} {request.url.path}"


def _rate_limit_identity(request: Request, api_key: str) -> str:
    if api_key:
        digest = sha256(api_key.encode("utf-8")).hexdigest()
        return f"api-key:{digest}"

    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',', maxsplit=1)[0].strip()}"

    client = request.client
    return f"ip:{client.host if client else 'unknown'}"
