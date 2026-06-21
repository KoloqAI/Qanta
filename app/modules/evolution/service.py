from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Protocol


class EvolutionLoop(Protocol):
    async def run_tier1(self) -> dict: ...
    async def run_tier2(self, budget: int) -> dict: ...
    async def propose_tier3(self, proposal: dict) -> dict: ...
    async def get_meta_lockbox_result(self) -> dict: ...


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMOTE_MIN_SESSIONS = 30
PROMOTE_MIN_SHARPE = 1.0
RETIRE_MAX_DD_THRESHOLD = 0.20  # 20% max drawdown triggers retirement


class EvolutionLoopImpl:
    """Scheduled evolution: promote/retire/discover/propose.

    T1: promote proven winners, retire decayed strategies (auto)
    T2: budgeted discovery — compose new specs, run gauntlet, log to ledger
    T3: capability proposals — new primitives/tools (human-gated)

    Evolution NEVER relaxes a guardrail, skips human gate, or self-deploys.
    """

    def __init__(self, monitoring=None, registry=None) -> None:
        self._monitoring = monitoring  # MonitoringServiceImpl
        self._registry = registry      # StrategyRegistryImpl
        self._promotions: list[dict] = []
        self._retirements: list[dict] = []
        self._discoveries: list[dict] = []
        self._proposals: list[dict] = []
        self._n_eff: int = 0  # total trials run across T2 rounds (DSR deflation)
        self._meta_lockbox: dict[str, Any] = {"status": "not_evaluated"}
        self._pre_change_sharpe: float | None = None

    # ------------------------------------------------------------------
    # T1 — Promote / Retire
    # ------------------------------------------------------------------

    async def run_tier1(self) -> dict:
        """Promote/retire based on performance monitoring.

        Promote: strategies paper-traded 30+ sessions with Sharpe > 1.0
                 and no decay detected.
        Retire:  strategies where decay has been detected (Sharpe degraded
                 significantly) or max drawdown exceeded threshold.
        """
        promoted: list[dict] = []
        retired: list[dict] = []

        if self._monitoring is None or self._registry is None:
            return {
                "tier": 1,
                "promoted": promoted,
                "retired": retired,
                "summary": "T1: skipped (no monitoring/registry)",
            }

        # Gather all strategies currently deployed for paper trading
        strategies = await self._registry.list_all({"status": "paper"})

        for strategy in strategies:
            strategy_id = strategy["id"]
            spec = strategy.get("spec", {})
            deployment_id = strategy_id  # use strategy_id as deployment key

            # Fetch performance records from monitoring
            records = self._monitoring._performance.get(deployment_id, [])
            n_sessions = len(records)

            # Check for decay
            decay_result = await self._monitoring.check_decay(deployment_id)

            # Compute aggregate Sharpe from records
            sharpe_values = [r.get("sharpe", 0) for r in records]
            avg_sharpe = (
                sum(sharpe_values) / len(sharpe_values) if sharpe_values else 0.0
            )

            # Compute max drawdown from records
            max_dd = max(
                (abs(r.get("max_drawdown", 0)) for r in records), default=0.0
            )

            # Retire: decay detected or max drawdown exceeded
            if decay_result.get("decayed", False):
                entry = {
                    "strategy_id": strategy_id,
                    "reason": f"decay_detected: {decay_result.get('reason', '')}",
                    "avg_sharpe": round(avg_sharpe, 4),
                    "n_sessions": n_sessions,
                    "ts": datetime.utcnow().isoformat(),
                }
                retired.append(entry)
                self._retirements.append(entry)
                continue

            if max_dd > RETIRE_MAX_DD_THRESHOLD:
                entry = {
                    "strategy_id": strategy_id,
                    "reason": f"max_dd {max_dd:.2%} exceeded threshold {RETIRE_MAX_DD_THRESHOLD:.2%}",
                    "avg_sharpe": round(avg_sharpe, 4),
                    "max_dd": round(max_dd, 4),
                    "n_sessions": n_sessions,
                    "ts": datetime.utcnow().isoformat(),
                }
                retired.append(entry)
                self._retirements.append(entry)
                continue

            # Promote: 30+ sessions, Sharpe > 1.0, no decay
            if (
                n_sessions >= PROMOTE_MIN_SESSIONS
                and avg_sharpe > PROMOTE_MIN_SHARPE
            ):
                entry = {
                    "strategy_id": strategy_id,
                    "reason": "passed_paper_period",
                    "avg_sharpe": round(avg_sharpe, 4),
                    "n_sessions": n_sessions,
                    "ts": datetime.utcnow().isoformat(),
                }
                promoted.append(entry)
                self._promotions.append(entry)

        return {
            "tier": 1,
            "promoted": promoted,
            "retired": retired,
            "summary": f"T1: {len(promoted)} promoted, {len(retired)} retired",
        }

    # ------------------------------------------------------------------
    # T2 — Budgeted Discovery
    # ------------------------------------------------------------------

    async def run_tier2(self, budget: int) -> dict:
        """Budgeted discovery — compose and validate new strategies.

        1. Scan for candidates using ShortTermEquityDomain
        2. Compose specs using StrategyAuthorImpl
        3. Parse and validate each through ValidationHarnessImpl
        4. Track N_eff for DSR deflation
        5. Keep only survivors that pass validation
        """
        from app.modules.research.service import ShortTermEquityDomain, StrategyAuthorImpl
        from app.core.dsl.parser import parse_spec
        from app.modules.validation.service import ValidationHarnessImpl
        from app.modules.data.providers import SampleDataProvider
        from datetime import datetime as dt

        survivors: list[dict] = []
        trials_run = 0

        domain = ShortTermEquityDomain()
        author = StrategyAuthorImpl()
        harness = ValidationHarnessImpl()
        provider = SampleDataProvider()

        # Scan for candidate tickers
        candidates = await domain.scan("short-term momentum and mean-reversion", {})

        for candidate in candidates:
            if trials_run >= budget:
                break

            ticker = candidate.get("ticker", "AAPL")

            # Compose a strategy spec for this candidate
            spec_raw = await author.author(
                f"Short-term opportunity in {ticker}",
                {"ticker": ticker},
            )

            # Parse the spec
            parse_result = parse_spec(spec_raw)
            if not parse_result.success:
                trials_run += 1
                self._n_eff += 1
                continue

            # Fetch bars for validation
            bars = await provider.bars(
                ticker, dt(2018, 1, 1), dt(2023, 1, 1)
            )

            # Run validation gauntlet with accumulated N_eff
            self._n_eff += 1
            trials_run += 1

            try:
                report = await harness.validate(
                    parse_result.spec, bars, n_eff=self._n_eff
                )
            except Exception:
                continue

            if report.passed:
                discovery = {
                    "ticker": ticker,
                    "spec": spec_raw,
                    "deflated_sharpe": report.deflated_sharpe,
                    "pbo": report.pbo,
                    "n_eff_at_discovery": self._n_eff,
                    "ts": datetime.utcnow().isoformat(),
                }
                survivors.append(discovery)
                self._discoveries.append(discovery)

        return {
            "tier": 2,
            "budget": budget,
            "trials_run": trials_run,
            "survivors": survivors,
            "n_eff": self._n_eff,
            "summary": f"T2: {trials_run}/{budget} trials, {len(survivors)} survivors",
        }

    # ------------------------------------------------------------------
    # T3 — Capability Proposals (human-gated) — already implemented
    # ------------------------------------------------------------------

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

                # After a T3 decision, evaluate meta-lockbox impact
                await self._evaluate_meta_lockbox()

                return p
        return {"error": "Proposal not found"}

    # ------------------------------------------------------------------
    # Meta-lockbox
    # ------------------------------------------------------------------

    async def record_pre_change_sharpe(self, sharpe: float) -> None:
        """Snapshot aggregate portfolio Sharpe before a T3 change is applied."""
        self._pre_change_sharpe = sharpe

    async def _evaluate_meta_lockbox(self) -> None:
        """Compare aggregate portfolio performance before/after a T3 change.

        Simple implementation: track whether overall Sharpe improved or
        degraded after the change. If no pre-change snapshot exists, record
        as inconclusive.
        """
        if self._pre_change_sharpe is None:
            self._meta_lockbox = {
                "status": "inconclusive",
                "reason": "no pre-change Sharpe snapshot recorded",
                "ts": datetime.utcnow().isoformat(),
            }
            return

        # Compute post-change Sharpe from promotions (best available proxy)
        post_sharpes = [
            p.get("avg_sharpe", 0) for p in self._promotions if p.get("avg_sharpe")
        ]
        if not post_sharpes:
            self._meta_lockbox = {
                "status": "inconclusive",
                "reason": "no post-change performance data available",
                "pre_sharpe": self._pre_change_sharpe,
                "ts": datetime.utcnow().isoformat(),
            }
            return

        post_sharpe = sum(post_sharpes) / len(post_sharpes)
        improved = post_sharpe >= self._pre_change_sharpe

        self._meta_lockbox = {
            "status": "improved" if improved else "degraded",
            "pre_sharpe": round(self._pre_change_sharpe, 4),
            "post_sharpe": round(post_sharpe, 4),
            "delta": round(post_sharpe - self._pre_change_sharpe, 4),
            "ts": datetime.utcnow().isoformat(),
        }

    async def get_meta_lockbox_result(self) -> dict:
        return self._meta_lockbox

    async def get_digest(self) -> dict:
        return {
            "promotions": self._promotions,
            "retirements": self._retirements,
            "discoveries": self._discoveries,
            "proposals": self._proposals,
            "meta_lockbox": self._meta_lockbox,
            "n_eff": self._n_eff,
        }
