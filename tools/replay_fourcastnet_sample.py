from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from earth2_sandbox.infrastructure.nvidia import (
    FOURCASTNET_POINT_VARIABLES,
    FourCastNetPostProcessor,
)
from earth2_sandbox.schemas.fourcastnet import FourCastNetHostedInferenceRequest

SEOUL_LATITUDE = 37.5665
SEOUL_LONGITUDE = 126.9780


def main() -> int:
    tar_path = _resolve_tar_path()
    if tar_path is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "No sample tar found. Pass a path or run hosted smoke first.",
                    "searched": ["data/samples/*.tar", "data/cache/fourcastnet/*.tar"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    processor = FourCastNetPostProcessor()
    request = FourCastNetHostedInferenceRequest(
        variables=list(FOURCASTNET_POINT_VARIABLES),
        simulation_length=1,
        ensemble_size=1,
        noise_amplitude=0,
        accept="application/x-tar",
    )
    content = tar_path.read_bytes()
    decoded = processor.decode_tar_bytes(content)
    forecast = processor.build_forecast_summary_from_tar_bytes(
        content=content,
        request=request,
        latitude=SEOUL_LATITUDE,
        longitude=SEOUL_LONGITUDE,
        generated_at=datetime.now(UTC),
    )

    print(
        json.dumps(
            {
                "ok": True,
                "sample_tar": str(tar_path),
                "byte_length": len(content),
                "decoded_member_count": decoded.member_count,
                "decoded_lead_hours": decoded.lead_time_hours,
                "decoded_batch_indices": decoded.batch_indices,
                "forecast_provider": forecast.provider,
                "forecast_lead_hours": forecast.forecast_window.lead_hours,
                "first_step": forecast.timeline[0].model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _resolve_tar_path() -> Path | None:
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1])
        return candidate if candidate.exists() else None

    candidates = [
        *Path("data/samples").glob("*.tar"),
        *Path("data/cache/fourcastnet").glob("*.tar"),
    ]
    if not candidates:
        return None

    return max(candidates, key=lambda path: path.stat().st_mtime)


if __name__ == "__main__":
    sys.exit(main())
