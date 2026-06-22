from __future__ import annotations

from typing import Any

from app.core.tools.base import Tool, Permission, ToolContext, ToolResult


class UniverseScanTool(Tool):
    name = "universe_scan"
    description = "Scan universe for candidate tickers matching criteria"
    permission = Permission.READ

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        from app.modules.data.providers import create_data_provider

        provider = create_data_provider()
        universe = await provider.universe()
        return ToolResult(success=True, data={"candidates": universe})


class TechnicalAnalysisTool(Tool):
    name = "technical_analysis"
    description = "Run technical analysis on a ticker using DSL features"
    permission = Permission.READ

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        from app.modules.data.providers import create_data_provider, recent_window
        from app.modules.data.features import FeatureComputer as fc

        ticker = args.get("ticker", "AAPL")
        provider = create_data_provider()
        start, end = recent_window(400)
        bars = await provider.bars(ticker, start, end)
        if bars.empty:
            return ToolResult(success=False, data={"error": "No data"})

        analysis = {
            "ticker": ticker,
            "bars": len(bars),
            "last_close": round(float(bars["close"].iloc[-1]), 2),
            "sma_20": round(float(fc.sma(bars["close"], 20).iloc[-1]), 2),
            "sma_50": round(float(fc.sma(bars["close"], 50).iloc[-1]), 2),
            "rsi_14": round(float(fc.rsi(bars["close"], 14).iloc[-1]), 2),
            "atr_14": round(float(fc.atr(bars["high"], bars["low"], bars["close"], 14).iloc[-1]), 2),
            "realized_vol_20": round(float(fc.realized_vol(bars["close"], 20).iloc[-1]), 4),
        }
        return ToolResult(success=True, data=analysis)


class CharacterizeTickerTool(Tool):
    name = "characterize_ticker"
    description = "Build a regime/behavior profile for a ticker"
    permission = Permission.READ

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        from app.modules.data.providers import create_data_provider, recent_window
        from app.modules.data.features import FeatureComputer as fc
        import numpy as np

        ticker = args.get("ticker", "AAPL")
        provider = create_data_provider()
        start, end = recent_window(700)
        bars = await provider.bars(ticker, start, end)
        if bars.empty:
            return ToolResult(success=False, data={"error": "No data"})

        returns = np.log(bars["close"] / bars["close"].shift(1)).dropna()
        profile = {
            "ticker": ticker,
            "mean_return": round(float(returns.mean()) * 252, 4),
            "annual_vol": round(float(returns.std()) * np.sqrt(252), 4),
            "skew": round(float(returns.skew()), 4),
            "kurtosis": round(float(returns.kurtosis()), 4),
            "avg_volume": round(float(bars["volume"].mean()), 0),
            "price_range": [
                round(float(bars["close"].min()), 2),
                round(float(bars["close"].max()), 2),
            ],
        }
        return ToolResult(success=True, data=profile)


class AuthorStrategyTool(Tool):
    name = "author_strategy"
    description = "Compose a DSL strategy spec from a thesis and intent"
    permission = Permission.READ

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        thesis = args.get("thesis", "")
        ticker = args.get("ticker", "AAPL")

        spec = {
            "id": "",
            "version": 1,
            "tickers": [ticker],
            "thesis": thesis,
            "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
            "entry": {
                "when": {"crosses_above": ["sma(20)", "sma(50)"]},
                "action": "enter_long",
                "sizing": {"fixed_pct": 5.0},
            },
            "exits": [
                {"stop_loss": {"pct": 3.0}},
                {"take_profit": {"pct": 6.0}},
                {"time_stop": {"sessions": 10}},
            ],
            "risk": {
                "max_position_pct": 5.0,
                "per_trade_stop_pct": 3.0,
                "max_gross_exposure": 40.0,
            },
            "universe": {"primary": ticker},
            "validation": {"targets": [{"R": 0.02, "H": 7}]},
        }
        return ToolResult(success=True, data={"spec": spec})


class BacktestTool(Tool):
    name = "backtest"
    description = "Run backtest on a strategy spec"
    permission = Permission.READ

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        from app.core.dsl.parser import parse_spec
        from app.modules.backtest.service import BacktesterImpl
        from app.modules.data.providers import create_data_provider, recent_window

        spec_raw = args.get("spec", {})
        result = parse_spec(spec_raw)
        if not result.success:
            return ToolResult(
                success=False,
                data={"errors": [e.message for e in (result.errors or [])]},
            )

        provider = create_data_provider()
        ticker = result.spec.tickers[0] if result.spec.tickers else "AAPL"
        start, end = recent_window(700)
        bars = await provider.bars(ticker, start, end)

        bt = BacktesterImpl()
        bt_result = await bt.run(result.spec, bars)
        return ToolResult(
            success=True,
            data={
                "sharpe": bt_result.sharpe,
                "max_drawdown": bt_result.max_drawdown,
                "net_edge": bt_result.net_edge,
                "frictionless_edge": bt_result.frictionless_edge,
                "n_trades": bt_result.n_trades,
                "win_rate": bt_result.win_rate,
            },
        )


class ValidateTool(Tool):
    name = "validate"
    description = "Run the full validation gauntlet on a strategy spec"
    permission = Permission.READ

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        from app.core.dsl.parser import parse_spec
        from app.modules.validation.service import ValidationHarnessImpl
        from app.modules.data.providers import create_data_provider, recent_window

        spec_raw = args.get("spec", {})
        parse_result = parse_spec(spec_raw)
        if not parse_result.success:
            return ToolResult(
                success=False,
                data={"errors": [e.message for e in (parse_result.errors or [])]},
            )

        provider = create_data_provider()
        ticker = parse_result.spec.tickers[0] if parse_result.spec.tickers else "AAPL"
        start, end = recent_window(700)
        bars = await provider.bars(ticker, start, end)

        harness = ValidationHarnessImpl()
        report = await harness.validate(parse_result.spec, bars, n_eff=args.get("n_eff", 1))
        return ToolResult(
            success=True,
            data={
                "passed": report.passed,
                "deflated_sharpe": report.deflated_sharpe,
                "pbo": report.pbo,
                "confidence_curve": report.confidence_curve,
            },
        )


class QueryBookTool(Tool):
    name = "query_book"
    description = "Query current portfolio/positions/exposure"
    permission = Permission.READ

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        from app import state

        positions = await state.broker.positions()
        gross_exposure = sum(
            abs(p.get("qty", 0)) * 100 for p in positions
        )
        return ToolResult(
            success=True,
            data={
                "equity": state.INITIAL_EQUITY,
                "positions": positions,
                "gross_exposure": gross_exposure,
                "daily_pnl": 0,
            },
        )


class PauseDeploymentTool(Tool):
    name = "pause_deployment"
    description = "Pause an active deployment"
    permission = Permission.RISK_REDUCING

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        from app import state

        deployment_id = args.get("deployment_id", "")
        if deployment_id not in state.deployments:
            return ToolResult(
                success=False,
                error=f"Deployment {deployment_id} not found",
            )

        await state.runtime.stop(deployment_id)
        state.deployments[deployment_id]["status"] = "paused"

        await state.audit_log.log(
            actor="assistant",
            action="deployment_paused",
            subject_type="deployment",
            subject_id=deployment_id,
            user_id=ctx.user_id,
        )

        return ToolResult(
            success=True,
            data={"deployment_id": deployment_id, "status": "paused"},
        )


class FlattenDeploymentTool(Tool):
    name = "flatten_deployment"
    description = "Flatten all positions for a deployment"
    permission = Permission.RISK_REDUCING

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        from app import state

        deployment_id = args.get("deployment_id", "")
        if deployment_id not in state.deployments:
            return ToolResult(
                success=False,
                error=f"Deployment {deployment_id} not found",
            )

        await state.broker.flatten_all()
        state.deployments[deployment_id]["status"] = "flattened"

        await state.audit_log.log(
            actor="assistant",
            action="deployment_flattened",
            subject_type="deployment",
            subject_id=deployment_id,
            user_id=ctx.user_id,
        )

        return ToolResult(
            success=True,
            data={"deployment_id": deployment_id, "status": "flattened"},
        )


class DeployStrategyTool(Tool):
    name = "deploy_strategy"
    description = "Deploy a strategy (STAGED -- requires human confirmation)"
    permission = Permission.RISK_INCREASING

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(
            success=False,
            data={"error": "Must be staged and confirmed by human"},
        )


class ApproveStrategyTool(Tool):
    name = "approve_strategy"
    description = "Approve a strategy (STAGED -- requires human confirmation)"
    permission = Permission.RISK_INCREASING

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(
            success=False,
            data={"error": "Must be staged and confirmed by human"},
        )


def register_all_tools(registry) -> None:
    """Register all tools in the catalog."""
    tools = [
        UniverseScanTool(),
        TechnicalAnalysisTool(),
        CharacterizeTickerTool(),
        AuthorStrategyTool(),
        BacktestTool(),
        ValidateTool(),
        QueryBookTool(),
        PauseDeploymentTool(),
        FlattenDeploymentTool(),
        DeployStrategyTool(),
        ApproveStrategyTool(),
    ]
    for tool in tools:
        registry.register(tool)
