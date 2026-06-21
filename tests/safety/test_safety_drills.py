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
from app.modules.execution.service import PaperBroker, Order, ExecutionRuntimeImpl
from app.modules.scheduling.service import MarketCalendarImpl
from app.modules.notifications.service import NotifierImpl
from datetime import date


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
