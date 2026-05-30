from earth2_sandbox.clients.nim import FourCastNetInferenceError, FourCastNetNimClient
from earth2_sandbox.providers.base import ForecastProviderUnavailableError
from earth2_sandbox.schemas.forecast import ForecastProviderStatus, ForecastSummary
from earth2_sandbox.schemas.fourcastnet import (
    FourCastNetHostedInferenceRequest,
    FourCastNetHostedInferenceResult,
)


class FourCastNetForecastProvider:
    """FourCastNet provider boundary for readiness checks and future inference wiring."""

    def __init__(self, client: FourCastNetNimClient):
        self.client = client

    async def get_status(self) -> ForecastProviderStatus:
        status = await self.client.get_readiness_status()
        return ForecastProviderStatus(
            provider="fourcastnet",
            mode=status.mode,
            configured=status.configured,
            ready=status.ready,
            supports_point_forecast=False,
            endpoint=status.endpoint,
            detail=(
                f"{status.detail} Point forecast post-processing is not implemented yet."
            ).strip(),
        )

    async def get_point_forecast(self, latitude: float, longitude: float) -> ForecastSummary:
        status = await self.get_status()
        detail = (
            status.detail
            if status.ready
            else "FourCastNet provider is not ready. Use mock provider until NIM is configured."
        )
        raise ForecastProviderUnavailableError(detail)

    async def run_hosted_inference(
        self,
        request: FourCastNetHostedInferenceRequest,
    ) -> FourCastNetHostedInferenceResult:
        if self.client.mode != "hosted":
            raise ForecastProviderUnavailableError(
                "Hosted inference requires EARTH2_FOURCASTNET_ENDPOINT_MODE=hosted."
            )

        try:
            return await self.client.run_hosted_inference(request)
        except FourCastNetInferenceError as error:
            raise ForecastProviderUnavailableError(str(error)) from error


FourCastNetForecastService = FourCastNetForecastProvider
