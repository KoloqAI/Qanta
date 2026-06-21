from __future__ import annotations

import uuid
from typing import Protocol


class StrategyRegistry(Protocol):
    async def create(self, spec: dict, user_id: str) -> dict: ...
    async def get(self, strategy_id: str) -> dict | None: ...
    async def list_all(self, filters: dict | None = None) -> list[dict]: ...
    async def update_state(
        self, strategy_id: str, version: int, new_state: str
    ) -> dict: ...
    async def get_version(
        self, strategy_id: str, version: int
    ) -> dict | None: ...


class StrategyRegistryImpl:
    """In-memory strategy registry for development."""

    def __init__(self) -> None:
        self._strategies: dict[str, dict] = {}
        self._versions: dict[str, list[dict]] = {}

    async def create(self, spec: dict, user_id: str) -> dict:
        strategy_id = str(uuid.uuid4())
        strategy = {
            "id": strategy_id,
            "user_id": user_id,
            "name": spec.get("thesis", "Untitled")[:50],
            "domain": "short_term_equity",
            "family": spec.get("tickers", [""])[0],
            "status": "draft",
            "spec": spec,
        }
        self._strategies[strategy_id] = strategy
        version = {
            "id": str(uuid.uuid4()),
            "strategy_id": strategy_id,
            "version": spec.get("version", 1),
            "rules": spec,
            "thesis": spec.get("thesis", ""),
            "state": "draft",
        }
        self._versions.setdefault(strategy_id, []).append(version)
        return strategy

    async def get(self, strategy_id: str) -> dict | None:
        return self._strategies.get(strategy_id)

    async def list_all(self, filters: dict | None = None) -> list[dict]:
        strategies = list(self._strategies.values())
        if filters:
            status = filters.get("status")
            if status:
                strategies = [s for s in strategies if s.get("status") == status]
        return strategies

    async def update_state(self, strategy_id: str, version: int, new_state: str) -> dict:
        versions = self._versions.get(strategy_id, [])
        for v in versions:
            if v["version"] == version:
                v["state"] = new_state
                return v
        return {"error": "Version not found"}

    async def get_version(self, strategy_id: str, version: int) -> dict | None:
        versions = self._versions.get(strategy_id, [])
        for v in versions:
            if v["version"] == version:
                return v
        return None
