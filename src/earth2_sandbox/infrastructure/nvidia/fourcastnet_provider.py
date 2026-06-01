from earth2_sandbox.application.ports.forecast_provider import (
    ForecastProviderResult,
    ForecastProviderUnavailableError,
)
from earth2_sandbox.infrastructure.nvidia.fourcastnet_decoder import (
    FOURCASTNET_POINT_VARIABLES,
    FourCastNetPostProcessingError,
    FourCastNetPostProcessor,
)
from earth2_sandbox.infrastructure.nvidia.nim_client import (
    FourCastNetInferenceError,
    FourCastNetNimClient,
)
from earth2_sandbox.schemas.forecast import ForecastProviderStatus, ForecastSummary
from earth2_sandbox.schemas.fourcastnet import (
    FourCastNetHostedInferenceRequest,
    FourCastNetHostedInferenceResult,
)
from earth2_sandbox.storage import FourCastNetResultCache


class FourCastNetForecastProvider:
    """FourCastNet provider boundary for readiness checks and future inference wiring."""

    def __init__(
        self,
        client: FourCastNetNimClient,
        post_processor: FourCastNetPostProcessor | None = None,
        result_cache: FourCastNetResultCache | None = None,
    ):
        self.client = client
        self.post_processor = post_processor or FourCastNetPostProcessor()
        self.result_cache = result_cache

    async def get_status(self) -> ForecastProviderStatus:
        status = await self.client.get_readiness_status()
        supports_point_forecast = status.mode == "hosted" and status.ready
        detail_suffix = (
            "Hosted point forecast sampling is available."
            if supports_point_forecast
            else "Point forecast sampling requires the hosted API path and a configured API key."
        )
        return ForecastProviderStatus(
            provider="fourcastnet",
            mode=status.mode,
            configured=status.configured,
            ready=status.ready,
            supports_point_forecast=supports_point_forecast,
            endpoint=status.endpoint,
            detail=f"{status.detail} {detail_suffix}".strip(),
        )

    async def get_point_forecast(self, latitude: float, longitude: float) -> ForecastSummary:
        result = await self.get_point_forecast_with_diagnostics(
            latitude=latitude,
            longitude=longitude,
        )
        return result.summary

    async def get_point_forecast_with_diagnostics(
        self,
        latitude: float,
        longitude: float,
    ) -> ForecastProviderResult:
        status = await self.get_status()
        if not status.supports_point_forecast:
            detail = (
                status.detail
                if status.ready
                else "FourCastNet provider is not ready. Use mock provider until NIM is configured."
            )
            raise ForecastProviderUnavailableError(detail)

        request = FourCastNetHostedInferenceRequest(
            variables=list(FOURCASTNET_POINT_VARIABLES),
            simulation_length=4,
            ensemble_size=1,
            accept="application/x-tar",
        )
        try:
            result = await self._run_hosted_inference_with_cache(request)
            if result.large_asset_message:
                raise ForecastProviderUnavailableError(
                    "Hosted FourCastNet returned a large asset marker instead of tar bytes. "
                    "No downloadable responseReference or Location header was available."
                )
            summary = self.post_processor.build_forecast_summary_from_hosted_result(
                result=result,
                request=request,
                latitude=latitude,
                longitude=longitude,
            )
            return ForecastProviderResult(
                summary=summary,
                diagnostics=self._build_result_diagnostics(result),
            )
        except ForecastProviderUnavailableError:
            raise
        except (FourCastNetInferenceError, FourCastNetPostProcessingError) as error:
            raise ForecastProviderUnavailableError(str(error)) from error

    async def run_hosted_inference(
        self,
        request: FourCastNetHostedInferenceRequest,
    ) -> FourCastNetHostedInferenceResult:
        if self.client.mode != "hosted":
            raise ForecastProviderUnavailableError(
                "Hosted inference requires EARTH2_FOURCASTNET_ENDPOINT_MODE=hosted."
            )

        try:
            result = await self._run_hosted_inference_with_cache(request)
        except FourCastNetInferenceError as error:
            raise ForecastProviderUnavailableError(str(error)) from error

        decoded_tar = self.post_processor.decode_hosted_result(result)
        result_without_raw = result.model_copy(
            update={
                "decoded_tar": decoded_tar,
                "raw_content": None,
            }
        )
        return result_without_raw.model_copy(
            update={
                "post_processing": self.post_processor.describe_hosted_result(result_without_raw),
            },
        )

    async def _run_hosted_inference_with_cache(
        self,
        request: FourCastNetHostedInferenceRequest,
    ) -> FourCastNetHostedInferenceResult:
        request_payload = self.client.build_hosted_inference_payload(
            input_id=request.input_id,
            variables=request.variables,
            simulation_length=request.simulation_length,
            ensemble_size=request.ensemble_size,
            noise_amplitude=request.noise_amplitude,
        )

        if self.result_cache:
            cached = self.result_cache.load(
                request_payload=request_payload,
                accept=request.accept,
            )
            if cached:
                content, record = cached
                return FourCastNetHostedInferenceResult(
                    endpoint=self.client.base_url,
                    status_code=200,
                    content_type=record.content_type,
                    byte_length=record.byte_length,
                    sha256=record.sha256,
                    request_payload=request_payload,
                    response_source="cache",
                    cache_status="hit",
                    cached_artifact_id=record.key,
                    raw_content=content,
                )

        result = await self.client.run_hosted_inference(request)
        if not self.result_cache:
            return result.model_copy(update={"cache_status": "disabled"})

        record = self.result_cache.save(
            request_payload=request_payload,
            accept=request.accept,
            result=result,
        )
        if record:
            return result.model_copy(
                update={
                    "cache_status": "stored",
                    "cached_artifact_id": record.key,
                }
            )

        return result.model_copy(update={"cache_status": "miss"})

    def _build_result_diagnostics(
        self,
        result: FourCastNetHostedInferenceResult,
    ) -> dict[str, object]:
        return {
            "provider": "fourcastnet",
            "response_source": result.response_source,
            "cache_status": result.cache_status,
            "cached_artifact_id": result.cached_artifact_id,
            "nvcf_request_id": result.nvcf_request_id,
            "nvcf_status": result.nvcf_status,
            "poll_attempts": result.poll_attempts,
            "response_reference_present": result.response_reference_present,
            "byte_length": result.byte_length,
            "sha256": result.sha256,
        }


FourCastNetForecastService = FourCastNetForecastProvider
