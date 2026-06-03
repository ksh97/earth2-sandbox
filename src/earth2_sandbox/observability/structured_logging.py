from __future__ import annotations

import json
import logging
from typing import Any

from earth2_sandbox.observability.request_context import get_request_id

LOGGER_NAME = "earth2_sandbox"


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    request_id = get_request_id()
    if request_id is not None and "request_id" not in payload:
        payload["request_id"] = request_id

    logging.getLogger(LOGGER_NAME).info(
        json.dumps(payload, default=str, sort_keys=True, separators=(",", ":"))
    )

