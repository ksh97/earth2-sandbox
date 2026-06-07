import asyncio
import os
from uuid import uuid4

import pytest

from earth2_sandbox.infrastructure.queue import RedisForecastQueue
from tests.forecast_queue_contract import ForecastQueueContract


def test_redis_forecast_queue_dequeues_by_priority_then_fifo() -> None:
    _run_redis_contract("test_dequeues_by_priority_then_fifo")


def test_redis_forecast_queue_deduplicates_pending_and_in_flight_jobs() -> None:
    _run_redis_contract("test_deduplicates_pending_and_in_flight_jobs")


def test_redis_forecast_queue_allows_reenqueue_after_completion() -> None:
    _run_redis_contract("test_allows_reenqueue_after_completion")


def test_redis_forecast_queue_marks_failed_items_without_requeue() -> None:
    _run_redis_contract("test_mark_failed_without_requeue_removes_in_flight_item")


def test_redis_forecast_queue_can_requeue_failed_items() -> None:
    _run_redis_contract("test_can_requeue_failed_items")


def test_redis_forecast_queue_sets_lease_on_dequeue() -> None:
    redis_url = _require_redis_url()
    queue = _build_queue(redis_url)

    async def scenario() -> int:
        try:
            await queue.enqueue(job_id="00000000-0000-0000-0000-000000000001")
            item = await queue.dequeue()
            assert item is not None
            ttl = await queue._redis.ttl(queue._lease_key(item.idempotency_key or item.job_id))
            return int(ttl)
        finally:
            await queue.clear()
            await queue.close()

    ttl = asyncio.run(scenario())

    assert 0 < ttl <= 30


def _run_redis_contract(contract_method_name: str) -> None:
    redis_url = _require_redis_url()
    _verify_redis_available(redis_url)
    contract = ForecastQueueContract(lambda: _build_queue(redis_url))

    getattr(contract, contract_method_name)()


def _build_queue(redis_url: str) -> RedisForecastQueue:
    return RedisForecastQueue(
        redis_url=redis_url,
        queue_name=f"earth2:test:{uuid4().hex}",
        visibility_timeout_seconds=30,
    )


def _require_redis_url() -> str:
    redis_url = os.environ.get("EARTH2_REDIS_TEST_URL")
    if not redis_url:
        pytest.skip("Set EARTH2_REDIS_TEST_URL to run Redis queue integration tests.")
    return redis_url


def _verify_redis_available(redis_url: str) -> None:
    queue = _build_queue(redis_url)

    async def scenario() -> None:
        try:
            await queue._redis.ping()
        except Exception as exc:
            pytest.skip(f"Redis queue integration tests require a reachable Redis server: {exc}")
        finally:
            await queue.close()

    asyncio.run(scenario())
