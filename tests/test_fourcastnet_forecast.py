import asyncio
import io
import struct
import tarfile
from pathlib import Path

from earth2_sandbox.services.fourcastnet import (
    FOURCASTNET_VARIABLES,
    FourCastNetForecastService,
    FourCastNetOutputArchive,
)


class FakeFourCastNetClient:
    def __init__(self, archive_bytes: bytes, ready: bool = True) -> None:
        self.archive_bytes = archive_bytes
        self.ready = ready

    async def is_ready(self) -> bool:
        return self.ready

    async def run_inference(
        self,
        *,
        input_array_path: Path,
        input_time: str,
        simulation_length: int,
        output_tar_path: Path,
    ) -> Path:
        output_tar_path.parent.mkdir(parents=True, exist_ok=True)
        output_tar_path.write_bytes(self.archive_bytes)
        return output_tar_path


def test_fourcastnet_archive_extracts_point_summary(tmp_path: Path) -> None:
    archive_path = tmp_path / "output.tar"
    archive_path.write_bytes(_forecast_archive_bytes())

    point = FourCastNetOutputArchive(archive_path).extract_point(
        latitude=0,
        longitude=90,
        preferred_lead_hours=6,
    )

    assert point.lead_hours == 6
    assert point.temperature_c == 16.9
    assert point.wind_speed_ms == 5.0
    assert point.mean_sea_level_pressure_hpa == 1013.2
    assert point.total_column_water_vapor_kg_m2 == 20.0


def test_fourcastnet_service_returns_mobile_friendly_forecast(tmp_path: Path) -> None:
    input_path = tmp_path / "fcn_inputs.npy"
    input_path.write_bytes(b"placeholder")
    service = FourCastNetForecastService(
        client=FakeFourCastNetClient(_forecast_archive_bytes()),
        input_array_path=input_path,
        input_time="2023-01-01T00:00:00Z",
        simulation_length=1,
        summary_lead_hours=6,
        output_dir=tmp_path,
    )

    forecast = asyncio.run(service.get_point_forecast(latitude=0, longitude=90))

    assert forecast.provider == "fourcastnet"
    assert forecast.lead_hours == 6
    assert forecast.source_time == "2023-01-01T00:00:00Z"
    assert {metric.name for metric in forecast.metrics} == {
        "temperature",
        "wind_speed",
        "mean_sea_level_pressure",
        "total_column_water_vapor",
    }


def _forecast_archive_bytes() -> bytes:
    shape = (1, 1, len(FOURCASTNET_VARIABLES), 3, 4)
    values = [0.0] * _product(shape)
    lat_index = 1
    lon_index = 1
    _set_value(values, shape, "u10m", lat_index, lon_index, 3.0)
    _set_value(values, shape, "v10m", lat_index, lon_index, 4.0)
    _set_value(values, shape, "t2m", lat_index, lon_index, 290.0)
    _set_value(values, shape, "msl", lat_index, lon_index, 101325.0)
    _set_value(values, shape, "tcwv", lat_index, lon_index, 20.0)

    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        npy_data = _npy_bytes(values, shape)
        info = tarfile.TarInfo("006_000.npy")
        info.size = len(npy_data)
        archive.addfile(info, io.BytesIO(npy_data))
    return output.getvalue()


def _npy_bytes(values: list[float], shape: tuple[int, ...]) -> bytes:
    header = repr({"descr": "<f4", "fortran_order": False, "shape": shape})
    padding = 16 - ((10 + len(header) + 1) % 16)
    header = header + (" " * padding) + "\n"

    output = io.BytesIO()
    output.write(b"\x93NUMPY\x01\x00")
    output.write(struct.pack("<H", len(header)))
    output.write(header.encode("latin1"))
    output.write(struct.pack(f"<{len(values)}f", *values))
    return output.getvalue()


def _set_value(
    values: list[float],
    shape: tuple[int, ...],
    variable: str,
    lat_index: int,
    lon_index: int,
    value: float,
) -> None:
    variable_index = FOURCASTNET_VARIABLES.index(variable)
    flat_index = ((variable_index * shape[-2]) + lat_index) * shape[-1] + lon_index
    values[flat_index] = value


def _product(shape: tuple[int, ...]) -> int:
    product = 1
    for dimension in shape:
        product *= dimension
    return product
