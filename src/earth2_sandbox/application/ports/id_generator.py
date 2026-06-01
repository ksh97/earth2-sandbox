from __future__ import annotations

from typing import Protocol


class IdGenerator(Protocol):
    """Application-facing source of unique identifiers."""

    def new_id(self) -> str: ...
