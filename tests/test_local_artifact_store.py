from datetime import UTC, datetime
from hashlib import sha256

import pytest

from earth2_sandbox.infrastructure.storage import LocalArtifactStore

FIXED_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return FIXED_NOW


def test_local_artifact_store_round_trips_content_and_metadata(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path, clock=FixedClock(), content_suffix=".tar")
    content = b"forecast tar bytes"

    saved = store.save(
        key="abc123",
        content=content,
        content_type="application/x-tar",
        metadata={"source": "fixture"},
    )
    loaded = store.load(key="abc123")

    assert saved.created_at == FIXED_NOW.isoformat()
    assert saved.sha256 == sha256(content).hexdigest()
    assert loaded is not None
    loaded_content, loaded_record = loaded
    assert loaded_content == content
    assert loaded_record.content_type == "application/x-tar"
    assert loaded_record.metadata["source"] == "fixture"


def test_local_artifact_store_rejects_digest_mismatch(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path, clock=FixedClock(), content_suffix=".tar")
    store.save(
        key="abc123",
        content=b"original",
        content_type="application/x-tar",
    )
    store.content_path("abc123").write_bytes(b"tampered")

    assert store.load(key="abc123") is None


def test_local_artifact_store_rejects_unsafe_keys(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path, clock=FixedClock())

    with pytest.raises(ValueError):
        store.save(
            key="../outside",
            content=b"bad",
            content_type="application/octet-stream",
        )
