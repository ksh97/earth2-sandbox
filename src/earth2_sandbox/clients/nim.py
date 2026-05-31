from dataclasses import dataclass
from pathlib import Path

import httpx
from pydantic import SecretStr


@dataclass(frozen=True)
class FourCastNetNimClient:
    """Small client wrapper for a self-hosted FourCastNet NIM endpoint."""

    base_url: str
    timeout_seconds: int = 300
    api_key: SecretStr | None = None

    def _headers(self, accept: str = "application/json") -> dict[str, str]:
        headers = {"accept": accept}
        if self.api_key is not None:
            headers["authorization"] = f"Bearer {self.api_key.get_secret_value()}"
        return headers

    async def is_ready(self) -> bool:
        url = f"{self.base_url.rstrip('/')}/v1/health/ready"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, headers=self._headers())
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def run_inference(
        self,
        *,
        input_array_path: Path,
        input_time: str,
        simulation_length: int,
        output_tar_path: Path,
    ) -> Path:
        url = f"{self.base_url.rstrip('/')}/v1/infer"
        timeout = httpx.Timeout(self.timeout_seconds)
        output_tar_path.parent.mkdir(parents=True, exist_ok=True)

        with input_array_path.open("rb") as input_array:
            files = {
                "input_array": (
                    input_array_path.name,
                    input_array,
                    "application/octet-stream",
                )
            }
            data = {
                "input_time": input_time,
                "simulation_length": str(simulation_length),
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=self._headers("application/x-tar"),
                    data=data,
                    files=files,
                ) as response:
                    response.raise_for_status()
                    with output_tar_path.open("wb") as output_tar:
                        async for chunk in response.aiter_bytes():
                            output_tar.write(chunk)

        return output_tar_path
