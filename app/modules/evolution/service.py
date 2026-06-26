from __future__ import annotations

import copy
import hashlib
import itertools
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Protocol

import numpy as np

from app.modules.registry.library_loader import (
    _fill_placeholders,
    _extract_defaults,
    resolve_grid_values,
)


class EvolutionLoop(Protocol):
    async def run_tier1(self) -> dict: ...
    async def run_tier2(self, budget: int) -> dict: ...
    async def propose_tier3(self, proposal: dict) -> dict: ...
    async def get_meta_lockbox_result(self) -> dict: ...


# ---------------------------------------------------------------------------
# Param-grid helpers
# ---------------------------------------------------------------------------


def _build_archetype_variants(
    template: dict,
    grid: dict[str, dict],
    n_max: int,
) -> list[dict]:
    """Build spec variants from an archetype's param_grid using explicit
    placeholder filling.

    *template* contains ``{param}`` placeholders; *grid* entries have
    ``default`` values.  The base variant uses defaults; sweep variants
    fill other combos from the cartesian product.

    Order: build full product → dedup distinct specs → strided-cap on
    the distinct set.  Base spec is always variant 0.

    Returns a **deduplicated** list — identical specs never appear twice.
    """
    defaults = _extract_defaults(grid)
    base = _fill_placeholders(template, defaults)
    base_key = json.dumps(base, sort_keys=True, default=str)

    param_names = list(grid.keys())
    param_values = [resolve_grid_values(grid[k]) for k in param_names]

    full_product = list(itertools.product(*param_values))
    if not full_product:
        return [base]

    # Step 1: dedup full product into distinct variants (excluding base)
    seen = {base_key}
    distinct: list[dict] = []
    for combo in full_product:
        values = dict(zip(param_names, combo))
        variant = _fill_placeholders(template, values)
        key = json.dumps(variant, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            distinct.append(variant)

    if not distinct:
        return [base]

    # Step 2: strided cap on the distinct set (not the raw product)
    if len(distinct) > n_max:
        indices = np.round(np.linspace(0, len(distinct) - 1, n_max)).astype(int)
        indices = list(dict.fromkeys(indices))
        if len(indices) < n_max:
            rng = np.random.default_rng(42)
            remaining = [i for i in range(len(distinct)) if i not in set(indices)]
            extra = rng.choice(remaining, min(n_max - len(indices), len(remaining)), replace=False)
            indices.extend(int(e) for e in extra)
        selected = [distinct[i] for i in sorted(indices[:n_max])]
    else:
        selected = distinct

    return [base] + selected


def _build_stop_loss_variants(spec_raw: dict, n_max: int) -> list[dict]:
    """Fallback: vary stop_loss when no archetype grid is available."""
    variants: list[dict] = [spec_raw]
    base_stop: float | None = None
    stop_idx: int | None = None
    for i, rule in enumerate(spec_raw.get("exits", [])):
        if isinstance(rule, dict) and "stop_loss" in rule:
            sl = rule["stop_loss"]
            if isinstance(sl, dict):
                base_stop = sl.get("pct") or sl.get("atr_mult")
                stop_idx = i
            break
    if base_stop is None or stop_idx is None:
        return variants

    field = "pct" if "pct" in spec_raw["exits"][stop_idx]["stop_loss"] else "atr_mult"
    multipliers = [0.50, 0.67, 0.80, 1.25, 1.50, 1.80, 2.00]
    for mult in multipliers:
        if len(variants) >= n_max:
            break
        variant = copy.deepcopy(spec_raw)
        new_val = round(base_stop * mult, 2)
        variant["exits"][stop_idx]["stop_loss"][field] = new_val
        if field == "pct" and isinstance(variant.get("risk"), dict):
            variant["risk"]["per_trade_stop_pct"] = new_val
        variants.append(variant)
    return variants


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
        self._ledger: list[dict] = []
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

    async def run_tier2(
        self,
        budget: int,
        archetype_subset: list[str] | None = None,
        as_of: datetime | None = None,
        candidates_per_archetype: int = 3,
    ) -> dict:
        """Budgeted discovery — scan per archetype, sweep param grids, validate.

        Iterates over library archetypes (not a generic domain scan), runs
        ``scan_universe()`` per archetype to find candidate tickers, fills
        archetype template with ticker + param_grid combos, backtests all
        variants, and validates the IS-best winner with multi-config PBO.

        n_eff counts hypothesis families (one per ticker/archetype), NOT
        individual param variants — PBO measures within-family selection-
        overfitting, DSR deflates across families.  Orthogonal, no double-
        counting.

        Every trial is logged to ``self._ledger``; survivors are registered
        in ``self._registry`` so they appear in the Review Queue.
        """
        from app.core.dsl.parser import parse_spec
        from app.modules.backtest.service import BacktesterImpl
        from app.modules.validation.service import ValidationHarnessImpl, _load_validation_config
        from app.modules.data.providers import (
            create_data_provider, recent_window, scan_universe, SampleDataProvider,
            enrich_bars_if_needed,
        )
        from app.modules.registry.library_loader import load_archetypes

        survivors: list[dict] = []
        trials_run = 0
        run_ledger: list[dict] = []

        harness = ValidationHarnessImpl()
        provider = create_data_provider()
        bt = BacktesterImpl()
        is_sample_provider = isinstance(provider, SampleDataProvider)

        val_config = _load_validation_config()
        max_configs = val_config.get("pbo", {}).get("max_configs", 20)
        archetypes = load_archetypes(validate=True)

        active = {
            aid: a for aid, a in archetypes.items()
            if a.get("status") != "excluded"
            and (archetype_subset is None or aid in archetype_subset)
        }

        if as_of is None:
            as_of_dt = datetime.utcnow() - timedelta(days=1)
        else:
            as_of_dt = as_of

        families_seen: dict[str, int] = {}

        for archetype_id, archetype in active.items():
            if trials_run >= budget:
                break

            family = archetype.get("family", "unknown")
            scan_result = await scan_universe(archetype, as_of=as_of_dt)
            candidates = scan_result["candidates"]

            for candidate in candidates[:candidates_per_archetype]:
                if trials_run >= budget:
                    break

                ticker = candidate["ticker"]

                # Inject ticker into archetype template
                template = copy.deepcopy(archetype["template"])
                template["tickers"] = [ticker]
                template.setdefault("universe", {})
                if isinstance(template["universe"], dict):
                    template["universe"]["primary"] = ticker
                template.setdefault("validation", {"targets": [{"R": 0.02, "H": 7}]})

                # Build param-grid variants from archetype template
                grid = archetype.get("param_grid", {})
                if grid:
                    variants = _build_archetype_variants(template, grid, max_configs)
                else:
                    variants = [_fill_placeholders(template, {})]

                val_start, val_end = recent_window(700)
                bars = await provider.bars(ticker, val_start, val_end)
                bars = await enrich_bars_if_needed(
                    provider, archetype, ticker, bars, as_of_dt,
                )
                if bars.empty or len(bars) < 50:
                    trials_run += 1
                    self._n_eff += 1
                    families_seen[family] = families_seen.get(family, 0) + 1
                    continue

                all_returns: list[np.ndarray] = []
                valid_specs: list[Any] = []
                valid_raws: list[dict] = []

                for var_raw in variants:
                    var_parse = parse_spec(var_raw)
                    if not var_parse.success:
                        continue
                    try:
                        result = await bt.run(var_parse.spec, bars)
                        equities = [e["equity"] for e in result.equity_curve]
                        if len(equities) > 1:
                            rets = np.diff(equities) / np.array(equities[:-1], dtype=float)
                            all_returns.append(rets)
                            valid_specs.append(var_parse.spec)
                            valid_raws.append(var_raw)
                    except Exception:
                        continue

                # Build competing-returns matrix (T×N), dedup identical columns
                competing_returns: np.ndarray | None = None
                n_configs_distinct = len(all_returns)
                if len(all_returns) >= 2:
                    min_t = min(len(r) for r in all_returns)
                    raw_matrix = np.column_stack([r[:min_t] for r in all_returns])
                    seen_cols: dict[bytes, int] = {}
                    unique_indices: list[int] = []
                    for j in range(raw_matrix.shape[1]):
                        key = raw_matrix[:, j].tobytes()
                        if key not in seen_cols:
                            seen_cols[key] = j
                            unique_indices.append(j)
                    n_configs_distinct = len(unique_indices)
                    if n_configs_distinct >= 2:
                        competing_returns = raw_matrix[:, unique_indices]

                # Select winner: best Sharpe across variants
                if valid_specs:
                    sharpes = [
                        float(np.mean(r) / np.std(r)) if np.std(r) > 0 else 0.0
                        for r in all_returns
                    ]
                    winner_idx = int(np.argmax(sharpes))
                    winner_spec = valid_specs[winner_idx]
                    winner_raw = valid_raws[winner_idx]
                    winner_sharpe = sharpes[winner_idx]
                else:
                    trials_run += 1
                    self._n_eff += 1
                    families_seen[family] = families_seen.get(family, 0) + 1
                    continue

                # n_eff counts families (one per ticker/archetype), not param variants
                self._n_eff += 1
                trials_run += 1
                families_seen[family] = families_seen.get(family, 0) + 1

                # Log to search ledger
                ledger_entry = {
                    "spec_hash": hashlib.md5(
                        json.dumps(winner_raw, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                    "hypothesis_family": family,
                    "archetype_id": archetype_id,
                    "ticker": ticker,
                    "n_configs_swept": len(valid_specs),
                    "n_configs_distinct": n_configs_distinct,
                    "winner_sharpe": round(winner_sharpe, 4),
                    "is_sample_fallback": is_sample_provider,
                    "validation_passed": None,
                    "failed_gates": [],
                    "ts": datetime.utcnow().isoformat(),
                }
                run_ledger.append(ledger_entry)
                self._ledger.append(ledger_entry)

                # Derive peer tickers from scan candidates (excl. current ticker)
                peer_tickers = [
                    c["ticker"] for c in candidates
                    if c["ticker"] != ticker
                ][:5]
                arch_peers_hint = archetype.get("peers_hint", "")

                try:
                    report = await harness.validate(
                        winner_spec, bars,
                        n_eff=self._n_eff,
                        competing_returns=competing_returns,
                        peer_tickers=peer_tickers if peer_tickers else None,
                        provider=provider,
                        as_of=as_of_dt,
                        peers_hint=arch_peers_hint,
                    )
                except Exception:
                    ledger_entry["validation_passed"] = False
                    ledger_entry["failed_gates"] = ["validation_error"]
                    continue

                gate_results = report.detail.get("gates", {})
                failed_gates = [g for g, ok in gate_results.items() if not ok]
                ledger_entry["validation_passed"] = report.passed
                ledger_entry["failed_gates"] = failed_gates

                if report.passed:
                    strategy_id = None
                    if self._registry:
                        strategy = await self._registry.create(winner_raw, "system")
                        strategy_id = strategy["id"]
                        await self._registry.update_state(
                            strategy_id, winner_raw.get("version", 1), "validated"
                        )

                    discovery = {
                        "ticker": ticker,
                        "archetype_id": archetype_id,
                        "family": family,
                        "spec": winner_raw,
                        "strategy_id": strategy_id,
                        "deflated_sharpe": report.deflated_sharpe,
                        "pbo": report.pbo,
                        "peer_hit": report.peer_hit,
                        "n_configs_swept": len(valid_specs),
                        "n_configs_distinct": n_configs_distinct,
                        "n_eff_at_discovery": self._n_eff,
                        "gates_version": report.gates_version,
                        "failed_gates": [],
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
            "families_seen": families_seen,
            "ledger": run_ledger,
            "is_sample_fallback": is_sample_provider,
            "summary": f"T2: {trials_run}/{budget} trials, {len(survivors)} survivors, n_eff={self._n_eff}",
        }

    # ------------------------------------------------------------------
    # Param grid for multi-config PBO
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_param_grid(
        spec_raw: dict,
        n_variants: int = 20,
        archetype_grid: dict[str, dict] | None = None,
    ) -> list[dict]:
        """Generate parameter variants via explicit placeholder filling.

        When *archetype_grid* is provided, *spec_raw* is the archetype
        **template** (with ``{param}`` placeholders).  Defaults fill the
        base variant; the cartesian product of grid values fills the rest
        (strided-sampled if exceeding *n_variants*).  All variants are
        deduplicated — identical specs never appear twice.

        When *archetype_grid* is None, falls back to stop_loss
        variation only (backward compat for non-archetype callers).
        """
        if archetype_grid:
            return _build_archetype_variants(spec_raw, archetype_grid, n_variants)

        return _build_stop_loss_variants(spec_raw, n_variants)

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
            "ledger_count": len(self._ledger),
        }

    def get_ledger(self) -> list[dict]:
        """Return the search ledger entries recorded during T2 runs."""
        return list(self._ledger)
