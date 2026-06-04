from __future__ import annotations

from fastapi import APIRouter, Response

from earth2_sandbox.observability.metrics import render_prometheus

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def create_metrics_router() -> APIRouter:
    router = APIRouter()

    @router.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(
            content=render_prometheus(),
            media_type=PROMETHEUS_CONTENT_TYPE,
        )

    return router
