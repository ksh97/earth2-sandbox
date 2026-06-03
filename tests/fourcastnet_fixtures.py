import json
from hashlib import sha256
from pathlib import Path

FOURCASTNET_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "fourcastnet"
HOSTED_POINT_FIXTURE = FOURCASTNET_FIXTURE_DIR / "hosted_point_sample.tar"
HOSTED_POINT_FIXTURE_SHA256 = "69be87bdd0d70f1a19c77a069fd48bc07b4a75ac16c61193cc79400be8061cd0"
HOSTED_POINT_EXPECTED_METADATA = FOURCASTNET_FIXTURE_DIR / "expected_metadata.json"


def load_hosted_point_fixture() -> bytes:
    content = HOSTED_POINT_FIXTURE.read_bytes()
    assert sha256(content).hexdigest() == HOSTED_POINT_FIXTURE_SHA256
    return content


def load_expected_hosted_metadata() -> dict[str, object]:
    return _load_fixture_json(HOSTED_POINT_EXPECTED_METADATA)


def load_expected_point_forecast(city: str) -> dict[str, object]:
    return _load_fixture_json(FOURCASTNET_FIXTURE_DIR / f"expected_point_forecast_{city}.json")


def _load_fixture_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)

    assert isinstance(payload, dict)
    return payload
