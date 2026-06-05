from fastapi.testclient import TestClient

from earth2_sandbox.app import create_app
from earth2_sandbox.config import Settings


def test_api_key_guard_blocks_protected_forecast_endpoint() -> None:
    client = _client(api_key_required=True, api_key="test-key")

    response = client.get(
        "/api/v1/forecast/point",
        params={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing or invalid API key."}


def test_api_key_guard_allows_valid_key() -> None:
    client = _client(api_key_required=True, api_key="test-key")

    response = client.get(
        "/api/v1/forecast/point",
        headers={"X-API-Key": "test-key"},
        params={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "mock"


def test_api_key_guard_allows_configured_key_list() -> None:
    client = _client(api_key_required=True, api_keys="first-key, second-key")

    response = client.post(
        "/api/v1/forecast/jobs",
        headers={"X-API-Key": "second-key"},
        json={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"


def test_api_key_guard_leaves_health_metrics_and_docs_public() -> None:
    client = _client(api_key_required=True, api_key="test-key")

    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_rate_limiter_blocks_expensive_endpoint_after_capacity() -> None:
    client = _client(
        rate_limit_enabled=True,
        rate_limit_capacity=1,
        rate_limit_window_seconds=60,
    )
    params = {"latitude": 37.5665, "longitude": 126.9780}

    first = client.get("/api/v1/forecast/point", params=params)
    second = client.get("/api/v1/forecast/point", params=params)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json() == {"detail": "Rate limit exceeded."}
    assert int(second.headers["retry-after"]) > 0


def test_rate_limiter_does_not_limit_public_health_endpoint() -> None:
    client = _client(
        rate_limit_enabled=True,
        rate_limit_capacity=1,
        rate_limit_window_seconds=60,
    )

    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200


def test_rate_limiter_uses_api_key_identity_when_available() -> None:
    client = _client(
        api_key_required=True,
        api_keys="first-key,second-key",
        rate_limit_enabled=True,
        rate_limit_capacity=1,
        rate_limit_window_seconds=60,
    )
    params = {"latitude": 37.5665, "longitude": 126.9780}

    first = client.get(
        "/api/v1/forecast/point",
        headers={"X-API-Key": "first-key"},
        params=params,
    )
    second = client.get(
        "/api/v1/forecast/point",
        headers={"X-API-Key": "second-key"},
        params=params,
    )

    assert first.status_code == 200
    assert second.status_code == 200


def _client(**settings_overrides) -> TestClient:
    settings = Settings(
        forecast_provider="mock",
        fourcastnet_endpoint_mode="self_hosted",
        nvidia_api_key=None,
        **settings_overrides,
    )
    return TestClient(create_app(settings=settings))
