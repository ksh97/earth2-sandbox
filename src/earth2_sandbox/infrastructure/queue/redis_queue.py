from __future__ import annotations

import inspect
import json
from typing import Any, cast

from earth2_sandbox.application.ports.forecast_queue import (
    ForecastQueueEnqueueResult,
    ForecastQueueItem,
)
from earth2_sandbox.domain.jobs.priority import (
    DEFAULT_FORECAST_JOB_PRIORITY,
    ForecastJobPriority,
    priority_rank,
)

_SCORE_FACTOR = 1_000_000_000_000

_ENQUEUE_SCRIPT = """
local pending_hash = KEYS[1]
local in_flight_hash = KEYS[2]
local pending_zset = KEYS[3]
local key = ARGV[1]
local payload = ARGV[2]
local score = ARGV[3]

local existing = redis.call("HGET", pending_hash, key)
if existing then
  return {0, existing}
end

existing = redis.call("HGET", in_flight_hash, key)
if existing then
  return {0, existing}
end

redis.call("HSET", pending_hash, key, payload)
redis.call("ZADD", pending_zset, score, key)
return {1, payload}
"""

_DEQUEUE_SCRIPT = """
local pending_hash = KEYS[1]
local in_flight_hash = KEYS[2]
local pending_zset = KEYS[3]

local keys = redis.call("ZRANGE", pending_zset, 0, 0)
local key = keys[1]
if not key then
  return nil
end

local payload = redis.call("HGET", pending_hash, key)
redis.call("ZREM", pending_zset, key)
redis.call("HDEL", pending_hash, key)

if payload then
  redis.call("HSET", in_flight_hash, key, payload)
end

return payload
"""


class RedisForecastQueue:
    """Redis-backed ForecastQueue adapter.

    The adapter stores pending jobs in a sorted set for priority/FIFO ordering
    and keeps pending/in-flight payloads in hashes for idempotency checks.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        queue_name: str,
        visibility_timeout_seconds: int,
        redis_client: Any | None = None,
    ) -> None:
        self._redis = redis_client or _build_redis_client(redis_url)
        self._queue_name = _normalize_queue_name(queue_name)
        self._visibility_timeout_seconds = visibility_timeout_seconds

    async def enqueue(
        self,
        *,
        job_id: str,
        priority: ForecastJobPriority = DEFAULT_FORECAST_JOB_PRIORITY,
        idempotency_key: str | None = None,
    ) -> ForecastQueueEnqueueResult:
        key = _queue_key(job_id=job_id, idempotency_key=idempotency_key)
        sequence = await self._redis.incr(self._sequence_key)
        item = ForecastQueueItem(
            job_id=job_id,
            priority=priority,
            idempotency_key=key,
        )
        payload = _encode_item(item)
        score = priority_rank(priority) * _SCORE_FACTOR + int(sequence)
        result = await self._redis.eval(
            _ENQUEUE_SCRIPT,
            3,
            self._pending_hash_key,
            self._in_flight_hash_key,
            self._pending_zset_key,
            key,
            payload,
            str(score),
        )
        enqueued, returned_payload = result
        returned_item = _decode_item(returned_payload)
        if returned_item is None:
            returned_item = item
        return ForecastQueueEnqueueResult(
            item=returned_item,
            enqueued=bool(int(enqueued)),
        )

    async def dequeue(self) -> ForecastQueueItem | None:
        payload = await self._redis.eval(
            _DEQUEUE_SCRIPT,
            3,
            self._pending_hash_key,
            self._in_flight_hash_key,
            self._pending_zset_key,
        )
        item = _decode_item(payload)
        if item is None:
            return None

        await self._redis.set(
            self._lease_key(_item_key(item)),
            item.job_id,
            ex=self._visibility_timeout_seconds,
        )
        return item

    async def mark_completed(self, item: ForecastQueueItem) -> None:
        key = _item_key(item)
        pipe = self._redis.pipeline(transaction=True)
        pipe.hdel(self._in_flight_hash_key, key)
        pipe.delete(self._lease_key(key))
        await pipe.execute()

    async def mark_failed(
        self,
        item: ForecastQueueItem,
        *,
        requeue: bool = False,
    ) -> None:
        key = _item_key(item)
        pipe = self._redis.pipeline(transaction=True)
        pipe.hdel(self._in_flight_hash_key, key)
        pipe.delete(self._lease_key(key))
        await pipe.execute()

        if requeue:
            await self.enqueue(
                job_id=item.job_id,
                priority=item.priority,
                idempotency_key=item.idempotency_key,
            )

    async def pending_count(self) -> int:
        return int(await self._redis.hlen(self._pending_hash_key))

    async def in_flight_count(self) -> int:
        return int(await self._redis.hlen(self._in_flight_hash_key))

    async def clear(self) -> None:
        keys = [
            self._pending_hash_key,
            self._in_flight_hash_key,
            self._pending_zset_key,
            self._sequence_key,
        ]
        async for key in self._redis.scan_iter(match=f"{self._queue_name}:lease:*"):
            keys.append(key)
        await self._redis.delete(*keys)

    async def close(self) -> None:
        close = getattr(self._redis, "aclose", None) or getattr(self._redis, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    @property
    def _pending_hash_key(self) -> str:
        return f"{self._queue_name}:pending"

    @property
    def _in_flight_hash_key(self) -> str:
        return f"{self._queue_name}:in-flight"

    @property
    def _pending_zset_key(self) -> str:
        return f"{self._queue_name}:pending:score"

    @property
    def _sequence_key(self) -> str:
        return f"{self._queue_name}:sequence"

    def _lease_key(self, key: str) -> str:
        return f"{self._queue_name}:lease:{key}"


def _build_redis_client(redis_url: str) -> Any:
    try:
        from redis.asyncio import Redis
    except ImportError as exc:
        msg = (
            "Redis queue backend requires the redis package. Install the "
            "project dependencies before selecting EARTH2_FORECAST_QUEUE_BACKEND=redis."
        )
        raise RuntimeError(msg) from exc

    return Redis.from_url(redis_url, decode_responses=True)


def _encode_item(item: ForecastQueueItem) -> str:
    return json.dumps(
        {
            "job_id": item.job_id,
            "priority": item.priority,
            "idempotency_key": item.idempotency_key,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _decode_item(payload: Any) -> ForecastQueueItem | None:
    if payload is None:
        return None
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    data = json.loads(cast(str, payload))
    priority = data.get("priority", DEFAULT_FORECAST_JOB_PRIORITY)
    if priority not in {"low", "normal", "high"}:
        priority = DEFAULT_FORECAST_JOB_PRIORITY
    return ForecastQueueItem(
        job_id=data["job_id"],
        priority=cast(ForecastJobPriority, priority),
        idempotency_key=data.get("idempotency_key"),
    )


def _queue_key(*, job_id: str, idempotency_key: str | None) -> str:
    return idempotency_key or job_id


def _item_key(item: ForecastQueueItem) -> str:
    return item.idempotency_key or item.job_id


def _normalize_queue_name(queue_name: str) -> str:
    return queue_name.strip().rstrip(":")
