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
    from app.modules.data.providers import SampleDataProvider
    from datetime import datetime

    spec_raw = kwargs.get("spec", {})
    parse_result = parse_spec(spec_raw)
    if not parse_result.success:
        return {"strategy_version_id": strategy_version_id, "status": "failed",
                "errors": [e.message for e in (parse_result.errors or [])]}

    provider = SampleDataProvider()
    ticker = parse_result.spec.tickers[0] if parse_result.spec.tickers else "AAPL"
    start = datetime.fromisoformat(window.get("start", "2020-01-01"))
    end = datetime.fromisoformat(window.get("end", "2023-01-01"))
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
    from app.modules.data.providers import SampleDataProvider
    from datetime import datetime

    spec_raw = kwargs.get("spec", {})
    parse_result = parse_spec(spec_raw)
    if not parse_result.success:
        return {"strategy_version_id": strategy_version_id, "status": "failed"}

    provider = SampleDataProvider()
    ticker = parse_result.spec.tickers[0] if parse_result.spec.tickers else "AAPL"
    bars = await provider.bars(ticker, datetime(2018, 1, 1), datetime(2023, 1, 1))

    harness = ValidationHarnessImpl()
    report = await harness.validate(parse_result.spec, bars, n_eff=kwargs.get("n_eff", 1))
    return {
        "strategy_version_id": strategy_version_id,
        "status": "completed",
        "passed": report.passed,
        "dsr": report.deflated_sharpe,
        "pbo": report.pbo,
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
