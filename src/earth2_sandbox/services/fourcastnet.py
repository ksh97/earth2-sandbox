from __future__ import annotations

import ast
import math
import struct
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BufferedIOBase
from pathlib import Path
from typing import Protocol

from earth2_sandbox.clients.nim import FourCastNetNimClient
from earth2_sandbox.config import Settings
from earth2_sandbox.services.forecast import (
    ForecastMetric,
    ForecastProviderUnavailable,
    ForecastSummary,
)

FOURCASTNET_VARIABLES = [
    "u10m",
    "v10m",
    "u100m",
    "v100m",
    "t2m",
    "msl",
    "tcwv",
    "u50",
    "u100",
    "u150",
    "u200",
    "u250",
    "u300",
    "u400",
    "u500",
    "u600",
    "u700",
    "u850",
    "u925",
    "u1000",
    "v50",
    "v100",
    "v150",
    "v200",
    "v250",
    "v300",
    "v400",
    "v500",
    "v600",
    "v700",
    "v850",
    "v925",
    "v1000",
    "z50",
    "z100",
    "z150",
    "z200",
    "z250",
    "z300",
    "z400",
    "z500",
    "z600",
    "z700",
    "z850",
    "z925",
    "z1000",
    "t50",
    "t100",
    "t150",
    "t200",
    "t250",
    "t300",
    "t400",
    "t500",
    "t600",
    "t700",
    "t850",
    "t925",
    "t1000",
    "q50",
    "q100",
    "q150",
    "q200",
    "q250",
    "q300",
    "q400",
    "q500",
    "q600",
    "q700",
    "q850",
    "q925",
    "q1000",
]


class FourCastNetClient(Protocol):
    async def is_ready(self) -> bool: ...

    async def run_inference(
        self,
        *,
        input_array_path: Path,
        input_time: str,
        simulation_length: int,
        output_tar_path: Path,
    ) -> Path: ...


@dataclass(frozen=True)
class FourCastNetPoint:
    temperature_c: float
    wind_speed_ms: float
    mean_sea_level_pressure_hpa: float
    total_column_water_vapor_kg_m2: float
    lead_hours: int


class NpyScalarReader:
    """Read selected scalar values from a C-order NumPy .npy array."""

    def __init__(self, file_obj: BufferedIOBase) -> None:
        self._file_obj = file_obj
        self.shape, self.dtype, self.data_offset = self._read_header()
        if len(self.shape) < 3:
            raise ValueError(
                f"Expected at least 3 dimensions in FourCastNet output, got {self.shape}"
            )

    def read(self, indexes: tuple[int, ...]) -> float:
        if len(indexes) != len(self.shape):
            raise ValueError(f"Index rank {len(indexes)} does not match array shape {self.shape}")

        flat_index = 0
        stride = 1
        for index, size in zip(reversed(indexes), reversed(self.shape), strict=True):
            if index < 0 or index >= size:
                raise IndexError(f"Index {indexes} is outside array shape {self.shape}")
            flat_index += index * stride
            stride *= size

        dtype_format, dtype_size = _dtype_format(self.dtype)
        self._file_obj.seek(self.data_offset + flat_index * dtype_size)
        raw = self._file_obj.read(dtype_size)
        if len(raw) != dtype_size:
            raise ValueError("Unexpected end of .npy data")
        return float(struct.unpack(dtype_format, raw)[0])

    def _read_header(self) -> tuple[tuple[int, ...], str, int]:
        magic = self._file_obj.read(6)
        if magic != b"\x93NUMPY":
            raise ValueError("Response member is not a NumPy .npy file")

        version = self._file_obj.read(2)
        if version == b"\x01\x00":
            header_length = struct.unpack("<H", self._file_obj.read(2))[0]
        elif version in {b"\x02\x00", b"\x03\x00"}:
            header_length = struct.unpack("<I", self._file_obj.read(4))[0]
        else:
            raise ValueError(f"Unsupported .npy version {version!r}")

        header = ast.literal_eval(self._file_obj.read(header_length).decode("latin1"))
        if header.get("fortran_order"):
            raise ValueError("Fortran-order .npy arrays are not supported")

        shape = tuple(int(dimension) for dimension in header["shape"])
        dtype = str(header["descr"])
        return shape, dtype, self._file_obj.tell()


class FourCastNetOutputArchive:
    def __init__(self, archive_path: Path) -> None:
        self.archive_path = archive_path

    def extract_point(
        self,
        *,
        latitude: float,
        longitude: float,
        preferred_lead_hours: int,
    ) -> FourCastNetPoint:
        with tarfile.open(self.archive_path, "r") as archive:
            member, lead_hours = self._select_member(archive, preferred_lead_hours)
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ForecastProviderUnavailable(f"Could not read {member.name} from NIM output")

            reader = NpyScalarReader(extracted)
            lat_index = _latitude_index(latitude, reader.shape[-2])
            lon_index = _longitude_index(longitude, reader.shape[-1])
            values = {
                variable: reader.read(
                    (0, 0, FOURCASTNET_VARIABLES.index(variable), lat_index, lon_index)
                )
                for variable in ("u10m", "v10m", "t2m", "msl", "tcwv")
            }

        return FourCastNetPoint(
            temperature_c=round(_kelvin_to_celsius_if_needed(values["t2m"]), 1),
            wind_speed_ms=round(math.hypot(values["u10m"], values["v10m"]), 1),
            mean_sea_level_pressure_hpa=round(values["msl"] / 100, 1),
            total_column_water_vapor_kg_m2=round(values["tcwv"], 1),
            lead_hours=lead_hours,
        )

    def _select_member(
        self,
        archive: tarfile.TarFile,
        preferred_lead_hours: int,
    ) -> tuple[tarfile.TarInfo, int]:
        candidates: list[tuple[int, tarfile.TarInfo]] = []
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith(".npy"):
                continue

            try:
                lead_text, batch_text = Path(member.name).stem.split("_", maxsplit=1)
                lead_hours = int(lead_text)
                batch_index = int(batch_text)
            except ValueError:
                continue

            if batch_index == 0:
                candidates.append((lead_hours, member))

        if not candidates:
            raise ForecastProviderUnavailable(
                "FourCastNet NIM response did not contain forecast arrays"
            )

        for lead_hours, member in candidates:
            if lead_hours == preferred_lead_hours:
                return member, lead_hours

        return max(candidates, key=lambda candidate: candidate[0])


class FourCastNetForecastService:
    def __init__(
        self,
        *,
        client: FourCastNetClient,
        input_array_path: Path,
        input_time: str,
        simulation_length: int,
        summary_lead_hours: int,
        output_dir: Path,
    ) -> None:
        self.client = client
        self.input_array_path = input_array_path
        self.input_time = input_time
        self.simulation_length = simulation_length
        self.summary_lead_hours = summary_lead_hours
        self.output_dir = output_dir

    @classmethod
    def from_settings(cls, settings: Settings) -> FourCastNetForecastService:
        if settings.fourcastnet_input_array_path is None:
            raise ForecastProviderUnavailable(
                "EARTH2_FOURCASTNET_INPUT_ARRAY_PATH must point to fcn_inputs.npy "
                "when mock forecasts are disabled"
            )

        return cls(
            client=FourCastNetNimClient(
                base_url=settings.nim_base_url,
                timeout_seconds=settings.request_timeout_seconds,
                api_key=settings.nvidia_api_key,
            ),
            input_array_path=Path(settings.fourcastnet_input_array_path),
            input_time=settings.fourcastnet_input_time,
            simulation_length=settings.fourcastnet_simulation_length,
            summary_lead_hours=settings.fourcastnet_summary_lead_hours,
            output_dir=Path(settings.output_dir),
        )

    async def get_point_forecast(self, latitude: float, longitude: float) -> ForecastSummary:
        if not self.input_array_path.exists():
            raise ForecastProviderUnavailable(
                f"FourCastNet input array not found: {self.input_array_path}"
            )

        if not await self.client.is_ready():
            raise ForecastProviderUnavailable("FourCastNet NIM is not ready")

        output_tar_path = self._next_output_path()
        await self.client.run_inference(
            input_array_path=self.input_array_path,
            input_time=self.input_time,
            simulation_length=self.simulation_length,
            output_tar_path=output_tar_path,
        )
        point = FourCastNetOutputArchive(output_tar_path).extract_point(
            latitude=latitude,
            longitude=longitude,
            preferred_lead_hours=self.summary_lead_hours,
        )

        return ForecastSummary(
            provider="fourcastnet",
            generated_at=datetime.now(UTC),
            latitude=latitude,
            longitude=longitude,
            source_time=self.input_time,
            lead_hours=point.lead_hours,
            headline=f"FourCastNet forecast for +{point.lead_hours}h lead time",
            metrics=[
                ForecastMetric(name="temperature", value=point.temperature_c, unit="celsius"),
                ForecastMetric(name="wind_speed", value=point.wind_speed_ms, unit="m/s"),
                ForecastMetric(
                    name="mean_sea_level_pressure",
                    value=point.mean_sea_level_pressure_hpa,
                    unit="hPa",
                ),
                ForecastMetric(
                    name="total_column_water_vapor",
                    value=point.total_column_water_vapor_kg_m2,
                    unit="kg/m^2",
                ),
            ],
        )

    def _next_output_path(self) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return self.output_dir / "fourcastnet" / f"forecast-{timestamp}.tar"


def _dtype_format(dtype: str) -> tuple[str, int]:
    if dtype in {"<f4", "|f4"}:
        return "<f", 4
    if dtype == ">f4":
        return ">f", 4
    if dtype in {"<f8", "|f8"}:
        return "<d", 8
    if dtype == ">f8":
        return ">d", 8
    raise ValueError(f"Unsupported .npy dtype {dtype}")


def _latitude_index(latitude: float, latitude_count: int) -> int:
    if latitude_count <= 1:
        return 0
    step = 180 / (latitude_count - 1)
    return max(0, min(latitude_count - 1, round((90 - latitude) / step)))


def _longitude_index(longitude: float, longitude_count: int) -> int:
    if longitude_count <= 1:
        return 0
    normalized = longitude % 360
    step = 360 / longitude_count
    return round(normalized / step) % longitude_count


def _kelvin_to_celsius_if_needed(value: float) -> float:
    if value > 150:
        return value - 273.15
    return value
