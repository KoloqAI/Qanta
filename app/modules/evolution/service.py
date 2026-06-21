from __future__ import annotations

import uuid
from typing import Any, Protocol


class EvolutionLoop(Protocol):
    async def run_tier1(self) -> dict: ...
    async def run_tier2(self, budget: int) -> dict: ...
    async def propose_tier3(self, proposal: dict) -> dict: ...
    async def get_meta_lockbox_result(self) -> dict: ...


class EvolutionLoopImpl:
    """Scheduled evolution: promote/retire/discover/propose.

    T1: promote proven winners, retire decayed strategies (auto)
    T2: budgeted discovery — compose new specs, run gauntlet, log to ledger
    T3: capability proposals — new primitives/tools (human-gated)

    Evolution NEVER relaxes a guardrail, skips human gate, or self-deploys.
    """

    def __init__(self) -> None:
        self._promotions: list[dict] = []
        self._retirements: list[dict] = []
        self._discoveries: list[dict] = []
        self._proposals: list[dict] = []
        self._meta_lockbox: dict[str, Any] = {"status": "not_evaluated"}

    async def run_tier1(self) -> dict:
        """Promote/retire based on performance monitoring."""
        promoted = []
        retired = []

        return {
            "tier": 1,
            "promoted": promoted,
            "retired": retired,
            "summary": f"T1: {len(promoted)} promoted, {len(retired)} retired",
        }

    async def run_tier2(self, budget: int) -> dict:
        """Budgeted discovery — compose and validate new strategies."""
        survivors: list[dict] = []
        trials_run = 0

        return {
            "tier": 2,
            "budget": budget,
            "trials_run": trials_run,
            "survivors": survivors,
            "summary": f"T2: {trials_run}/{budget} trials, {len(survivors)} survivors",
        }

    async def propose_tier3(self, proposal: dict) -> dict:
        """Propose a capability change (new primitive/tool). Requires human approval."""
        proposal_id = str(uuid.uuid4())
        entry = {
            "id": proposal_id,
            "proposal": proposal,
            "status": "pending_approval",
            "meta_lockbox_impact": None,
        }
        self._proposals.append(entry)
        return entry

    async def decide_tier3(self, proposal_id: str, approved: bool, reason: str = "") -> dict:
        """Human decides on a T3 proposal."""
        for p in self._proposals:
            if p["id"] == proposal_id:
                p["status"] = "approved" if approved else "rejected"
                p["decision_reason"] = reason
                return p
        return {"error": "Proposal not found"}

    async def get_meta_lockbox_result(self) -> dict:
        return self._meta_lockbox

    async def get_digest(self) -> dict:
        return {
            "promotions": self._promotions,
            "retirements": self._retirements,
            "discoveries": self._discoveries,
            "proposals": self._proposals,
            "meta_lockbox": self._meta_lockbox,
        }
