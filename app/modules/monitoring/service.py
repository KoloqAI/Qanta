from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Protocol


class MonitoringService(Protocol):
    async def record_performance(self, deployment_id: str, metrics: dict) -> None: ...
    async def check_decay(self, deployment_id: str) -> dict: ...
    async def get_calibration(self, strategy_id: str) -> list[dict]: ...


class AuditLog(Protocol):
    async def log(
        self,
        actor: str,
        action: str,
        subject_type: str,
        subject_id: str,
        payload: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> None: ...
    async def query(self, filters: dict) -> list[dict]: ...


class MonitoringServiceImpl:
    """Performance monitoring, decay detection, calibration tracking."""

    def __init__(self) -> None:
        self._performance: dict[str, list[dict]] = {}
        self._calibration: dict[str, list[dict]] = {}

    async def record_performance(self, deployment_id: str, metrics: dict) -> None:
        self._performance.setdefault(deployment_id, []).append({
            "ts": datetime.utcnow().isoformat(),
            **metrics,
        })

    async def check_decay(self, deployment_id: str) -> dict:
        records = self._performance.get(deployment_id, [])
        if len(records) < 20:
            return {"decayed": False, "reason": "Insufficient data", "n_records": len(records)}

        recent = records[-10:]
        older = records[-20:-10]

        recent_sharpe = sum(r.get("sharpe", 0) for r in recent) / len(recent)
        older_sharpe = sum(r.get("sharpe", 0) for r in older) / len(older)

        decay_threshold = 0.5
        if older_sharpe > 0 and recent_sharpe < older_sharpe * decay_threshold:
            return {
                "decayed": True,
                "reason": f"Sharpe degraded from {older_sharpe:.2f} to {recent_sharpe:.2f}",
                "recent_sharpe": round(recent_sharpe, 4),
                "older_sharpe": round(older_sharpe, 4),
            }
        return {"decayed": False, "recent_sharpe": round(recent_sharpe, 4)}

    async def get_calibration(self, strategy_id: str) -> list[dict]:
        return self._calibration.get(strategy_id, [])

    async def record_calibration(
        self, strategy_id: str, claimed_c: float, target_r: float, horizon: int, realized: bool
    ) -> None:
        self._calibration.setdefault(strategy_id, []).append({
            "claimed_c": claimed_c,
            "target_r": target_r,
            "horizon": horizon,
            "realized": realized,
            "ts": datetime.utcnow().isoformat(),
        })


class AuditLogImpl:
    """Immutable audit log. Every signal, order, fill, rejection, approval,
    kill-switch event, assistant action, and evolution change."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    async def log(
        self,
        actor: str,
        action: str,
        subject_type: str,
        subject_id: str,
        payload: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> None:
        self._entries.append({
            "id": str(uuid.uuid4()),
            "actor": actor,
            "action": action,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "payload": payload or {},
            "user_id": user_id,
            "ts": datetime.utcnow().isoformat(),
        })

    async def query(self, filters: dict) -> list[dict]:
        results = self._entries
        if "actor" in filters:
            results = [e for e in results if e["actor"] == filters["actor"]]
        if "action" in filters:
            results = [e for e in results if e["action"] == filters["action"]]
        if "subject_type" in filters:
            results = [e for e in results if e["subject_type"] == filters["subject_type"]]
        if "subject_id" in filters:
            results = [e for e in results if e["subject_id"] == filters["subject_id"]]
        return results

    def all_entries(self) -> list[dict[str, Any]]:
        return list(self._entries)
