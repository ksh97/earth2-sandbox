from __future__ import annotations

from uuid import uuid4


class UuidIdGenerator:
    """UUID4 id generator adapter for job identities."""

    def new_id(self) -> str:
        return str(uuid4())
