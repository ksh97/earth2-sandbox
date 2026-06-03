from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from earth2_sandbox.observability.request_context import (
    REQUEST_ID_HEADER,
    coerce_request_id,
    reset_request_id,
    set_request_id,
)


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = coerce_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            reset_request_id(token)
