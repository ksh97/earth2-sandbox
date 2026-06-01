from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from earth2_sandbox.application.ports.artifact_store import ArtifactRecord, ArtifactStore
from earth2_sandbox.application.ports.clock import Clock
from earth2_sandbox.infrastructure.storage.local_artifact_store import LocalArtifactStore
from earth2_sandbox.schemas.fourcastnet import FourCastNetHostedInferenceResult


@dataclass(frozen=True)
class FourCastNetCacheRecord:
    key: str
    path: Path
    metadata_path: Path
    byte_length: int
    sha256: str
    content_type: str
    created_at: str


class FourCastNetResultCache:
    """Filesystem cache for hosted FourCastNet tar responses.

    The cache key is derived from the sanitized inference payload and requested
    content type. API keys, headers, and presigned download URLs are never stored.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        clock: Clock | None = None,
        artifact_store: ArtifactStore | None = None,
    ):
        self.root = Path(root)
        self.artifact_store = artifact_store or LocalArtifactStore(
            self.root,
            clock=clock,
            content_suffix=".tar",
        )

    def load(
        self,
        *,
        request_payload: dict[str, int | float | str],
        accept: str,
    ) -> tuple[bytes, FourCastNetCacheRecord] | None:
        key = self._key(request_payload=request_payload, accept=accept)
        loaded = self.artifact_store.load(key=key)
        if loaded is None:
            return None

        content, record = loaded
        return (content, self._cache_record_from_artifact(record))

    def save(
        self,
        *,
        request_payload: dict[str, int | float | str],
        accept: str,
        result: FourCastNetHostedInferenceResult,
    ) -> FourCastNetCacheRecord | None:
        if result.raw_content is None or "tar" not in result.content_type.lower():
            return None

        key = self._key(request_payload=request_payload, accept=accept)
        record = self.artifact_store.save(
            key=key,
            content=result.raw_content,
            content_type=result.content_type,
            metadata={
                "request_payload": request_payload,
                "source": result.response_source,
                "nvcf_request_id": result.nvcf_request_id,
                "nvcf_status": result.nvcf_status,
            },
        )
        return self._cache_record_from_artifact(record)

    def _cache_record_from_artifact(self, record: ArtifactRecord) -> FourCastNetCacheRecord:
        return FourCastNetCacheRecord(
            key=record.key,
            path=self._content_path(record.key),
            metadata_path=self._metadata_path(record.key),
            byte_length=record.byte_length,
            sha256=record.sha256,
            content_type=record.content_type,
            created_at=record.created_at,
        )

    def _content_path(self, key: str) -> Path:
        content_path = getattr(self.artifact_store, "content_path", None)
        if callable(content_path):
            return Path(content_path(key))
        return self.root / f"{key}.tar"

    def _metadata_path(self, key: str) -> Path:
        metadata_path = getattr(self.artifact_store, "metadata_path", None)
        if callable(metadata_path):
            return Path(metadata_path(key))
        return self.root / f"{key}.json"

    def _key(self, *, request_payload: dict[str, int | float | str], accept: str) -> str:
        key_payload = {
            "accept": accept,
            "request_payload": request_payload,
        }
        serialized = json.dumps(key_payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return sha256(serialized).hexdigest()
