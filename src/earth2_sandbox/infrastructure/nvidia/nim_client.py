import asyncio
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
    status_url: str = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/status"
    max_poll_attempts: int = 20
    poll_interval_seconds: float = 1
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
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.post(self.base_url, json=payload, headers=headers)
                return await self._resolve_hosted_response(
                    client=client,
                    response=response,
                    request_payload=payload,
                    request_accept=request.accept,
                    headers=headers,
                )
        except httpx.HTTPError as error:
            raise FourCastNetInferenceError(
                f"Hosted FourCastNet request failed: {error}"
            ) from error

    async def _resolve_hosted_response(
        self,
        *,
        client: httpx.AsyncClient,
        response: httpx.Response,
        request_payload: dict[str, int | float | str],
        request_accept: str,
        headers: dict[str, str],
    ) -> FourCastNetHostedInferenceResult:
        request_id = self._request_id(response)
        nvcf_status = response.headers.get("nvcf-status")
        poll_attempts = 0
        response_source: Literal["inline", "poll", "redirect", "response_reference"] = "inline"

        while response.status_code == 202:
            request_id = self._request_id(response) or request_id
            nvcf_status = response.headers.get("nvcf-status") or nvcf_status
            if request_id is None:
                raise FourCastNetInferenceError(
                    "Hosted FourCastNet returned 202 without an NVCF request id."
                )
            if poll_attempts >= self.max_poll_attempts:
                raise FourCastNetInferenceError(
                    f"Hosted FourCastNet polling exceeded {self.max_poll_attempts} attempts."
                )

            if self.poll_interval_seconds > 0:
                await asyncio.sleep(self.poll_interval_seconds)

            response = await client.get(
                f"{self.status_url.rstrip('/')}/{request_id}",
                headers={
                    "Authorization": headers["Authorization"],
                    "NVCF-POLL-SECONDS": headers["NVCF-POLL-SECONDS"],
                    "accept": request_accept,
                },
            )
            poll_attempts += 1
            response_source = "poll"

        if response.status_code == 302:
            request_id = self._request_id(response) or request_id
            nvcf_status = response.headers.get("nvcf-status") or nvcf_status
            content_response = await self._download_large_response(client, response)
            return self._build_hosted_result(
                response=content_response,
                request_payload=request_payload,
                request_id=request_id,
                nvcf_status=nvcf_status,
                poll_attempts=poll_attempts,
                response_source="redirect",
                response_reference_present=True,
            )

        if not response.is_success:
            detail = self._response_error_detail(response)
            raise FourCastNetInferenceError(
                f"Hosted FourCastNet returned {response.status_code}: {detail}"
            )

        content_type = response.headers.get("content-type", "")
        json_preview = self._json_preview(response) if "application/json" in content_type else None
        response_reference = self._response_reference(json_preview)
        if response_reference:
            request_id = self._request_id(response) or request_id
            nvcf_status = response.headers.get("nvcf-status") or nvcf_status
            content_response = await self._download_url(client, response_reference)
            return self._build_hosted_result(
                response=content_response,
                request_payload=request_payload,
                request_id=request_id,
                nvcf_status=nvcf_status,
                poll_attempts=poll_attempts,
                response_source="response_reference",
                response_reference_present=True,
            )

        return self._build_hosted_result(
            response=response,
            request_payload=request_payload,
            request_id=request_id,
            nvcf_status=nvcf_status,
            poll_attempts=poll_attempts,
            response_source=response_source,
            response_reference_present=False,
            json_preview=json_preview,
        )

    async def _download_large_response(
        self,
        client: httpx.AsyncClient,
        response: httpx.Response,
    ) -> httpx.Response:
        location = response.headers.get("location")
        if not location:
            raise FourCastNetInferenceError(
                "Hosted FourCastNet returned 302 without a Location header."
            )

        return await self._download_url(client, location)

    async def _download_url(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        response = await client.get(url, follow_redirects=True)
        if not response.is_success:
            detail = self._response_error_detail(response)
            raise FourCastNetInferenceError(
                f"Hosted FourCastNet large result download returned "
                f"{response.status_code}: {detail}"
            )

        return response

    def _build_hosted_result(
        self,
        *,
        response: httpx.Response,
        request_payload: dict[str, int | float | str],
        request_id: str | None,
        nvcf_status: str | None,
        poll_attempts: int,
        response_source: Literal["inline", "poll", "redirect", "response_reference"],
        response_reference_present: bool,
        json_preview: object | None = None,
    ) -> FourCastNetHostedInferenceResult:
        content_type = response.headers.get("content-type", "")
        content = response.content
        if json_preview is None and "application/json" in content_type:
            json_preview = self._json_preview(response)
        large_asset_message = self._large_asset_message(json_preview)
        return FourCastNetHostedInferenceResult(
            endpoint=self.base_url,
            status_code=response.status_code,
            content_type=content_type,
            byte_length=len(content),
            sha256=sha256(content).hexdigest(),
            request_payload=request_payload,
            json_preview=json_preview,
            nvcf_request_id=response.headers.get("nvcf-reqid") or request_id,
            nvcf_status=response.headers.get("nvcf-status") or nvcf_status,
            large_asset_message=large_asset_message,
            poll_attempts=poll_attempts,
            response_source=response_source,
            response_reference_present=response_reference_present,
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

    def _request_id(self, response: httpx.Response) -> str | None:
        header_value = response.headers.get("nvcf-reqid")
        if header_value:
            return header_value

        preview = self._json_preview(response)
        if isinstance(preview, dict):
            for key in ("reqId", "requestId", "request_id", "id"):
                value = preview.get(key)
                if isinstance(value, str) and value:
                    return value

        return None

    def _response_reference(self, preview: object | None) -> str | None:
        if not isinstance(preview, dict):
            return None

        for key in (
            "responseReference",
            "response_reference",
            "downloadUrl",
            "download_url",
            "assetUrl",
            "asset_url",
        ):
            value = preview.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value

        return None

    def _large_asset_message(self, preview: object | None) -> str | None:
        if isinstance(preview, dict) and preview.get("message") == "Large asset written":
            return "Large asset written"

        return None

