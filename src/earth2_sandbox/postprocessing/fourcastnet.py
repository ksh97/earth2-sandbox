import re
import tarfile
from io import BytesIO

import numpy as np
from numpy.typing import NDArray

from earth2_sandbox.schemas.fourcastnet import (
    FourCastNetDecodedArray,
    FourCastNetDecodedTarSummary,
    FourCastNetHostedInferenceResult,
    FourCastNetPostProcessingReport,
)

NVIDIA_TAR_MEMBER_PATTERN = re.compile(r"^(?P<lead>\d{3})_(?P<batch>\d{3})\.npy$")


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
        arrays: list[FourCastNetDecodedArray] = []
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

                    arrays.append(
                        self._summarize_array(
                            filename=filename,
                            lead_time_hours=int(match.group("lead")),
                            batch_index=int(match.group("batch")),
                            array=array,
                        )
                    )
        except tarfile.TarError as error:
            warnings.append(f"Could not decode FourCastNet tar archive: {error}")

        arrays.sort(key=lambda array: (array.lead_time_hours, array.batch_index, array.filename))

        return FourCastNetDecodedTarSummary(
            member_count=len(arrays),
            arrays=arrays,
            lead_time_hours=sorted({array.lead_time_hours for array in arrays}),
            batch_indices=sorted({array.batch_index for array in arrays}),
            warnings=warnings,
        )

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

    def _detect_format(self, content_type: str) -> str:
        normalized = content_type.lower()
        if "tar" in normalized:
            return "tar"
        if "json" in normalized:
            return "json"
        return "unknown"
