from __future__ import annotations

import json
import re
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path

from earth2_sandbox.application.ports.artifact_store import ArtifactRecord
from earth2_sandbox.application.ports.clock import Clock
from earth2_sandbox.infrastructure.runtime import SystemClock

_SAFE_ARTIFACT_KEY = re.compile(r"^[A-Za-z0-9._-]+$")


class LocalArtifactStore:
    """Local filesystem artifact adapter with digest-checked metadata."""

    def __init__(
        self,
        root: str | Path,
        *,
        clock: Clock | None = None,
        content_suffix: str = ".artifact",
    ) -> None:
        self.root = Path(root)
        self.clock = clock or SystemClock()
        self.content_suffix = content_suffix

    def load(self, *, key: str) -> tuple[bytes, ArtifactRecord] | None:
        content_path = self.content_path(key)
        metadata_path = self.metadata_path(key)
        if not content_path.exists() or not metadata_path.exists():
            return None

        content = content_path.read_bytes()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest = sha256(content).hexdigest()
        if metadata.get("sha256") != digest:
            return None

        return (
            content,
            ArtifactRecord(
                key=key,
                byte_length=len(content),
                sha256=digest,
                content_type=str(metadata.get("content_type") or "application/octet-stream"),
                created_at=str(metadata.get("created_at") or ""),
                metadata=metadata,
            ),
        )

    def save(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str,
        metadata: Mapping[str, object] | None = None,
    ) -> ArtifactRecord:
        self.root.mkdir(parents=True, exist_ok=True)
        digest = sha256(content).hexdigest()
        created_at = self.clock.now().isoformat()
        document: dict[str, object] = {
            "key": key,
            "created_at": created_at,
            "content_type": content_type,
            "byte_length": len(content),
            "sha256": digest,
            **dict(metadata or {}),
        }

        self.content_path(key).write_bytes(content)
        self.metadata_path(key).write_text(
            json.dumps(
                document,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return ArtifactRecord(
            key=key,
            byte_length=len(content),
            sha256=digest,
            content_type=content_type,
            created_at=created_at,
            metadata=document,
        )

    def content_path(self, key: str) -> Path:
        return self._safe_path(key=key, suffix=self.content_suffix)

    def metadata_path(self, key: str) -> Path:
        return self._safe_path(key=key, suffix=".json")

    def _safe_path(self, *, key: str, suffix: str) -> Path:
        if not _SAFE_ARTIFACT_KEY.fullmatch(key):
            raise ValueError("Artifact key must be path-safe.")

        root = self.root.resolve()
        target = (root / f"{key}{suffix}").resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError("Artifact key resolved outside artifact root.") from error
        return target
