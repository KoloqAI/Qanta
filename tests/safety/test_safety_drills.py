"""M5 Safety Drills -- acceptance gate tests for execution + guardrails.

Drills from docs/06:
1. Stop-loss triggers and closes a position
2. Over-size order rejected + logged
3. Gross exposure cap rejects
4. Portfolio aggregate cap rejects
5. Kill-switch flattens all + halts
6. Live deploy without ValidationReport + Approval is refused
7. PDT block fires when intraday + <$25k
8. Broker-resident stop survives engine kill (paper mode)
9. EOD flatten for intraday
"""
from __future__ import annotations

import pytest
from app.modules.risk.service import RiskGateImpl, BookState, RiskDecision
from app.modules.portfolio.service import PortfolioRiskGateImpl, AllocatorImpl
from app.modules.execution.service import PaperBroker, Order, ExecutionRuntimeImpl, DeploymentGateError
from app.modules.scheduling.service import MarketCalendarImpl, EODFlattenJob
from app.modules.notifications.service import NotifierImpl
from app.modules.registry.service import StrategyRegistryImpl
from datetime import date, datetime


class TestStopLoss:
    def test_order_without_stop_rejected(self):
        gate = RiskGateImpl()
        book = BookState(equity=100_000, positions=[], daily_pnl=0, gross_exposure=0)
        order = {"symbol": "AAPL", "side": "buy", "qty": 10, "price": 150}
        decision = gate.check(order, book)
        assert not decision.allowed
        assert "stop" in decision.reason.lower()

    def test_order_with_stop_allowed(self):
        gate = RiskGateImpl()
        book = BookState(equity=100_000, positions=[], daily_pnl=0, gross_exposure=0)
        order = {"symbol": "AAPL", "side": "buy", "qty": 10, "price": 150,
                 "bracket_stop": 145.0}
        decision = gate.check(order, book)
        assert decision.allowed


class TestPositionSizing:
    def test_oversize_order_rejected(self):
        gate = RiskGateImpl(max_position_pct=10.0)
        book = BookState(equity=100_000, positions=[], daily_pnl=0, gross_exposure=0)
        order = {"symbol": "AAPL", "side": "buy", "qty": 100, "price": 150,
                 "bracket_stop": 145.0}
        decision = gate.check(order, book)
        assert not decision.allowed
        assert "size" in decision.reason.lower() or "exceeds" in decision.reason.lower()


class TestGrossExposure:
    def test_gross_exposure_cap_rejects(self):
        gate = PortfolioRiskGateImpl(max_gross_exposure_pct=50.0)
        portfolio = {"equity": 100_000, "gross_exposure": 45_000, "symbol_exposures": {}, "active_strategies": 1}
        order = {"symbol": "AAPL", "side": "buy", "qty": 100, "price": 150}
        result = gate.check(order, portfolio)
        assert not result["allowed"]
        assert "exposure" in result["reason"].lower()


class TestPortfolioAggregate:
    def test_per_symbol_cap_rejects(self):
        gate = PortfolioRiskGateImpl(per_symbol_cap_pct=20.0)
        portfolio = {
            "equity": 100_000,
            "gross_exposure": 10_000,
            "symbol_exposures": {"AAPL": 18_000},
            "active_strategies": 1,
        }
        order = {"symbol": "AAPL", "side": "buy", "qty": 30, "price": 150}
        result = gate.check(order, portfolio)
        assert not result["allowed"]
        assert "AAPL" in result["reason"]

    def test_max_strategies_rejects(self):
        gate = PortfolioRiskGateImpl(max_strategies=3)
        portfolio = {
            "equity": 100_000,
            "gross_exposure": 10_000,
            "symbol_exposures": {},
            "active_strategies": 3,
        }
        order = {"symbol": "TSLA", "side": "buy", "qty": 5, "price": 200}
        result = gate.check(order, portfolio)
        assert not result["allowed"]
        assert "strategies" in result["reason"].lower()


class TestKillSwitch:
    def test_daily_drawdown_triggers_kill(self):
        gate = RiskGateImpl(daily_drawdown_kill_pct=5.0)
        book = BookState(equity=100_000, positions=[], daily_pnl=-5_500, gross_exposure=0)
        order = {"symbol": "AAPL", "side": "buy", "qty": 1, "price": 150, "bracket_stop": 145}
        decision = gate.check(order, book)
        assert not decision.allowed
        assert gate.is_killed

    def test_kill_switch_blocks_all_subsequent(self):
        gate = RiskGateImpl()
        gate.trigger_kill_switch()
        book = BookState(equity=100_000, positions=[], daily_pnl=0, gross_exposure=0)
        order = {"symbol": "AAPL", "side": "buy", "qty": 1, "price": 150, "bracket_stop": 145}
        decision = gate.check(order, book)
        assert not decision.allowed
        assert "kill" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_flatten_all_on_kill(self):
        broker = PaperBroker()
        await broker.submit(Order("AAPL", "buy", 10, "market", bracket_stop=145.0))
        await broker.submit(Order("MSFT", "buy", 20, "market", bracket_stop=290.0))
        positions = await broker.positions()
        assert len(positions) >= 1
        await broker.flatten_all()
        positions = await broker.positions()
        assert len(positions) == 0


class TestPDT:
    def test_pdt_block_fires(self):
        gate = RiskGateImpl(pdt_equity_minimum=25_000)
        book = BookState(equity=20_000, positions=[], daily_pnl=0, gross_exposure=0)
        order = {"symbol": "AAPL", "side": "buy", "qty": 1, "price": 150,
                 "bracket_stop": 145.0, "horizon_mode": "intraday"}
        decision = gate.check(order, book)
        assert not decision.allowed
        assert "PDT" in decision.reason or "25,000" in decision.reason

    def test_pdt_passes_with_sufficient_equity(self):
        gate = RiskGateImpl(pdt_equity_minimum=25_000)
        book = BookState(equity=30_000, positions=[], daily_pnl=0, gross_exposure=0)
        order = {"symbol": "AAPL", "side": "buy", "qty": 1, "price": 150,
                 "bracket_stop": 145.0, "horizon_mode": "intraday"}
        decision = gate.check(order, book)
        assert decision.allowed


class TestMarketCalendar:
    def test_weekend_not_trading_day(self):
        cal = MarketCalendarImpl()
        assert not cal.is_trading_day(date(2024, 12, 7))  # Saturday
        assert not cal.is_trading_day(date(2024, 12, 8))  # Sunday

    def test_holiday_not_trading_day(self):
        cal = MarketCalendarImpl()
        assert not cal.is_trading_day(date(2024, 12, 25))  # Christmas

    def test_regular_day_is_trading(self):
        cal = MarketCalendarImpl()
        assert cal.is_trading_day(date(2024, 12, 9))  # Monday

    def test_next_trading_day_skips_weekend(self):
        cal = MarketCalendarImpl()
        friday = date(2024, 12, 6)
        assert cal.next_trading_day(friday) == date(2024, 12, 9)


class TestAllocator:
    def test_fixed_fraction_allocation(self):
        alloc = AllocatorImpl(cash_buffer_pct=10.0, max_strategies=10)
        deployments = [{"id": "d1"}, {"id": "d2"}, {"id": "d3"}]
        result = alloc.allocate(deployments, equity=100_000)
        assert len(result) == 3
        total = sum(result.values())
        assert total <= 90_000 + 1  # 10% cash buffer

    def test_max_strategies_capped(self):
        alloc = AllocatorImpl(max_strategies=2)
        deployments = [{"id": "d1"}, {"id": "d2"}, {"id": "d3"}, {"id": "d4"}]
        result = alloc.allocate(deployments, equity=100_000)
        assert len(result) == 2


class TestPaperBroker:
    @pytest.mark.asyncio
    async def test_submit_and_positions(self):
        broker = PaperBroker()
        ack = await broker.submit(Order("AAPL", "buy", 10, "market"))
        assert ack.status == "filled"
        positions = await broker.positions()
        assert any(p["symbol"] == "AAPL" for p in positions)

    @pytest.mark.asyncio
    async def test_reconcile(self):
        broker = PaperBroker()
        await broker.submit(Order("AAPL", "buy", 10, "market"))
        rec = await broker.reconcile()
        assert rec["status"] == "ok"


class TestOrderFlow:
    @pytest.mark.asyncio
    async def test_full_order_flow(self):
        risk = RiskGateImpl()
        portfolio_gate = PortfolioRiskGateImpl()
        broker = PaperBroker()
        runtime = ExecutionRuntimeImpl(broker, risk, portfolio_gate)

        book = BookState(equity=100_000, positions=[], daily_pnl=0, gross_exposure=0)
        portfolio = {"equity": 100_000, "gross_exposure": 0, "symbol_exposures": {}, "active_strategies": 1}
        order = Order("AAPL", "buy", 5, "market", bracket_stop=145.0)
        ack = await runtime.submit_order(order, book, portfolio)
        assert ack.status == "filled"

    @pytest.mark.asyncio
    async def test_rejected_order_no_stop(self):
        risk = RiskGateImpl()
        portfolio_gate = PortfolioRiskGateImpl()
        broker = PaperBroker()
        runtime = ExecutionRuntimeImpl(broker, risk, portfolio_gate)

        book = BookState(equity=100_000, positions=[], daily_pnl=0, gross_exposure=0)
        portfolio = {"equity": 100_000, "gross_exposure": 0, "symbol_exposures": {}, "active_strategies": 1}
        order = Order("AAPL", "buy", 5, "market")
        ack = await runtime.submit_order(order, book, portfolio)
        assert ack.status == "rejected"
        assert "RiskGate" in ack.message


class TestDeploymentGate:
    """Drill 6: Live deploy without ValidationReport + Approval is refused."""

    @pytest.mark.asyncio
    async def test_live_deploy_without_validation_refused(self):
        """A live deployment for a strategy with no approval/validation must be refused."""
        registry = StrategyRegistryImpl()
        # Create a strategy that is still in draft status (not approved)
        strategy = await registry.create(
            {"thesis": "Test momentum", "tickers": ["AAPL"]},
            user_id="user-001",
        )
        strategy_id = strategy["id"]

        broker = PaperBroker()
        risk_gate = RiskGateImpl()
        portfolio_gate = PortfolioRiskGateImpl()
        runtime = ExecutionRuntimeImpl(broker, risk_gate, portfolio_gate, registry=registry)

        with pytest.raises(DeploymentGateError):
            await runtime.start(
                "deploy-001",
                deployment_info={"mode": "live", "strategy_id": strategy_id},
            )

        # Verify deployment was NOT activated
        assert "deploy-001" not in runtime._active

    @pytest.mark.asyncio
    async def test_paper_deploy_always_allowed(self):
        """Paper deployments are always allowed regardless of validation status."""
        broker = PaperBroker()
        risk_gate = RiskGateImpl()
        portfolio_gate = PortfolioRiskGateImpl()
        runtime = ExecutionRuntimeImpl(broker, risk_gate, portfolio_gate)

        # Paper mode via deployment_info
        await runtime.start(
            "deploy-002",
            deployment_info={"mode": "paper", "strategy_id": "any-strategy"},
        )
        assert runtime._active.get("deploy-002") is True

        # No deployment_info at all (backward-compatible path)
        await runtime.start("deploy-003")
        assert runtime._active.get("deploy-003") is True

    @pytest.mark.asyncio
    async def test_live_deploy_with_approval_succeeds(self):
        """A live deployment for an approved strategy must succeed."""
        registry = StrategyRegistryImpl()
        strategy = await registry.create(
            {"thesis": "Approved momentum", "tickers": ["MSFT"]},
            user_id="user-002",
        )
        strategy_id = strategy["id"]

        # Simulate human approval by setting status to "approved"
        registry._strategies[strategy_id]["status"] = "approved"

        broker = PaperBroker()
        risk_gate = RiskGateImpl()
        portfolio_gate = PortfolioRiskGateImpl()
        runtime = ExecutionRuntimeImpl(broker, risk_gate, portfolio_gate, registry=registry)

        # Should NOT raise
        await runtime.start(
            "deploy-004",
            deployment_info={"mode": "live", "strategy_id": strategy_id},
        )
        assert runtime._active.get("deploy-004") is True


class TestHaltDetection:
    """LULD halt detection: halted symbols are rejected, resumed symbols pass."""

    def test_halted_symbol_rejected(self):
        from app.modules.data.halts import HaltDetectorImpl

        halt = HaltDetectorImpl()
        halt.halt_symbol("AAPL", "LULD halt")
        gate = RiskGateImpl(halt_detector=halt)
        book = BookState(equity=100_000, positions=[], daily_pnl=0, gross_exposure=0)
        order = {"symbol": "AAPL", "side": "buy", "qty": 5, "price": 150, "bracket_stop": 145.0}
        decision = gate.check(order, book)
        assert not decision.allowed
        assert "halted" in decision.reason.lower()
        assert "LULD" in decision.reason

    def test_resumed_symbol_allowed(self):
        from app.modules.data.halts import HaltDetectorImpl

        halt = HaltDetectorImpl()
        halt.halt_symbol("AAPL", "LULD halt")
        halt.resume_symbol("AAPL")
        gate = RiskGateImpl(halt_detector=halt)
        book = BookState(equity=100_000, positions=[], daily_pnl=0, gross_exposure=0)
        order = {"symbol": "AAPL", "side": "buy", "qty": 5, "price": 150, "bracket_stop": 145.0}
        decision = gate.check(order, book)
        assert decision.allowed

    def test_non_halted_symbol_unaffected(self):
        from app.modules.data.halts import HaltDetectorImpl

        halt = HaltDetectorImpl()
        halt.halt_symbol("TSLA", "LULD halt")
        gate = RiskGateImpl(halt_detector=halt)
        book = BookState(equity=100_000, positions=[], daily_pnl=0, gross_exposure=0)
        order = {"symbol": "AAPL", "side": "buy", "qty": 5, "price": 150, "bracket_stop": 145.0}
        decision = gate.check(order, book)
        assert decision.allowed


class TestLockbox:
    """Validation lockbox: reserve final portion of data for OOS check."""

    @pytest.mark.asyncio
    async def test_lockbox_enforced(self):
        from app.core.dsl.schema import StrategySpec, RiskEnvelope
        from app.modules.data.providers import SampleDataProvider
        from app.modules.validation.service import ValidationHarnessImpl
        from datetime import datetime

        spec = StrategySpec(
            id="lockbox-test",
            version=1,
            tickers=["AAPL"],
            thesis="SMA crossover lockbox test",
            regime={"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
            entry={
                "when": {"crosses_above": ["sma(20)", "sma(50)"]},
                "action": "enter_long",
                "sizing": {"fixed_pct": {"pct": 5.0}},
            },
            exits=[{"stop_loss": {"pct": 3.0}}, {"take_profit": {"pct": 6.0}}],
            risk=RiskEnvelope(max_position_pct=10.0, per_trade_stop_pct=3.0, max_gross_exposure=40.0),
            universe={"primary": "AAPL"},
            validation={"targets": [{"R": 0.01, "H": 10}]},
        )

        provider = SampleDataProvider()
        bars = await provider.bars("AAPL", datetime(2018, 1, 1), datetime(2023, 1, 1))

        harness = ValidationHarnessImpl(
            dsr_threshold=0.0,
            pbo_threshold=1.0,
            min_trades=0,
            cost_edge_ratio=0.0,
            lockbox_pct=0.15,
        )
        report = await harness.validate_with_lockbox(spec, bars, n_eff=1)
        assert "lockbox" in report.detail

    def test_lockbox_split_covers_all_bars(self):
        """Research bars + lockbox bars = total bars."""
        import pandas as pd

        n_total = 1000
        lockbox_pct = 0.15
        bars = pd.DataFrame({"close": range(n_total)})

        lockbox_start = int(n_total * (1 - lockbox_pct))
        research_bars = bars.iloc[:lockbox_start]
        lockbox_bars = bars.iloc[lockbox_start:]

        assert len(research_bars) + len(lockbox_bars) == n_total
        assert len(lockbox_bars) == n_total - lockbox_start
        assert lockbox_start == 850


class TestEODFlatten:
    """Drill 9: EOD flatten closes all intraday positions before market close."""

    @pytest.mark.asyncio
    async def test_eod_flatten_fires_before_close(self):
        """Positions should be flattened when within the flatten window."""
        broker = PaperBroker()
        cal = MarketCalendarImpl()

        # Submit some positions
        await broker.submit(Order("AAPL", "buy", 10, "market", bracket_stop=145.0))
        await broker.submit(Order("MSFT", "buy", 20, "market", bracket_stop=290.0))
        positions = await broker.positions()
        assert len(positions) >= 1

        job = EODFlattenJob(broker, cal, flatten_minutes_before_close=5)

        # Use a known trading day: Monday Dec 9, 2024
        # Normal close is 4:00 PM, so 3 minutes before = 3:57 PM
        flatten_time = datetime(2024, 12, 9, 15, 57, 0)
        result = await job.check_and_flatten(current_time=flatten_time)

        assert result["flattened"] is True
        positions = await broker.positions()
        assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_eod_flatten_skips_outside_window(self):
        """Positions should NOT be flattened when outside the flatten window."""
        broker = PaperBroker()
        cal = MarketCalendarImpl()

        await broker.submit(Order("AAPL", "buy", 10, "market", bracket_stop=145.0))

        job = EODFlattenJob(broker, cal, flatten_minutes_before_close=5)

        # 2:00 PM on a trading day -- well outside the 3:55-4:00 PM window
        outside_time = datetime(2024, 12, 9, 14, 0, 0)
        result = await job.check_and_flatten(current_time=outside_time)

        assert result["flattened"] is False
        positions = await broker.positions()
        assert len(positions) == 1  # Position still held


class TestBracketOrders:
    """Drill 8: Broker-resident bracket orders survive independently."""

    @pytest.mark.asyncio
    async def test_bracket_stop_created_on_submit(self):
        """Submitting an order with bracket_stop creates an active stop bracket entry."""
        broker = PaperBroker()
        await broker.submit(Order("AAPL", "buy", 10, "market", bracket_stop=145.0))

        brackets = await broker.get_bracket_orders()
        assert len(brackets) == 1
        assert brackets[0]["type"] == "stop"
        assert brackets[0]["trigger_price"] == 145.0
        assert brackets[0]["status"] == "active"
        assert brackets[0]["side"] == "sell"  # Opposite of buy
        assert brackets[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_bracket_stop_triggers(self):
        """Stop bracket triggers when price drops below trigger for a long position."""
        broker = PaperBroker()
        await broker.submit(Order("AAPL", "buy", 10, "market", bracket_stop=145.0))

        # Verify position exists
        positions = await broker.positions()
        assert any(p["symbol"] == "AAPL" for p in positions)

        # Price drops to 144, below the 145 stop
        triggered = await broker.check_brackets({"AAPL": 144.0})
        assert len(triggered) == 1
        assert triggered[0]["type"] == "stop"
        assert triggered[0]["status"] == "triggered"

        # Position should be closed
        positions = await broker.positions()
        assert not any(p["symbol"] == "AAPL" for p in positions)

    @pytest.mark.asyncio
    async def test_bracket_survives_heartbeat_loss(self):
        """Bracket orders execute even when heartbeat is lost; new entries are blocked."""
        broker = PaperBroker()
        await broker.submit(Order("AAPL", "buy", 10, "market", bracket_stop=145.0))

        # Lose heartbeat
        broker.set_heartbeat(False)

        # New entries should be blocked
        ack = await broker.submit(Order("MSFT", "buy", 5, "market", bracket_stop=290.0))
        assert ack.status == "rejected"
        assert "Heartbeat lost" in ack.message

        # But bracket orders still fire
        triggered = await broker.check_brackets({"AAPL": 144.0})
        assert len(triggered) == 1
        assert triggered[0]["type"] == "stop"

        # Position should be closed despite heartbeat loss
        positions = await broker.positions()
        assert not any(p["symbol"] == "AAPL" for p in positions)

    @pytest.mark.asyncio
    async def test_bracket_tp_triggers(self):
        """Take-profit bracket triggers when price rises above trigger for a long position."""
        broker = PaperBroker()
        await broker.submit(Order("AAPL", "buy", 10, "market", bracket_tp=160.0))

        # Verify position exists
        positions = await broker.positions()
        assert any(p["symbol"] == "AAPL" for p in positions)

        # Price rises to 161, above the 160 TP
        triggered = await broker.check_brackets({"AAPL": 161.0})
        assert len(triggered) == 1
        assert triggered[0]["type"] == "tp"
        assert triggered[0]["status"] == "triggered"

        # Position should be closed
        positions = await broker.positions()
        assert not any(p["symbol"] == "AAPL" for p in positions)
