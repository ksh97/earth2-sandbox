import re
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from earth2_sandbox.schemas.forecast import (
    ForecastMetric,
    ForecastModelInfo,
    ForecastSignal,
    ForecastSummary,
    ForecastTimelineStep,
    ForecastWindow,
)
from earth2_sandbox.schemas.fourcastnet import (
    FourCastNetDecodedArray,
    FourCastNetDecodedTarSummary,
    FourCastNetHostedInferenceRequest,
    FourCastNetHostedInferenceResult,
    FourCastNetPostProcessingReport,
    HostedFourCastNetVariable,
)

NVIDIA_TAR_MEMBER_PATTERN = re.compile(r"^(?P<lead>\d{3})_(?P<batch>\d{3})\.npy$")
FOURCASTNET_POINT_VARIABLES: tuple[HostedFourCastNetVariable, ...] = (
    "w10m",
    "t2m",
    "msl",
    "tcwv",
    "z500",
)
REQUIRED_POINT_VARIABLES = {"w10m", "t2m", "msl", "tcwv"}
FORECAST_STEP_HOURS = 6


class FourCastNetPostProcessingError(RuntimeError):
    """Raised when FourCastNet output cannot be converted into a mobile forecast."""


@dataclass(frozen=True)
class _DecodedNumpyMember:
    filename: str
    lead_time_hours: int
    batch_index: int
    array: NDArray[np.generic]


class FourCastNetPostProcessor:
    """Describes the boundary between raw FourCastNet output and mobile summaries."""

    def describe_hosted_result(
        self,
        result: FourCastNetHostedInferenceResult,
    ) -> FourCastNetPostProcessingReport:
        detected_format = self._detect_format(result.content_type)
        required_steps = [
            "Persist raw hosted inference output outside GitHub.",
            "Map requested variables to mobile forecast fields.",
            "Sample or interpolate the global grid for the requested latitude/longitude.",
            "Compute timeline, summary metrics, confidence, and signal levels.",
            "Return the existing ForecastSummary contract to the mobile app.",
        ]

        if result.decoded_tar:
            required_steps.insert(
                1,
                "Use decoded NumPy member metadata to select lead times and batch outputs.",
            )
        else:
            required_steps.insert(1, "Decode returned tar archive and load contained NumPy arrays.")

        if detected_format == "json":
            required_steps[1] = "Inspect JSON response shape before array decoding."

        decoded_note = []
        if result.decoded_tar:
            decoded_note = [
                (
                    f"Decoded {len(result.decoded_tar.arrays)} NumPy array(s) "
                    f"across lead times {result.decoded_tar.lead_time_hours}."
                )
            ]

        return FourCastNetPostProcessingReport(
            mobile_summary_ready=False,
            detected_format=detected_format,
            required_steps=required_steps,
            notes=[
                f"Captured {result.byte_length} bytes from hosted FourCastNet.",
                f"Response digest is {result.sha256}.",
                *decoded_note,
                "Raw model output is intentionally not exposed directly to mobile clients.",
            ],
        )

    def decode_hosted_result(
        self,
        result: FourCastNetHostedInferenceResult,
    ) -> FourCastNetDecodedTarSummary | None:
        if self._detect_format(result.content_type) != "tar" or result.raw_content is None:
            return None

        return self.decode_tar_bytes(result.raw_content)

    def decode_tar_bytes(self, content: bytes) -> FourCastNetDecodedTarSummary:
        decoded_members, warnings = self._load_tar_members(content)
        arrays = [
            self._summarize_array(
                filename=member.filename,
                lead_time_hours=member.lead_time_hours,
                batch_index=member.batch_index,
                array=member.array,
            )
            for member in decoded_members
        ]

        arrays.sort(key=lambda array: (array.lead_time_hours, array.batch_index, array.filename))

        return FourCastNetDecodedTarSummary(
            member_count=len(arrays),
            arrays=arrays,
            lead_time_hours=sorted({array.lead_time_hours for array in arrays}),
            batch_indices=sorted({array.batch_index for array in arrays}),
            warnings=warnings,
        )

    def build_forecast_summary_from_hosted_result(
        self,
        *,
        result: FourCastNetHostedInferenceResult,
        request: FourCastNetHostedInferenceRequest,
        latitude: float,
        longitude: float,
        generated_at: datetime | None = None,
    ) -> ForecastSummary:
        if self._detect_format(result.content_type) != "tar":
            if result.large_asset_message:
                raise FourCastNetPostProcessingError(
                    "Hosted FourCastNet returned a large-asset marker without a tar body. "
                    "A downloadable result URL or a local sample tar is required "
                    "for point sampling."
                )
            raise FourCastNetPostProcessingError(
                f"Point forecast sampling requires tar output, got {result.content_type!r}."
            )
        if result.raw_content is None:
            raise FourCastNetPostProcessingError("Point forecast sampling requires raw tar bytes.")

        return self.build_forecast_summary_from_tar_bytes(
            content=result.raw_content,
            request=request,
            latitude=latitude,
            longitude=longitude,
            generated_at=generated_at,
        )

    def build_forecast_summary_from_tar_bytes(
        self,
        *,
        content: bytes,
        request: FourCastNetHostedInferenceRequest,
        latitude: float,
        longitude: float,
        generated_at: datetime | None = None,
    ) -> ForecastSummary:
        variables = tuple(request.variables)
        missing_variables = REQUIRED_POINT_VARIABLES.difference(variables)
        if missing_variables:
            missing = ", ".join(sorted(missing_variables))
            raise FourCastNetPostProcessingError(
                f"Point forecast sampling requires variables: {missing}."
            )

        decoded_members, warnings = self._load_tar_members(content)
        selected_members = self._select_batch_members(decoded_members)
        if not selected_members:
            raise FourCastNetPostProcessingError("No decodable FourCastNet NumPy arrays found.")

        generated_at = generated_at or datetime.now(UTC)
        timeline = [
            self._build_timeline_step(
                member=member,
                variables=variables,
                latitude=latitude,
                longitude=longitude,
                generated_at=generated_at,
                warning_count=len(warnings),
            )
            for member in selected_members
        ]

        first_step = timeline[0]
        return ForecastSummary(
            provider="fourcastnet",
            generated_at=generated_at,
            latitude=latitude,
            longitude=longitude,
            headline=self._build_headline(first_step),
            metrics=[
                ForecastMetric(
                    name="temperature",
                    value=first_step.temperature_c,
                    unit="celsius",
                ),
                ForecastMetric(
                    name="wind_speed",
                    value=first_step.wind_speed_ms,
                    unit="m/s",
                ),
                ForecastMetric(
                    name="humidity",
                    value=first_step.humidity_percent,
                    unit="percent",
                ),
            ],
            model=ForecastModelInfo(
                name="FourCastNet hosted",
                version="hosted-api",
                resolution="0.25 degree global latitude-longitude grid",
                run_mode="nim",
            ),
            forecast_window=ForecastWindow(
                start_at=timeline[0].valid_at,
                end_at=timeline[-1].valid_at,
                step_hours=FORECAST_STEP_HOURS,
                lead_hours=[step.lead_time_hours for step in timeline],
            ),
            timeline=timeline,
            signals=self._build_signals(timeline),
        )

    def _load_tar_members(self, content: bytes) -> tuple[list[_DecodedNumpyMember], list[str]]:
        decoded_members: list[_DecodedNumpyMember] = []
        warnings: list[str] = []

        try:
            with tarfile.open(fileobj=BytesIO(content), mode="r:*") as archive:
                members = [member for member in archive.getmembers() if member.isfile()]
                for member in members:
                    filename = member.name.rsplit("/", maxsplit=1)[-1]
                    match = NVIDIA_TAR_MEMBER_PATTERN.match(filename)
                    if not match:
                        warnings.append(f"Skipping unsupported tar member name: {member.name}")
                        continue

                    extracted = archive.extractfile(member)
                    if extracted is None:
                        warnings.append(f"Could not extract tar member: {member.name}")
                        continue

                    try:
                        array = np.load(BytesIO(extracted.read()), allow_pickle=False)
                    except (EOFError, OSError, ValueError) as error:
                        warnings.append(f"Could not load NumPy array from {member.name}: {error}")
                        continue

                    decoded_members.append(
                        _DecodedNumpyMember(
                            filename=filename,
                            lead_time_hours=int(match.group("lead")),
                            batch_index=int(match.group("batch")),
                            array=array,
                        )
                    )
        except tarfile.TarError as error:
            warnings.append(f"Could not decode FourCastNet tar archive: {error}")

        decoded_members.sort(
            key=lambda member: (member.lead_time_hours, member.batch_index, member.filename)
        )
        return decoded_members, warnings

    def _select_batch_members(
        self,
        members: list[_DecodedNumpyMember],
    ) -> list[_DecodedNumpyMember]:
        if not members:
            return []

        batch_index = (
            0 if any(member.batch_index == 0 for member in members) else members[0].batch_index
        )
        selected_by_lead: dict[int, _DecodedNumpyMember] = {}
        for member in members:
            if member.batch_index == batch_index and member.lead_time_hours not in selected_by_lead:
                selected_by_lead[member.lead_time_hours] = member

        return [selected_by_lead[lead] for lead in sorted(selected_by_lead)]

    def _build_timeline_step(
        self,
        *,
        member: _DecodedNumpyMember,
        variables: tuple[HostedFourCastNetVariable, ...],
        latitude: float,
        longitude: float,
        generated_at: datetime,
        warning_count: int,
    ) -> ForecastTimelineStep:
        values = self._sample_member_values(
            member.array,
            variables=variables,
            latitude=latitude,
            longitude=longitude,
        )
        temperature_c = round(self._to_celsius(values["t2m"]), 1)
        wind_speed_ms = round(max(0, values["w10m"]), 1)
        humidity_percent = round(self._tcwv_to_humidity_percent(values["tcwv"]), 1)
        pressure_hpa = round(self._to_hpa(values["msl"]), 1)
        precipitation_probability_percent = round(
            self._estimate_precipitation_probability(
                humidity_percent=humidity_percent,
                pressure_hpa=pressure_hpa,
                wind_speed_ms=wind_speed_ms,
            ),
            1,
        )
        confidence = round(
            max(0.55, min(0.95, 0.92 - member.lead_time_hours * 0.003 - warning_count * 0.03)),
            2,
        )
        condition = self._choose_condition(
            wind_speed_ms=wind_speed_ms,
            humidity_percent=humidity_percent,
            precipitation_probability_percent=precipitation_probability_percent,
        )

        return ForecastTimelineStep(
            lead_time_hours=member.lead_time_hours,
            valid_at=generated_at + timedelta(hours=member.lead_time_hours),
            temperature_c=temperature_c,
            wind_speed_ms=wind_speed_ms,
            humidity_percent=humidity_percent,
            precipitation_probability_percent=precipitation_probability_percent,
            pressure_hpa=pressure_hpa,
            confidence=confidence,
            condition=condition,
            summary=self._build_step_summary(
                condition=condition,
                temperature_c=temperature_c,
                wind_speed_ms=wind_speed_ms,
                precipitation_probability_percent=precipitation_probability_percent,
            ),
        )

    def _sample_member_values(
        self,
        array: NDArray[np.generic],
        *,
        variables: tuple[HostedFourCastNetVariable, ...],
        latitude: float,
        longitude: float,
    ) -> dict[str, float]:
        if array.ndim not in {4, 5}:
            raise FourCastNetPostProcessingError(
                f"Expected 4D or 5D FourCastNet array, got shape {array.shape}."
            )

        latitude_index, longitude_index = self._grid_indices(
            array=array,
            latitude=latitude,
            longitude=longitude,
        )
        values: dict[str, float] = {}
        for variable in REQUIRED_POINT_VARIABLES:
            variable_index = variables.index(variable)  # guarded by missing_variables check
            values[variable] = self._read_grid_value(
                array=array,
                variable_index=variable_index,
                latitude_index=latitude_index,
                longitude_index=longitude_index,
            )

        return values

    def _grid_indices(
        self,
        *,
        array: NDArray[np.generic],
        latitude: float,
        longitude: float,
    ) -> tuple[int, int]:
        latitude_count = array.shape[-2]
        longitude_count = array.shape[-1]
        if latitude_count <= 0 or longitude_count <= 0:
            raise FourCastNetPostProcessingError(f"Invalid grid shape {array.shape}.")

        latitude_step = 180 / (latitude_count - 1) if latitude_count > 1 else 180
        longitude_step = 360 / longitude_count
        latitude_index = round((90 - latitude) / latitude_step) if latitude_count > 1 else 0
        normalized_longitude = longitude % 360
        longitude_index = round(normalized_longitude / longitude_step) % longitude_count

        return (
            min(latitude_count - 1, max(0, latitude_index)),
            min(longitude_count - 1, max(0, longitude_index)),
        )

    def _read_grid_value(
        self,
        *,
        array: NDArray[np.generic],
        variable_index: int,
        latitude_index: int,
        longitude_index: int,
    ) -> float:
        variable_axis = 1 if array.ndim == 4 else 2
        if variable_index >= array.shape[variable_axis]:
            raise FourCastNetPostProcessingError(
                f"Variable index {variable_index} is outside FourCastNet array shape {array.shape}."
            )

        index = (
            (0, variable_index, latitude_index, longitude_index)
            if array.ndim == 4
            else (0, 0, variable_index, latitude_index, longitude_index)
        )
        value = float(array[index])
        if not np.isfinite(value):
            raise FourCastNetPostProcessingError(
                f"Sampled non-finite FourCastNet value at index {index}."
            )

        return value

    def _summarize_array(
        self,
        *,
        filename: str,
        lead_time_hours: int,
        batch_index: int,
        array: NDArray[np.generic],
    ) -> FourCastNetDecodedArray:
        finite_values = array[np.isfinite(array)]
        min_value = float(np.min(finite_values)) if finite_values.size else None
        max_value = float(np.max(finite_values)) if finite_values.size else None
        mean_value = float(np.mean(finite_values)) if finite_values.size else None

        return FourCastNetDecodedArray(
            filename=filename,
            lead_time_hours=lead_time_hours,
            batch_index=batch_index,
            shape=list(array.shape),
            dtype=str(array.dtype),
            finite_count=int(finite_values.size),
            min_value=min_value,
            max_value=max_value,
            mean_value=mean_value,
        )

    def _to_celsius(self, value: float) -> float:
        return value - 273.15 if value > 170 else value

    def _to_hpa(self, value: float) -> float:
        return value / 100 if value > 2000 else value

    def _tcwv_to_humidity_percent(self, value: float) -> float:
        return min(98, max(15, value * 1.5))

    def _estimate_precipitation_probability(
        self,
        *,
        humidity_percent: float,
        pressure_hpa: float,
        wind_speed_ms: float,
    ) -> float:
        pressure_signal = max(0, 1013.25 - pressure_hpa) * 1.4
        humidity_signal = max(0, humidity_percent - 45) * 0.85
        wind_signal = min(12, wind_speed_ms * 0.8)
        return min(95, max(2, humidity_signal + pressure_signal + wind_signal))

    def _choose_condition(
        self,
        *,
        wind_speed_ms: float,
        humidity_percent: float,
        precipitation_probability_percent: float,
    ) -> Literal["clear", "breezy", "humid", "rain_watch"]:
        if precipitation_probability_percent >= 45:
            return "rain_watch"
        if wind_speed_ms >= 8:
            return "breezy"
        if humidity_percent >= 74:
            return "humid"

        return "clear"

    def _build_headline(self, current_step: ForecastTimelineStep) -> str:
        if current_step.condition == "rain_watch":
            return "Rain risk proxy is elevated in the FourCastNet sample."
        if current_step.condition == "breezy":
            return "FourCastNet indicates breezy near-surface winds."
        if current_step.condition == "humid":
            return "FourCastNet moisture proxy is elevated."

        return "FourCastNet point sample is stable for this location."

    def _build_step_summary(
        self,
        *,
        condition: Literal["clear", "breezy", "humid", "rain_watch"],
        temperature_c: float,
        wind_speed_ms: float,
        precipitation_probability_percent: float,
    ) -> str:
        condition_text = {
            "clear": "Stable conditions",
            "breezy": "Breezy air flow",
            "humid": "Elevated moisture",
            "rain_watch": "Rain watch proxy",
        }[condition]
        return (
            f"{condition_text}: {temperature_c} C, wind {wind_speed_ms} m/s, "
            f"rain proxy {precipitation_probability_percent}%."
        )

    def _build_signals(self, timeline: list[ForecastTimelineStep]) -> list[ForecastSignal]:
        max_rain = max(step.precipitation_probability_percent for step in timeline)
        max_wind = max(step.wind_speed_ms for step in timeline)
        min_confidence = min(step.confidence for step in timeline)
        return [
            ForecastSignal(
                name="Precipitation",
                level="elevated" if max_rain >= 55 else "moderate" if max_rain >= 35 else "low",
                message=f"Peak FourCastNet rain proxy reaches {max_rain}%.",
            ),
            ForecastSignal(
                name="Wind",
                level="moderate" if max_wind >= 9 else "low",
                message=f"Peak sampled wind speed reaches {max_wind} m/s.",
            ),
            ForecastSignal(
                name="Model confidence",
                level="moderate" if min_confidence < 0.78 else "low",
                message=(
                    "Lowest sampling confidence across the window is "
                    f"{round(min_confidence * 100)}%."
                ),
            ),
        ]

    def _detect_format(self, content_type: str) -> str:
        normalized = content_type.lower()
        if "tar" in normalized:
            return "tar"
        if "json" in normalized:
            return "json"
        return "unknown"
