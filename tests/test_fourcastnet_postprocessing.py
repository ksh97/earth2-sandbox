import tarfile
from datetime import UTC, datetime
from io import BytesIO

import numpy as np
import pytest

from earth2_sandbox.infrastructure.nvidia import (
    FourCastNetPostProcessingError,
    FourCastNetPostProcessor,
)
from earth2_sandbox.schemas.fourcastnet import (
    FourCastNetHostedInferenceRequest,
    FourCastNetHostedInferenceResult,
)
from tests.fourcastnet_fixtures import (
    HOSTED_POINT_FIXTURE_SHA256,
    load_expected_hosted_metadata,
    load_expected_point_forecast,
    load_hosted_point_fixture,
)


def test_fourcastnet_tar_decoder_reads_nvidia_naming_convention() -> None:
    processor = FourCastNetPostProcessor()
    content = build_tar_bytes(
        {
            "000_000.npy": np.array([[[[1.0, 2.0], [3.0, 4.0]]]], dtype=np.float32),
            "006_000.npy": np.array([[[[5.0, 6.0], [7.0, 8.0]]]], dtype=np.float32),
            "012_000.npy": b"not a numpy array",
            "notes.txt": b"ignored",
        }
    )

    summary = processor.decode_tar_bytes(content)

    assert summary.member_count == 2
    assert summary.lead_time_hours == [0, 6]
    assert summary.batch_indices == [0]
    assert summary.warnings[0].startswith("Could not load NumPy array from 012_000.npy")
    assert summary.warnings[1] == "Skipping unsupported tar member name: notes.txt"
    assert summary.arrays[0].filename == "000_000.npy"
    assert summary.arrays[0].shape == [1, 1, 2, 2]
    assert summary.arrays[0].dtype == "float32"
    assert summary.arrays[0].finite_count == 4
    assert summary.arrays[0].min_value == 1.0
    assert summary.arrays[0].max_value == 4.0
    assert summary.arrays[0].mean_value == 2.5


def test_fourcastnet_tar_sampler_builds_forecast_summary_from_4d_arrays() -> None:
    processor = FourCastNetPostProcessor()
    request = FourCastNetHostedInferenceRequest(
        variables=["w10m", "t2m", "msl", "tcwv", "z500"],
        simulation_length=1,
    )
    content = build_tar_bytes(
        {
            "000_000.npy": build_sample_array(
                wind_speed_ms=8,
                temperature_k=293.15,
                pressure_pa=101000,
                tcwv=40,
            ),
            "006_000.npy": build_sample_array(
                wind_speed_ms=10,
                temperature_k=294.15,
                pressure_pa=100800,
                tcwv=42,
            ),
        }
    )

    forecast = processor.build_forecast_summary_from_tar_bytes(
        content=content,
        request=request,
        latitude=0,
        longitude=90,
        generated_at=datetime(2026, 5, 31, 0, 0, tzinfo=UTC),
    )

    assert forecast.provider == "fourcastnet"
    assert forecast.model.run_mode == "nim"
    assert forecast.forecast_window.lead_hours == [0, 6]
    assert forecast.timeline[0].temperature_c == 20.0
    assert forecast.timeline[0].wind_speed_ms == 8.0
    assert forecast.timeline[0].pressure_hpa == 1010.0
    assert forecast.timeline[0].humidity_percent == 60.0
    assert forecast.timeline[0].condition == "breezy"
    assert forecast.timeline[1].temperature_c == 21.0


def test_fourcastnet_tar_sampler_accepts_5d_self_hosted_shape() -> None:
    processor = FourCastNetPostProcessor()
    request = FourCastNetHostedInferenceRequest(
        variables=["w10m", "t2m", "msl", "tcwv", "z500"],
        simulation_length=1,
    )
    content = build_tar_bytes(
        {
            "000_000.npy": build_sample_array(
                wind_speed_ms=6,
                temperature_k=291.15,
                pressure_pa=101325,
                tcwv=35,
            )[np.newaxis, ...],
        }
    )

    forecast = processor.build_forecast_summary_from_tar_bytes(
        content=content,
        request=request,
        latitude=0,
        longitude=90,
        generated_at=datetime(2026, 5, 31, 0, 0, tzinfo=UTC),
    )

    assert forecast.timeline[0].temperature_c == 18.0
    assert forecast.timeline[0].pressure_hpa == 1013.2


def test_fourcastnet_hosted_fixture_decodes_and_samples_forecast_summary() -> None:
    processor = FourCastNetPostProcessor()
    content = load_hosted_point_fixture()
    request = FourCastNetHostedInferenceRequest(
        variables=["w10m", "t2m", "msl", "tcwv", "z500"],
        simulation_length=4,
    )
    result = FourCastNetHostedInferenceResult(
        endpoint="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
        status_code=200,
        content_type="application/x-tar",
        byte_length=len(content),
        sha256=HOSTED_POINT_FIXTURE_SHA256,
        request_payload={
            "input_id": 0,
            "variables": "w10m,t2m,msl,tcwv,z500",
            "simulation_length": 4,
            "ensemble_size": 1,
            "noise_amplitude": 0,
        },
        nvcf_request_id="fixture-request-id",
        nvcf_status="fulfilled",
        poll_attempts=2,
        response_source="response_reference",
        response_reference_present=True,
        raw_content=content,
    )

    decoded_tar = processor.decode_hosted_result(result)
    assert decoded_tar is not None
    assert decoded_tar.model_dump(mode="json") == load_expected_hosted_metadata()

    described = processor.describe_hosted_result(
        result.model_copy(update={"decoded_tar": decoded_tar})
    )
    assert described.detected_format == "tar"
    assert described.mobile_summary_ready is False
    assert "Decoded 3 NumPy array(s) across lead times [0, 6, 12]." in described.notes

    locations = (
        ("seoul", 37.5665, 126.9780),
        ("tokyo", 35.6762, 139.6503),
    )
    for city, latitude, longitude in locations:
        forecast = processor.build_forecast_summary_from_hosted_result(
            result=result,
            request=request,
            latitude=latitude,
            longitude=longitude,
            generated_at=datetime(2026, 5, 31, 0, 0, tzinfo=UTC),
        )

        assert forecast.model_dump(mode="json") == load_expected_point_forecast(city)


def test_fourcastnet_tar_sampler_uses_nearest_grid_and_unit_conversions() -> None:
    processor = FourCastNetPostProcessor()
    request = FourCastNetHostedInferenceRequest(
        variables=["w10m", "t2m", "msl", "tcwv", "z500"],
        simulation_length=1,
    )
    array = np.zeros((1, 5, 5, 8), dtype=np.float32)
    latitude_index = 1
    longitude_index = 3
    array[0, 0, latitude_index, longitude_index] = 12.3
    array[0, 1, latitude_index, longitude_index] = 300.15
    array[0, 2, latitude_index, longitude_index] = 100050
    array[0, 3, latitude_index, longitude_index] = 50
    array[0, 4, latitude_index, longitude_index] = 5600

    forecast = processor.build_forecast_summary_from_tar_bytes(
        content=build_tar_bytes({"000_000.npy": array}),
        request=request,
        latitude=37.5665,
        longitude=126.9780,
        generated_at=datetime(2026, 5, 31, 0, 0, tzinfo=UTC),
    )

    step = forecast.timeline[0]
    assert step.temperature_c == 27.0
    assert step.wind_speed_ms == 12.3
    assert step.pressure_hpa == 1000.5
    assert step.humidity_percent == 75.0
    assert step.precipitation_probability_percent == 53.2
    assert step.condition == "rain_watch"


def test_fourcastnet_tar_sampler_requires_all_point_variables() -> None:
    processor = FourCastNetPostProcessor()
    request = FourCastNetHostedInferenceRequest(
        variables=["w10m", "t2m", "msl"],
        simulation_length=1,
    )
    content = build_tar_bytes(
        {
            "000_000.npy": build_sample_array(
                wind_speed_ms=8,
                temperature_k=293.15,
                pressure_pa=101000,
                tcwv=40,
            ),
        }
    )

    with pytest.raises(FourCastNetPostProcessingError, match="tcwv"):
        processor.build_forecast_summary_from_tar_bytes(
            content=content,
            request=request,
            latitude=0,
            longitude=90,
            generated_at=datetime(2026, 5, 31, 0, 0, tzinfo=UTC),
        )


def test_fourcastnet_tar_sampler_rejects_non_finite_sampled_values() -> None:
    processor = FourCastNetPostProcessor()
    request = FourCastNetHostedInferenceRequest(
        variables=["w10m", "t2m", "msl", "tcwv", "z500"],
        simulation_length=1,
    )
    array = build_sample_array(
        wind_speed_ms=8,
        temperature_k=293.15,
        pressure_pa=101000,
        tcwv=40,
    )
    array[0, 1, 1, 1] = np.inf

    with pytest.raises(FourCastNetPostProcessingError, match="Sampled non-finite"):
        processor.build_forecast_summary_from_tar_bytes(
            content=build_tar_bytes({"000_000.npy": array}),
            request=request,
            latitude=0,
            longitude=90,
            generated_at=datetime(2026, 5, 31, 0, 0, tzinfo=UTC),
        )


def build_tar_bytes(entries: dict[str, np.ndarray | bytes]) -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for filename, payload in entries.items():
            if isinstance(payload, np.ndarray):
                payload_buffer = BytesIO()
                np.save(payload_buffer, payload)
                data = payload_buffer.getvalue()
            else:
                data = payload

            info = tarfile.TarInfo(filename)
            info.size = len(data)
            archive.addfile(info, BytesIO(data))

    return buffer.getvalue()


def build_sample_array(
    *,
    wind_speed_ms: float,
    temperature_k: float,
    pressure_pa: float,
    tcwv: float,
) -> np.ndarray:
    array = np.zeros((1, 5, 3, 4), dtype=np.float32)
    latitude_index = 1
    longitude_index = 1
    array[0, 0, latitude_index, longitude_index] = wind_speed_ms
    array[0, 1, latitude_index, longitude_index] = temperature_k
    array[0, 2, latitude_index, longitude_index] = pressure_pa
    array[0, 3, latitude_index, longitude_index] = tcwv
    array[0, 4, latitude_index, longitude_index] = 5500
    return array
