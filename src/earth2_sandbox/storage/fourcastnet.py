from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

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

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def load(
        self,
        *,
        request_payload: dict[str, int | float | str],
        accept: str,
    ) -> tuple[bytes, FourCastNetCacheRecord] | None:
        key = self._key(request_payload=request_payload, accept=accept)
        tar_path = self.root / f"{key}.tar"
        metadata_path = self.root / f"{key}.json"
        if not tar_path.exists() or not metadata_path.exists():
            return None

        content = tar_path.read_bytes()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest = sha256(content).hexdigest()
        if metadata.get("sha256") != digest:
            return None

        return (
            content,
            FourCastNetCacheRecord(
                key=key,
                path=tar_path,
                metadata_path=metadata_path,
                byte_length=len(content),
                sha256=digest,
                content_type=str(metadata.get("content_type") or "application/x-tar"),
                created_at=str(metadata.get("created_at") or ""),
            ),
        )

    def save(
        self,
        *,
        request_payload: dict[str, int | float | str],
        accept: str,
        result: FourCastNetHostedInferenceResult,
    ) -> FourCastNetCacheRecord | None:
        if result.raw_content is None or "tar" not in result.content_type.lower():
            return None

        self.root.mkdir(parents=True, exist_ok=True)
        key = self._key(request_payload=request_payload, accept=accept)
        tar_path = self.root / f"{key}.tar"
        metadata_path = self.root / f"{key}.json"
        content = result.raw_content
        digest = sha256(content).hexdigest()
        created_at = datetime.now(UTC).isoformat()

        tar_path.write_bytes(content)
        metadata_path.write_text(
            json.dumps(
                {
                    "key": key,
                    "created_at": created_at,
                    "content_type": result.content_type,
                    "byte_length": len(content),
                    "sha256": digest,
                    "request_payload": request_payload,
                    "source": result.response_source,
                    "nvcf_request_id": result.nvcf_request_id,
                    "nvcf_status": result.nvcf_status,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        return FourCastNetCacheRecord(
            key=key,
            path=tar_path,
            metadata_path=metadata_path,
            byte_length=len(content),
            sha256=digest,
            content_type=result.content_type,
            created_at=created_at,
        )

    def _key(self, *, request_payload: dict[str, int | float | str], accept: str) -> str:
        key_payload = {
            "accept": accept,
            "request_payload": request_payload,
        }
        serialized = json.dumps(key_payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return sha256(serialized).hexdigest()
