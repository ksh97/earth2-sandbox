from pathlib import Path

import yaml

from earth2_sandbox.app import create_app
from earth2_sandbox.config import Settings

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2] / "contracts" / "openapi" / "earth2-api.v1.yaml"
)


def test_openapi_snapshot_matches_current_v1_contract() -> None:
    app = create_app(
        settings=Settings(
            forecast_provider="mock",
            fourcastnet_endpoint_mode="self_hosted",
            nvidia_api_key=None,
        )
    )

    expected = yaml.safe_load(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert app.openapi() == expected

