from pathlib import Path

import yaml

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2] / "contracts" / "openapi" / "earth2-api.v1.yaml"
)


def test_openapi_v1_exposes_expected_http_contracts() -> None:
    schema = _load_snapshot()

    expected_methods = {
        "/": {"get"},
        "/health": {"get"},
        "/api/v1/forecast/provider/status": {"get"},
        "/api/v1/forecast/point": {"get"},
        "/api/v1/forecast/sample": {"get"},
        "/api/v1/forecast/fourcastnet/hosted/infer": {"post"},
        "/api/v1/forecast/jobs": {"get", "post"},
        "/api/v1/forecast/jobs/cleanup": {"post"},
        "/api/v1/forecast/jobs/{job_id}": {"get"},
        "/api/v1/forecast/jobs/{job_id}/poll": {"get"},
        "/api/v1/forecast/jobs/{job_id}/cancel": {"post"},
        "/api/v1/forecast/jobs/{job_id}/retry": {"post"},
    }

    assert set(schema["paths"]) == set(expected_methods)
    for path, methods in expected_methods.items():
        assert set(schema["paths"][path]) == methods


def test_job_poll_schema_preserves_mobile_polling_fields() -> None:
    schema = _load_snapshot()
    properties = schema["components"]["schemas"]["ForecastJobPollResponse"]["properties"]

    assert {
        "id",
        "status",
        "terminal",
        "forecast_ready",
        "updated_at",
        "retry_after_seconds",
        "event_count",
        "latest_event",
        "links",
    }.issubset(properties)
    assert properties["terminal"]["type"] == "boolean"
    assert properties["forecast_ready"]["type"] == "boolean"


def _load_snapshot() -> dict:
    return yaml.safe_load(SNAPSHOT_PATH.read_text(encoding="utf-8"))

