from __future__ import annotations

from typing import Any


async def run_research(ctx: dict, run_id: str, goal: str, **kwargs: Any) -> dict:
    from app.modules.research.service import (
        ShortTermEquityDomain,
        StrategyAuthorImpl,
        create_llm_provider,
    )

    llm = create_llm_provider()
    domain = ShortTermEquityDomain(llm=llm)
    candidates = await domain.scan(goal, {})
    specs = []
    author = StrategyAuthorImpl(llm=llm)
    for c in candidates[:3]:
        spec = await author.author(
            f"{goal} opportunity in {c['ticker']}", {"ticker": c["ticker"]}
        )
        concerns = await author.red_team(spec)
        specs.append({"spec": spec, "concerns": concerns})
    return {"run_id": run_id, "status": "completed", "candidates": specs}


async def run_backtest(
    ctx: dict, strategy_version_id: str, window: dict, **kwargs: Any
) -> dict:
    from app.core.dsl.parser import parse_spec
    from app.modules.backtest.service import BacktesterImpl
    from app.modules.data.providers import create_data_provider, recent_window
    from datetime import datetime

    spec_raw = kwargs.get("spec", {})
    parse_result = parse_spec(spec_raw)
    if not parse_result.success:
        return {"strategy_version_id": strategy_version_id, "status": "failed",
                "errors": [e.message for e in (parse_result.errors or [])]}

    provider = create_data_provider()
    ticker = parse_result.spec.tickers[0] if parse_result.spec.tickers else "AAPL"
    default_start, default_end = recent_window(700)
    start = datetime.fromisoformat(window["start"]) if window.get("start") else default_start
    end = datetime.fromisoformat(window["end"]) if window.get("end") else default_end
    bars = await provider.bars(ticker, start, end)

    bt = BacktesterImpl()
    result = await bt.run(parse_result.spec, bars)
    return {
        "strategy_version_id": strategy_version_id,
        "status": "completed",
        "sharpe": result.sharpe,
        "net_edge": result.net_edge,
        "frictionless_edge": result.frictionless_edge,
        "n_trades": result.n_trades,
    }


async def run_validation(ctx: dict, strategy_version_id: str, **kwargs: Any) -> dict:
    from app.core.dsl.parser import parse_spec
    from app.modules.validation.service import ValidationHarnessImpl
    from app.modules.data.providers import create_data_provider, recent_window, SAMPLE_UNIVERSE
    from app.modules.data.peers import select_correlation_peers

    spec_raw = kwargs.get("spec", {})
    parse_result = parse_spec(spec_raw)
    if not parse_result.success:
        return {"strategy_version_id": strategy_version_id, "status": "failed"}

    provider = create_data_provider()
    ticker = parse_result.spec.tickers[0] if parse_result.spec.tickers else "AAPL"
    start, end = recent_window(700)
    bars = await provider.bars(ticker, start, end)
    as_of = end

    candidates = await provider.filtered_universe(
        as_of=as_of, min_price=5, min_dollar_volume=5_000_000, cap=200,
    )
    if not candidates:
        candidates = list(SAMPLE_UNIVERSE)

    selection = await select_correlation_peers(
        primary=ticker,
        candidates=candidates,
        provider=provider,
        as_of=as_of,
    )

    harness = ValidationHarnessImpl()
    report = await harness.validate(
        parse_result.spec, bars,
        n_eff=kwargs.get("n_eff", 1),
        peer_tickers=selection.peers if selection.sufficient else None,
        provider=provider,
        as_of=as_of,
    )
    return {
        "strategy_version_id": strategy_version_id,
        "status": "completed",
        "passed": report.passed,
        "dsr": report.deflated_sharpe,
        "pbo": report.pbo,
        "peer_hit": report.peer_hit,
        "gates_version": report.gates_version,
        "confidence_curve": report.confidence_curve,
    }


async def run_evolution_tier1(ctx: dict, **kwargs: Any) -> dict:
    from app.modules.evolution.service import EvolutionLoopImpl
    from app.modules.monitoring.service import MonitoringServiceImpl
    from app.modules.registry.service import StrategyRegistryImpl

    monitoring = kwargs.get("monitoring") or MonitoringServiceImpl()
    registry = kwargs.get("registry") or StrategyRegistryImpl()
    loop = EvolutionLoopImpl(monitoring=monitoring, registry=registry)
    return await loop.run_tier1()


async def run_evolution_tier2(ctx: dict, budget: int = 10, **kwargs: Any) -> dict:
    from app.modules.evolution.service import EvolutionLoopImpl
    from app.modules.monitoring.service import MonitoringServiceImpl
    from app.modules.registry.service import StrategyRegistryImpl

    monitoring = kwargs.get("monitoring") or MonitoringServiceImpl()
    registry = kwargs.get("registry") or StrategyRegistryImpl()
    loop = EvolutionLoopImpl(monitoring=monitoring, registry=registry)
    return await loop.run_tier2(budget)


async def run_explore(
    ctx: dict,
    job_id: str,
    archetype_id: str,
    budget: int = 10,
    param_grid: dict | None = None,
    **kwargs: Any,
) -> dict:
    """Explore one archetype: universe_scan -> param-grid backtest -> validate.

    Deterministic, agent-free (doc 13 section 2).  Publishes AG-UI events to
    the Redis Stream ``job:{job_id}:events`` for real-time WS relay.
    """
    import copy
    import hashlib
    import json as _json
    import uuid as _uuid
    from datetime import datetime, timedelta

    import numpy as np

    from app.core.dsl.parser import parse_spec
    from app.modules.backtest.service import BacktesterImpl
    from app.modules.validation.service import ValidationHarnessImpl, _load_validation_config
    from app.modules.data.providers import (
        create_data_provider, recent_window, scan_universe, SampleDataProvider,
    )
    from app.modules.registry.library_loader import load_archetypes, _fill_placeholders
    from app.modules.registry.service import StrategyRegistryImpl
    from app.modules.evolution.service import _build_archetype_variants
    from app.workers.job_events import publish_event

    async def emit(event: dict) -> None:
        await publish_event(job_id, event)

    await emit({"type": "run_started", "label": f"Exploring archetype {archetype_id}"})

    try:
        archetypes = load_archetypes(validate=True)
        archetype = archetypes.get(archetype_id)
        if not archetype:
            await emit({"type": "run_error", "error": f"Archetype {archetype_id} not found"})
            return {"status": "failed", "error": "archetype_not_found"}

        if archetype.get("status") == "excluded":
            reason = archetype.get("exclusion_reason", "")
            await emit({"type": "run_error", "error": f"Archetype excluded: {reason}"})
            return {"status": "failed", "error": "archetype_excluded"}

        family = archetype.get("family", "unknown")
        grid = param_grid or archetype.get("param_grid", {})
        template = archetype["template"]

        harness = ValidationHarnessImpl()
        provider = create_data_provider()
        bt = BacktesterImpl()
        registry = kwargs.get("registry") or StrategyRegistryImpl()
        is_sample = isinstance(provider, SampleDataProvider)

        val_config = _load_validation_config()
        max_configs = val_config.get("pbo", {}).get("max_configs", 20)

        as_of_dt = datetime.utcnow() - timedelta(days=1)

        # ── Universe scan ────────────────────────────────────────────
        scan_step_id = str(_uuid.uuid4())
        await emit({"type": "step_started", "step_id": scan_step_id, "label": "Universe scan"})

        scan_result = await scan_universe(archetype, as_of=as_of_dt)
        candidates = scan_result["candidates"]

        await emit({
            "type": "step_finished", "step_id": scan_step_id,
            "label": "Universe scan", "status": "done",
        })

        candidates_per_archetype = min(len(candidates), budget)

        funnel = {"trials": 0, "backtested": 0, "validated": 0, "survivors": 0}
        survivors: list[dict] = []
        run_ledger: list[dict] = []
        n_eff = 0

        for candidate in candidates[:candidates_per_archetype]:
            if funnel["trials"] >= budget:
                break

            ticker = candidate["ticker"]

            # ── Backtest step ────────────────────────────────────────
            bt_step_id = str(_uuid.uuid4())
            await emit({"type": "step_started", "step_id": bt_step_id, "label": f"Backtest {ticker}"})

            tmpl = copy.deepcopy(template)
            tmpl["tickers"] = [ticker]
            tmpl.setdefault("universe", {})
            if isinstance(tmpl["universe"], dict):
                tmpl["universe"]["primary"] = ticker
            tmpl.setdefault("validation", {"targets": [{"R": 0.02, "H": 7}]})

            if grid:
                variants = _build_archetype_variants(tmpl, grid, max_configs)
            else:
                variants = [_fill_placeholders(tmpl, {})]

            val_start, val_end = recent_window(700)
            bars = await provider.bars(ticker, val_start, val_end)

            if bars.empty or len(bars) < 50:
                funnel["trials"] += 1
                n_eff += 1
                await emit({
                    "type": "step_finished", "step_id": bt_step_id,
                    "label": f"Backtest {ticker}", "status": "done",
                })
                await emit({"type": "progress", "funnel": dict(funnel)})
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

            # Competing-returns matrix (T x N), dedup identical columns
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

            # Select IS-best winner by Sharpe
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
                funnel["trials"] += 1
                n_eff += 1
                await emit({
                    "type": "step_finished", "step_id": bt_step_id,
                    "label": f"Backtest {ticker}", "status": "done",
                })
                await emit({"type": "progress", "funnel": dict(funnel)})
                continue

            funnel["trials"] += 1
            funnel["backtested"] += 1
            n_eff += 1

            await emit({
                "type": "step_finished", "step_id": bt_step_id,
                "label": f"Backtest {ticker}", "status": "done",
            })

            # Log to search ledger
            ledger_entry = {
                "spec_hash": hashlib.md5(
                    _json.dumps(winner_raw, sort_keys=True, default=str).encode()
                ).hexdigest(),
                "hypothesis_family": family,
                "archetype_id": archetype_id,
                "ticker": ticker,
                "n_configs_swept": len(valid_specs),
                "n_configs_distinct": n_configs_distinct,
                "winner_sharpe": round(winner_sharpe, 4),
                "is_sample_fallback": is_sample,
                "validation_passed": None,
                "failed_gates": [],
                "ts": datetime.utcnow().isoformat(),
            }
            run_ledger.append(ledger_entry)

            await emit({"type": "progress", "funnel": dict(funnel)})

            # ── Validate step ────────────────────────────────────────
            val_step_id = str(_uuid.uuid4())
            await emit({"type": "step_started", "step_id": val_step_id, "label": f"Validate {ticker}"})

            peer_tickers = [c["ticker"] for c in candidates if c["ticker"] != ticker][:5]
            arch_peers_hint = archetype.get("peers_hint", "")

            try:
                report = await harness.validate(
                    winner_spec, bars,
                    n_eff=n_eff,
                    competing_returns=competing_returns,
                    peer_tickers=peer_tickers if peer_tickers else None,
                    provider=provider,
                    as_of=as_of_dt,
                    peers_hint=arch_peers_hint,
                )
            except Exception:
                ledger_entry["validation_passed"] = False
                ledger_entry["failed_gates"] = ["validation_error"]
                await emit({
                    "type": "step_finished", "step_id": val_step_id,
                    "label": f"Validate {ticker}", "status": "failed",
                })
                await emit({"type": "progress", "funnel": dict(funnel)})
                continue

            funnel["validated"] += 1

            gate_results = report.detail.get("gates", {})
            failed_gates = [g for g, ok in gate_results.items() if not ok]
            ledger_entry["validation_passed"] = report.passed
            ledger_entry["failed_gates"] = failed_gates

            if report.passed:
                strategy = await registry.create(winner_raw, "system")
                strategy_id = strategy["id"]
                await registry.update_state(
                    strategy_id, winner_raw.get("version", 1), "validated",
                )
                funnel["survivors"] += 1
                survivors.append({
                    "ticker": ticker,
                    "archetype_id": archetype_id,
                    "family": family,
                    "strategy_id": strategy_id,
                    "deflated_sharpe": report.deflated_sharpe,
                    "pbo": report.pbo,
                    "peer_hit": report.peer_hit,
                    "n_configs_swept": len(valid_specs),
                    "n_configs_distinct": n_configs_distinct,
                    "n_eff_at_discovery": n_eff,
                    "gates_version": report.gates_version,
                    "ts": datetime.utcnow().isoformat(),
                })

            await emit({
                "type": "step_finished", "step_id": val_step_id,
                "label": f"Validate {ticker}",
                "status": "done" if report.passed else "failed",
            })
            await emit({"type": "progress", "funnel": dict(funnel)})

        # ── Terminal: run_finished ────────────────────────────────────
        await emit({
            "type": "run_finished",
            "status": "done",
            "funnel": dict(funnel),
            "survivors": survivors,
        })

        return {
            "status": "completed",
            "archetype_id": archetype_id,
            "trials_run": funnel["trials"],
            "survivors": survivors,
            "n_eff": n_eff,
            "ledger": run_ledger,
            "is_sample_fallback": is_sample,
        }

    except Exception as exc:
        try:
            await emit({"type": "run_error", "error": str(exc)})
        except Exception:
            pass
        raise
