from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    key: str
    byte_length: int
    sha256: str
    content_type: str
    created_at: str
    metadata: Mapping[str, object]


class ArtifactStore(Protocol):
    """Storage boundary for generated or downloaded forecast artifacts."""

    def load(self, *, key: str) -> tuple[bytes, ArtifactRecord] | None: ...

    def save(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str,
        metadata: Mapping[str, object] | None = None,
    ) -> ArtifactRecord: ...
