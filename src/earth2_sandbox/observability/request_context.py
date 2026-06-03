from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import uuid4

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[str | None] = ContextVar("earth2_request_id", default=None)


def coerce_request_id(value: str | None) -> str:
    candidate = (value or "").strip()
    return candidate or str(uuid4())


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(request_id: str) -> Token[str | None]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)

