from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

import httpx

from earth2_sandbox.schemas.fourcastnet import (
    FourCastNetHostedInferenceRequest,
    FourCastNetHostedInferenceResult,
)

FourCastNetEndpointMode = Literal["self_hosted", "hosted"]


@dataclass(frozen=True)
class FourCastNetNimStatus:
    mode: FourCastNetEndpointMode
    endpoint: str
    ready: bool
    configured: bool
    status_code: int | None = None
    detail: str = ""


class FourCastNetInferenceError(RuntimeError):
    """Raised when a FourCastNet inference request cannot be completed."""


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
        variables: tuple[str, ...] | list[str] = ("t2m", "w10m", "msl", "tcwv", "z500"),
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

    async def run_hosted_inference(
        self,
        request: FourCastNetHostedInferenceRequest,
    ) -> FourCastNetHostedInferenceResult:
        if self.mode != "hosted":
            raise FourCastNetInferenceError(
                "Hosted inference requires fourcastnet_endpoint_mode='hosted'."
            )
        if not self.api_key:
            raise FourCastNetInferenceError("Hosted FourCastNet API key is missing.")

        payload = self.build_hosted_inference_payload(
            input_id=request.input_id,
            variables=request.variables,
            simulation_length=request.simulation_length,
            ensemble_size=request.ensemble_size,
            noise_amplitude=request.noise_amplitude,
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "NVCF-POLL-SECONDS": str(request.poll_seconds),
            "accept": request.accept,
            "content-type": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(self.base_url, json=payload, headers=headers)
        except httpx.HTTPError as error:
            raise FourCastNetInferenceError(
                f"Hosted FourCastNet request failed: {error}"
            ) from error

        if not response.is_success:
            detail = self._response_error_detail(response)
            raise FourCastNetInferenceError(
                f"Hosted FourCastNet returned {response.status_code}: {detail}"
            )

        content_type = response.headers.get("content-type", "")
        content = response.content
        json_preview = self._json_preview(response) if "application/json" in content_type else None
        large_asset_message = self._large_asset_message(json_preview)
        return FourCastNetHostedInferenceResult(
            endpoint=self.base_url,
            status_code=response.status_code,
            content_type=content_type,
            byte_length=len(content),
            sha256=sha256(content).hexdigest(),
            request_payload=payload,
            json_preview=json_preview,
            nvcf_request_id=response.headers.get("nvcf-reqid"),
            nvcf_status=response.headers.get("nvcf-status"),
            large_asset_message=large_asset_message,
            raw_content=content,
        )

    def _response_error_detail(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:500] if response.text else "No response body."

        if isinstance(payload, dict) and "detail" in payload:
            return str(payload["detail"])

        return str(payload)[:500]

    def _json_preview(self, response: httpx.Response) -> object | None:
        try:
            return response.json()
        except ValueError:
            return None

    def _large_asset_message(self, preview: object | None) -> str | None:
        if isinstance(preview, dict) and preview.get("message") == "Large asset written":
            return "Large asset written"

        return None

