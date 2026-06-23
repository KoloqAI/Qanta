from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.deps import DB, CurrentUser
from app import state
from app.schemas.library import BacktestBody

router = APIRouter()


@router.post("")
async def run_backtest(body: BacktestBody, db: DB, user: CurrentUser) -> dict:
    """Ad-hoc backtest endpoint (Backtest Sandbox).

    Source can be:
      - {"spec": {...}}                    — raw DSL spec
      - {"archetype_id": "...", "params": {...}} — library archetype + overrides
      - {"strategy_version_id": "..."}     — existing registry version

    Every run is logged to the search_ledger (it counts toward n_eff).
    Results can promote to Research/Registry but NEVER to live.
    """
    job_id = str(uuid.uuid4())
    spec_raw = _resolve_source(body.source)
    if spec_raw is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid source. Provide spec, archetype_id+params, or strategy_version_id.",
        )

    # Parse the spec through the DSL type-checker
    from app.core.dsl.parser import parse_spec

    parse_result = parse_spec(spec_raw)
    if not parse_result.success:
        return {
            "job_id": job_id,
            "status": "failed",
            "errors": [e.message for e in (parse_result.errors or [])],
        }

    # Override tickers if provided
    if body.tickers:
        parse_result.spec.tickers = body.tickers

    # Fetch bar data via the existing data provider
    from app.modules.data.providers import create_data_provider
    from datetime import datetime

    provider = create_data_provider()
    ticker = parse_result.spec.tickers[0] if parse_result.spec.tickers else "AAPL"
    start = datetime.fromisoformat(body.start)
    end = datetime.fromisoformat(body.end)
    bars = await provider.bars(ticker, start, end)

    # Run backtest using the existing custom Python Backtester
    from app.modules.backtest.service import BacktesterImpl, CostModel

    bt = BacktesterImpl()
    result = await bt.run(parse_result.spec, bars, CostModel())

    response = {
        "job_id": job_id,
        "status": "completed",
        "mode": body.mode,
        "ticker": ticker,
        "sharpe": result.sharpe,
        "max_drawdown": result.max_drawdown,
        "net_edge": result.net_edge,
        "frictionless_edge": result.frictionless_edge,
        "n_trades": result.n_trades,
        "win_rate": result.win_rate,
        "total_return": result.total_return,
        "equity_curve": result.equity_curve,
        "trades": [
            {
                "entry_date": t.entry_date,
                "exit_date": t.exit_date,
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl_net": t.pnl_net,
                "exit_reason": t.exit_reason,
            }
            for t in result.trades
        ],
    }

    # In full_gauntlet mode, also run validation
    if body.mode == "full_gauntlet":
        from app.modules.validation.service import ValidationHarnessImpl

        harness = ValidationHarnessImpl()
        val_report = await harness.validate(parse_result.spec, bars, n_eff=1)
        response["validation"] = {
            "passed": val_report.passed,
            "deflated_sharpe": val_report.deflated_sharpe,
            "pbo": val_report.pbo,
        }

    # Log to search ledger (every sandbox run counts toward n_eff)
    import hashlib, json

    spec_hash = hashlib.sha256(
        json.dumps(spec_raw, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]

    await state.audit_log.log(
        actor="user",
        action="sandbox_backtest",
        subject_type="backtest",
        subject_id=job_id,
        payload={
            "spec_hash": spec_hash,
            "ticker": ticker,
            "mode": body.mode,
            "sharpe": result.sharpe,
            "n_trades": result.n_trades,
        },
        user_id=user.get("id"),
    )

    return response


def _resolve_source(source: dict) -> dict | None:
    """Resolve a backtest source to a raw spec dict."""
    if "spec" in source:
        return source["spec"]

    if "archetype_id" in source:
        from app.api.library import _archetypes

        archetype = _archetypes.get(source["archetype_id"])
        if not archetype:
            return None
        template = dict(archetype.get("template", {}))
        params = source.get("params", {})
        template.update(params)
        return template

    if "strategy_version_id" in source:
        # Placeholder: look up from registry (in-memory for now)
        # Full DB lookup comes when services are wired to Postgres
        return None

    return None
