"""Redis Streams event bus for cross-process job progress streaming.

publish_event() XADD's events from the worker process.
iter_events() XREAD's them from the API process (WS relay).
Late subscribers replay from id "0" — no subscribe-before-publish race.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import redis.asyncio as aioredis

from app.config import settings

STREAM_MAXLEN = 1000
STREAM_TTL_SECONDS = 3600

_client: aioredis.Redis | None = None


def _stream_key(job_id: str) -> str:
    return f"job:{job_id}:events"


def _get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def publish_event(job_id: str, event: dict[str, Any]) -> None:
    """Append an event to the job's Redis Stream (XADD)."""
    event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    key = _stream_key(job_id)
    r = _get_redis()
    await r.xadd(key, {"data": json.dumps(event)}, maxlen=STREAM_MAXLEN)
    await r.expire(key, STREAM_TTL_SECONDS)


async def iter_events(
    job_id: str, timeout_ms: int = 5000,
) -> AsyncIterator[dict[str, Any] | None]:
    """Yield events from the job's Redis Stream via XREAD BLOCK.

    Starts from id "0-0" so late-connecting clients replay the full
    history.  Yields ``None`` after *timeout_ms* of inactivity (caller
    should send a WS heartbeat).  Returns on terminal events
    (``run_finished`` / ``run_error``).
    """
    key = _stream_key(job_id)
    last_id = "0-0"
    r = _get_redis()
    while True:
        entries = await r.xread({key: last_id}, block=timeout_ms, count=100)
        if not entries:
            yield None
            continue
        for _stream_name, messages in entries:
            for msg_id, fields in messages:
                last_id = msg_id
                event = json.loads(fields["data"])
                yield event
                if event.get("type") in ("run_finished", "run_error"):
                    return
