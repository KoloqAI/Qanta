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
