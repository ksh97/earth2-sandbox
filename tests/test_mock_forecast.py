import asyncio

from earth2_sandbox.providers.mock import MockForecastProvider


def test_mock_forecast_returns_mobile_friendly_summary() -> None:
    service = MockForecastProvider()

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
    assert forecast.model.name == "FourCastNet-compatible mock"
    assert forecast.forecast_window.lead_hours == [0, 6, 12, 24, 36, 48, 72]
    assert len(forecast.timeline) == 7
    assert forecast.timeline[0].lead_time_hours == 0
    assert forecast.timeline[-1].lead_time_hours == 72
    assert forecast.signals
