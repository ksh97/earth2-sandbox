from earth2_sandbox.schemas.fourcastnet import (
    FourCastNetHostedInferenceResult,
    FourCastNetPostProcessingReport,
)


class FourCastNetPostProcessor:
    """Describes the boundary between raw FourCastNet output and mobile summaries."""

    def describe_hosted_result(
        self,
        result: FourCastNetHostedInferenceResult,
    ) -> FourCastNetPostProcessingReport:
        detected_format = self._detect_format(result.content_type)
        required_steps = [
            "Persist raw hosted inference output outside GitHub.",
            "Decode returned tar archive and load contained NumPy arrays.",
            "Map requested variables to mobile forecast fields.",
            "Sample or interpolate the global grid for the requested latitude/longitude.",
            "Compute timeline, summary metrics, confidence, and signal levels.",
            "Return the existing ForecastSummary contract to the mobile app.",
        ]

        if detected_format == "json":
            required_steps[1] = "Inspect JSON response shape before array decoding."

        return FourCastNetPostProcessingReport(
            mobile_summary_ready=False,
            detected_format=detected_format,
            required_steps=required_steps,
            notes=[
                f"Captured {result.byte_length} bytes from hosted FourCastNet.",
                f"Response digest is {result.sha256}.",
                "Raw model output is intentionally not exposed directly to mobile clients.",
            ],
        )

    def _detect_format(self, content_type: str) -> str:
        normalized = content_type.lower()
        if "tar" in normalized:
            return "tar"
        if "json" in normalized:
            return "json"
        return "unknown"
