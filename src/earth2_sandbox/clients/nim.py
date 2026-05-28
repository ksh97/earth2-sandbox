from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class FourCastNetNimClient:
    """Small client wrapper for a self-hosted FourCastNet NIM endpoint."""

    base_url: str
    timeout_seconds: int = 300

    async def is_ready(self) -> bool:
        url = f"{self.base_url.rstrip('/')}/v1/health/ready"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, headers={"accept": "application/json"})
            return response.status_code == 200
        except httpx.HTTPError:
            return False

