from dataclasses import dataclass
from typing import Literal

import httpx

FourCastNetEndpointMode = Literal["self_hosted", "hosted"]


@dataclass(frozen=True)
class FourCastNetNimStatus:
    mode: FourCastNetEndpointMode
    endpoint: str
    ready: bool
    configured: bool
    status_code: int | None = None
    detail: str = ""


@dataclass(frozen=True)
class FourCastNetNimClient:
    """Small client wrapper for self-hosted or hosted FourCastNet endpoints."""

    base_url: str
    timeout_seconds: int = 300
    mode: FourCastNetEndpointMode = "self_hosted"
    api_key: str | None = None
    transport: httpx.AsyncBaseTransport | None = None

    async def is_ready(self) -> bool:
        status = await self.get_readiness_status()
        return status.ready

    async def get_readiness_status(self) -> FourCastNetNimStatus:
        if self.mode == "hosted":
            configured = bool(self.api_key)
            return FourCastNetNimStatus(
                mode=self.mode,
                endpoint=self.base_url,
                ready=configured,
                configured=configured,
                detail=(
                    "Hosted FourCastNet API key is configured."
                    if configured
                    else "Hosted FourCastNet API key is missing."
                ),
            )

        url = f"{self.base_url.rstrip('/')}/v1/health/ready"
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(url, headers={"accept": "application/json"})
            return FourCastNetNimStatus(
                mode=self.mode,
                endpoint=url,
                ready=response.status_code == 200,
                configured=True,
                status_code=response.status_code,
                detail=(
                    "Self-hosted FourCastNet NIM is ready."
                    if response.status_code == 200
                    else f"Self-hosted FourCastNet NIM returned {response.status_code}."
                ),
            )
        except httpx.HTTPError as error:
            return FourCastNetNimStatus(
                mode=self.mode,
                endpoint=url,
                ready=False,
                configured=True,
                detail=f"Self-hosted FourCastNet NIM readiness check failed: {error}",
            )

    def build_hosted_inference_payload(
        self,
        *,
        variables: tuple[str, ...] = ("t2m", "w10m", "msl", "tcwv", "z500"),
        simulation_length: int = 4,
        ensemble_size: int = 1,
        noise_amplitude: float = 0,
        input_id: int = 0,
    ) -> dict[str, int | float | str]:
        return {
            "input_id": input_id,
            "variables": ",".join(variables),
            "simulation_length": simulation_length,
            "ensemble_size": ensemble_size,
            "noise_amplitude": noise_amplitude,
        }

