import asyncio

from earth2_sandbox.services.forecast import MockForecastService


def test_mock_forecast_returns_mobile_friendly_summary() -> None:
    service = MockForecastService()

    forecast = asyncio.run(
        service.get_point_forecast(latitude=37.5665, longitude=126.9780)
    )

    assert forecast.provider == "mock"
    assert forecast.latitude == 37.5665
    assert forecast.longitude == 126.9780
    assert forecast.metrics
    assert {metric.name for metric in forecast.metrics} == {
        "temperature",
        "wind_speed",
        "humidity",
    }
