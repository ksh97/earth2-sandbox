from hashlib import sha256
from pathlib import Path

HOSTED_POINT_FIXTURE = (
    Path(__file__).parent / "fixtures" / "fourcastnet" / "hosted_point_sample.tar"
)
HOSTED_POINT_FIXTURE_SHA256 = "69be87bdd0d70f1a19c77a069fd48bc07b4a75ac16c61193cc79400be8061cd0"


def load_hosted_point_fixture() -> bytes:
    content = HOSTED_POINT_FIXTURE.read_bytes()
    assert sha256(content).hexdigest() == HOSTED_POINT_FIXTURE_SHA256
    return content
