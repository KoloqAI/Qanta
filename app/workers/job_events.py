"""In-process event bus for job progress streaming.

Per-job event buffer that supports multiple readers (WS clients), handles
the subscribe-before-publish race via pre-initialized buffers, and signals
heartbeats on idle timeout.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator


_buffers: dict[str, list[dict[str, Any]]] = {}
_notifiers: dict[str, asyncio.Event] = {}


def init_job(job_id: str) -> None:
    """Initialize event buffer for a job.  Call before spawning the task."""
    _buffers[job_id] = []
    _notifiers[job_id] = asyncio.Event()


def has_job(job_id: str) -> bool:
    return job_id in _buffers


async def publish_event(job_id: str, event: dict[str, Any]) -> None:
    """Append an event to the job's buffer and wake waiting readers."""
    event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    buf = _buffers.get(job_id)
    if buf is not None:
        buf.append(event)
    ev = _notifiers.get(job_id)
    if ev is not None:
        ev.set()


async def iter_events(
    job_id: str, timeout: float = 5.0,
) -> AsyncIterator[dict[str, Any] | None]:
    """Yield buffered + live events for a job.

    Starts from the head of the buffer so late-connecting clients catch
    up.  Yields *None* after *timeout* seconds of inactivity (caller
    should send a WS heartbeat).  Returns on terminal events.
    """
    idx = 0
    ev = _notifiers.get(job_id)
    if ev is None:
        return

    while True:
        buf = _buffers.get(job_id, [])
        while idx < len(buf):
            event = buf[idx]
            idx += 1
            yield event
            if event.get("type") in ("run_finished", "run_error"):
                return
        ev.clear()
        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            yield None


def cleanup_job(job_id: str) -> None:
    """Remove the event buffer for a completed job."""
    _buffers.pop(job_id, None)
    _notifiers.pop(job_id, None)
