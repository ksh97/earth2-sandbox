from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from earth2_sandbox.clients.nim import FourCastNetNimClient
from earth2_sandbox.config import Settings
from earth2_sandbox.postprocessing import FOURCASTNET_POINT_VARIABLES, FourCastNetPostProcessor
from earth2_sandbox.schemas.fourcastnet import FourCastNetHostedInferenceRequest

SEOUL_LATITUDE = 37.5665
SEOUL_LONGITUDE = 126.9780


async def main() -> None:
    settings = Settings()
    if settings.nvidia_api_key is None:
        raise SystemExit("NVIDIA_API_KEY_CONFIGURED=false")

    client = FourCastNetNimClient(
        base_url=settings.fourcastnet_hosted_url,
        mode="hosted",
        api_key=settings.nvidia_api_key.get_secret_value(),
        timeout_seconds=settings.request_timeout_seconds,
    )
    request = FourCastNetHostedInferenceRequest(
        variables=list(FOURCASTNET_POINT_VARIABLES),
        simulation_length=1,
        ensemble_size=1,
        noise_amplitude=0,
        accept="application/x-tar",
        poll_seconds=10,
    )

    result = await client.run_hosted_inference(request)
    processor = FourCastNetPostProcessor()
    decoded = processor.decode_hosted_result(result)
    if decoded is None:
        preview = result.json_preview
        preview_summary = preview
        if isinstance(preview, dict):
            preview_summary = {
                key: value
                for key, value in preview.items()
                if key.lower() not in {"token", "authorization", "api_key", "apiKey"}
            }
        print(
            json.dumps(
                {
                    "status_code": result.status_code,
                    "content_type": result.content_type,
                    "byte_length": result.byte_length,
                    "sha256_prefix": result.sha256[:12],
                    "nvcf_request_id": result.nvcf_request_id,
                    "nvcf_status": result.nvcf_status,
                    "large_asset_message": result.large_asset_message,
                    "decoded_member_count": 0,
                    "json_preview": preview_summary,
                    "note": "Expected application/x-tar, but NVIDIA returned JSON.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    forecast = processor.build_forecast_summary_from_hosted_result(
        result=result,
        request=request,
        latitude=SEOUL_LATITUDE,
        longitude=SEOUL_LONGITUDE,
        generated_at=datetime.now(UTC),
    )

    samples_dir = Path("data") / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    tar_path = samples_dir / f"fourcastnet_hosted_{stamp}.tar"
    tar_path.write_bytes(result.raw_content or b"")

    print(
        json.dumps(
            {
                "status_code": result.status_code,
                "content_type": result.content_type,
                "byte_length": result.byte_length,
                "sha256_prefix": result.sha256[:12],
                "saved_tar": str(tar_path),
                "decoded_member_count": decoded.member_count if decoded else 0,
                "decoded_lead_hours": decoded.lead_time_hours if decoded else [],
                "decoded_batch_indices": decoded.batch_indices if decoded else [],
                "forecast_provider": forecast.provider,
                "forecast_lead_hours": forecast.forecast_window.lead_hours,
                "first_step": forecast.timeline[0].model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
