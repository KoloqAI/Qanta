from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import state

router = APIRouter()


@router.websocket("/jobs/{job_id}")
async def ws_job(websocket: WebSocket, job_id: str) -> None:
    """WebSocket for job progress updates.

    Reads the Redis Stream ``job:{job_id}:events`` via XREAD BLOCK,
    starting from id "0" so late-connecting clients replay all events.
    For legacy jobs that never publish a stream the XREAD times out
    every 5 s and the handler sends a heartbeat — identical to the old
    heartbeat-only fallback.
    """
    await websocket.accept()
    try:
        from app.workers.job_events import iter_events

        async for event in iter_events(job_id):
            if event is None:
                await websocket.send_json({
                    "type": "heartbeat",
                    "job_id": job_id,
                    "ts": datetime.utcnow().isoformat(),
                })
            else:
                await websocket.send_json(event)
                if event.get("type") in ("run_finished", "run_error"):
                    break
    except WebSocketDisconnect:
        pass


@router.websocket("/monitor")
async def ws_monitor(websocket: WebSocket) -> None:
    """WebSocket for live monitor data. Sends positions, PnL, and
    kill switch status every 5 seconds."""
    await websocket.accept()
    try:
        while True:
            positions = await state.broker.positions()
            gross_exposure = sum(
                abs(p.get("qty", 0)) * 100
                for p in positions
            )

            await websocket.send_json({
                "type": "monitor",
                "ts": datetime.utcnow().isoformat(),
                "equity": state.INITIAL_EQUITY,
                "positions": positions,
                "gross_exposure": gross_exposure,
                "kill_switch": state.risk_gate.is_killed,
                "active_deployments": len(state.runtime._active),
            })

            # Wait for messages or timeout
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass


@router.websocket("/assistant")
async def ws_assistant(websocket: WebSocket) -> None:
    """WebSocket for streaming assistant responses. Receives messages
    and streams back responses."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                content = msg.get("content", "")
            except json.JSONDecodeError:
                content = data

            # Send acknowledgement
            await websocket.send_json({
                "type": "ack",
                "ts": datetime.utcnow().isoformat(),
            })

            # Stream a simple response (in production this would invoke
            # the tool pipeline and stream intermediate results)
            await websocket.send_json({
                "type": "response",
                "content": (
                    f"Received your message: '{content[:100]}'. "
                    "Use the REST API at POST /assistant/messages for "
                    "full tool execution."
                ),
                "ts": datetime.utcnow().isoformat(),
                "done": True,
            })
    except WebSocketDisconnect:
        pass
