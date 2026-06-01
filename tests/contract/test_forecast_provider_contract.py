import asyncio

import httpx

from earth2_sandbox.application.ports.forecast_provider import ForecastProvider
from earth2_sandbox.clients.nim import FourCastNetNimClient
from earth2_sandbox.providers import FourCastNetForecastProvider, MockForecastProvider
from earth2_sandbox.schemas.forecast import ForecastSummary
from earth2_sandbox.schemas.fourcastnet import (
    FourCastNetHostedInferenceRequest,
    FourCastNetHostedInferenceResult,
)
from earth2_sandbox.storage import FourCastNetResultCache
from tests.fourcastnet_fixtures import (
    HOSTED_POINT_FIXTURE_SHA256,
    load_hosted_point_fixture,
)


def test_mock_provider_satisfies_forecast_provider_contract() -> None:
    provider: ForecastProvider = MockForecastProvider()

    status = asyncio.run(provider.get_status())
    forecast = asyncio.run(provider.get_point_forecast(latitude=37.5665, longitude=126.978))

    assert status.ready is True
    assert status.supports_point_forecast is True
    _assert_forecast_summary_contract(forecast, provider_name="mock")


def test_cached_fourcastnet_provider_satisfies_forecast_provider_contract(tmp_path) -> None:
    content = load_hosted_point_fixture()
    request = FourCastNetHostedInferenceRequest()

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Cache hit should avoid hosted request: {request.url}")

    client = FourCastNetNimClient(
        base_url="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
        mode="hosted",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    request_payload = client.build_hosted_inference_payload(
        input_id=request.input_id,
        variables=request.variables,
        simulation_length=request.simulation_length,
        ensemble_size=request.ensemble_size,
        noise_amplitude=request.noise_amplitude,
    )
    cache = FourCastNetResultCache(tmp_path)
    cache.save(
        request_payload=request_payload,
        accept=request.accept,
        result=FourCastNetHostedInferenceResult(
            endpoint=client.base_url,
            status_code=200,
            content_type="application/x-tar",
            byte_length=len(content),
            sha256=HOSTED_POINT_FIXTURE_SHA256,
            request_payload=request_payload,
            response_source="response_reference",
            response_reference_present=True,
            nvcf_request_id="fixture-request-id",
            nvcf_status="fulfilled",
            raw_content=content,
        ),
    )
    provider: ForecastProvider = FourCastNetForecastProvider(client=client, result_cache=cache)

    status = asyncio.run(provider.get_status())
    forecast = asyncio.run(provider.get_point_forecast(latitude=0, longitude=90))

    assert status.ready is True
    assert status.supports_point_forecast is True
    _assert_forecast_summary_contract(forecast, provider_name="fourcastnet")


def _assert_forecast_summary_contract(
    forecast: ForecastSummary,
    *,
    provider_name: str,
) -> None:
    assert forecast.provider == provider_name
    assert -90 <= forecast.latitude <= 90
    assert -180 <= forecast.longitude <= 180
    assert forecast.headline
    assert forecast.generated_at is not None
    assert forecast.metrics
    assert {metric.name for metric in forecast.metrics} >= {"temperature", "wind_speed"}
    assert forecast.model.name
    assert forecast.model.run_mode
    assert forecast.forecast_window.lead_hours
    assert forecast.timeline
    assert forecast.timeline[0].valid_at is not None
    assert forecast.signals

