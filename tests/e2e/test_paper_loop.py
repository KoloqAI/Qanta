from __future__ import annotations

from datetime import datetime


class TestFullPaperLoop:
    """M7: propose -> validate -> review -> approve -> paper-trade -> monitor."""

    async def test_full_paper_loop(self):
        """End-to-end: propose -> validate -> approve -> paper-trade -> monitor."""
        from app.modules.research.service import ShortTermEquityDomain, StrategyAuthorImpl
        from app.core.dsl.parser import parse_spec
        from app.modules.backtest.service import BacktesterImpl
        from app.modules.validation.service import ValidationHarnessImpl
        from app.modules.data.providers import SampleDataProvider
        from app.modules.execution.service import (
            ExecutionRuntimeImpl,
            PaperBroker,
            Order,
        )
        from app.modules.risk.service import RiskGateImpl, BookState
        from app.modules.portfolio.service import PortfolioRiskGateImpl
        from app.modules.monitoring.service import MonitoringServiceImpl

        # 1. Scan for candidates
        domain = ShortTermEquityDomain()
        candidates = await domain.scan("short-term momentum", {})
        assert len(candidates) > 0
        ticker = candidates[0]["ticker"]

        # 2. Author a strategy spec
        author = StrategyAuthorImpl()
        spec_raw = await author.author(
            f"Momentum opportunity in {ticker}", {"ticker": ticker}
        )
        assert spec_raw["thesis"]
        assert spec_raw["tickers"] == [ticker]

        # 3. Parse and validate the spec
        parse_result = parse_spec(spec_raw)
        assert parse_result.success, (
            f"Parse failed: {[e.message for e in (parse_result.errors or [])]}"
        )
        spec = parse_result.spec

        # 4. Run backtest
        provider = SampleDataProvider()
        bars = await provider.bars(ticker, datetime(2019, 1, 1), datetime(2023, 1, 1))
        bt = BacktesterImpl()
        bt_result = await bt.run(spec, bars)
        assert bt_result.n_trades >= 0
        assert isinstance(bt_result.sharpe, float)

        # 5. Run validation harness
        harness = ValidationHarnessImpl()
        report = await harness.validate(spec, bars, n_eff=1)
        assert isinstance(report.passed, bool)
        assert isinstance(report.deflated_sharpe, float)
        assert isinstance(report.pbo, float)

        # 6. Simulate human approval
        approval_record = {
            "user_id": "test-user-001",
            "strategy_id": spec_raw.get("id", "test"),
            "approved": True,
            "reason": "Backtest looks good, validation passed",
            "ts": datetime.utcnow().isoformat(),
        }
        assert approval_record["approved"] is True

        # 7. Submit order through ExecutionRuntimeImpl with PaperBroker
        broker = PaperBroker()
        risk_gate = RiskGateImpl()
        portfolio_gate = PortfolioRiskGateImpl()
        runtime = ExecutionRuntimeImpl(broker, risk_gate, portfolio_gate)

        await runtime.start("deployment-001")

        order = Order(
            symbol=ticker,
            side="buy",
            qty=10,
            order_type="market",
            bracket_stop=bars["close"].iloc[-1] * 0.97,  # 3% stop
            bracket_tp=bars["close"].iloc[-1] * 1.06,     # 6% take profit
        )
        book = BookState(
            equity=100_000,
            positions=[],
            daily_pnl=0,
            gross_exposure=0,
        )
        portfolio = {
            "equity": 100_000,
            "gross_exposure": 0,
            "symbol_exposures": {},
            "active_strategies": 0,
        }
        ack = await runtime.submit_order(order, book, portfolio)
        assert ack.status == "filled"
        assert ack.order_id != ""

        # 8. Verify position exists
        positions = await broker.positions()
        assert len(positions) > 0
        assert any(p["symbol"] == ticker for p in positions)

        # 9. Record performance via MonitoringServiceImpl
        monitoring = MonitoringServiceImpl()
        await monitoring.record_performance("deployment-001", {
            "sharpe": bt_result.sharpe,
            "max_drawdown": bt_result.max_drawdown,
            "n_trades": bt_result.n_trades,
        })
        records = monitoring._performance.get("deployment-001", [])
        assert len(records) == 1
        assert "sharpe" in records[0]

    async def test_critical_event_fires_notification(self):
        """Kill switch triggers a critical notification."""
        from app.modules.risk.service import RiskGateImpl
        from app.modules.notifications.service import NotifierImpl

        # 1. Create risk gate and trigger the kill switch
        risk_gate = RiskGateImpl()
        assert not risk_gate.is_killed

        risk_gate.trigger_kill_switch()
        assert risk_gate.is_killed

        # 2. Send notification via NotifierImpl
        notifier = NotifierImpl()
        await notifier.send(
            event="kill_switch_activated",
            severity="critical",
            payload={
                "reason": "Manual kill switch triggered",
                "triggered_by": "test",
            },
        )

        # 3. Verify the notification was logged with severity="critical"
        log = notifier.get_log()
        assert len(log) == 1
        assert log[0]["event"] == "kill_switch_activated"
        assert log[0]["severity"] == "critical"
        assert log[0]["payload"]["reason"] == "Manual kill switch triggered"

        # Verify kill switch blocks further orders
        from app.modules.risk.service import BookState

        book = BookState(equity=100_000, positions=[], daily_pnl=0, gross_exposure=0)
        decision = risk_gate.check(
            {"symbol": "AAPL", "side": "buy", "qty": 10, "bracket_stop": 95.0},
            book,
        )
        assert not decision.allowed
        assert "Kill switch" in decision.reason

    async def test_assistant_stages_risk_increasing(self):
        """Agent tools exclude RISK_INCREASING; those actions must be staged."""
        from app.core.tools.base import ToolRegistry, Permission
        from app.core.tools.catalog import register_all_tools

        # 1. Create ToolRegistry and register all tools
        registry = ToolRegistry()
        register_all_tools(registry)

        all_tools = registry.list_tools()
        assert len(all_tools) == 11  # total tools in catalog

        # 2. Agent tools (READ + RISK_REDUCING) should NOT include deploy/approve
        agent_tools = registry.available_for_agent()
        agent_tool_names = {t.name for t in agent_tools}
        assert "deploy_strategy" not in agent_tool_names
        assert "approve_strategy" not in agent_tool_names

        # Verify READ and RISK_REDUCING tools are accessible
        assert "universe_scan" in agent_tool_names
        assert "backtest" in agent_tool_names
        assert "validate" in agent_tool_names
        assert "pause_deployment" in agent_tool_names
        assert "flatten_deployment" in agent_tool_names

        # 3. RISK_INCREASING tools exist in registry but not in agent toolkit
        risk_increasing_tools = registry.list_tools(permission=Permission.RISK_INCREASING)
        assert len(risk_increasing_tools) >= 2
        ri_names = {t.name for t in risk_increasing_tools}
        assert "deploy_strategy" in ri_names
        assert "approve_strategy" in ri_names

        # Confirm no overlap: RISK_INCREASING tools should not appear in agent tools
        for tool in risk_increasing_tools:
            assert tool.name not in agent_tool_names

        # 4. Simulate: when assistant encounters a deploy request, it returns
        #    a staged_action rather than executing directly
        deploy_tool = registry.get("deploy_strategy")
        assert deploy_tool is not None

        from app.core.tools.base import ToolContext

        ctx = ToolContext(user_id="test-user", session_id="test-session")
        result = await deploy_tool.invoke({"strategy_id": "strat-001"}, ctx)
        assert not result.success
        assert "staged" in result.data["error"].lower() or "human" in result.data["error"].lower()

    async def test_audit_log_captures_all(self):
        """All event types are captured and queryable in the audit log."""
        from app.modules.monitoring.service import AuditLogImpl

        # 1. Create AuditLogImpl
        audit = AuditLogImpl()

        # 2. Log a series of events covering the full lifecycle
        events = [
            ("system", "research_scan", "research_run", "run-001", {"goal": "momentum"}),
            ("system", "backtest_completed", "strategy_version", "sv-001", {"sharpe": 1.5}),
            ("system", "validation_completed", "strategy_version", "sv-001", {"passed": True, "dsr": 0.98}),
            ("user", "approved", "strategy_version", "sv-001", {"reason": "looks good"}),
            ("system", "order_submitted", "order", "ord-001", {"symbol": "AAPL", "side": "buy"}),
            ("system", "order_filled", "order", "ord-001", {"fill_price": 150.0, "qty": 10}),
            ("system", "order_rejected", "order", "ord-002", {"reason": "kill switch active"}),
        ]

        for actor, action, subject_type, subject_id, payload in events:
            await audit.log(
                actor=actor,
                action=action,
                subject_type=subject_type,
                subject_id=subject_id,
                payload=payload,
                user_id="test-user-001" if actor == "user" else None,
            )

        # 3. Verify all events are captured
        all_entries = audit.all_entries()
        assert len(all_entries) == 7

        # Each entry has required fields
        for entry in all_entries:
            assert "id" in entry
            assert "actor" in entry
            assert "action" in entry
            assert "subject_type" in entry
            assert "subject_id" in entry
            assert "ts" in entry
            assert "payload" in entry

        # 4. Query by actor
        system_events = await audit.query({"actor": "system"})
        assert len(system_events) == 6

        user_events = await audit.query({"actor": "user"})
        assert len(user_events) == 1
        assert user_events[0]["action"] == "approved"

        # Query by action
        fills = await audit.query({"action": "order_filled"})
        assert len(fills) == 1
        assert fills[0]["payload"]["fill_price"] == 150.0

        # Query by subject_type
        order_events = await audit.query({"subject_type": "order"})
        assert len(order_events) == 3

        strategy_events = await audit.query({"subject_type": "strategy_version"})
        assert len(strategy_events) == 3

        # Query by subject_id
        sv001_events = await audit.query({"subject_id": "sv-001"})
        assert len(sv001_events) == 3  # backtest, validation, approval

        # Query with combined filters
        system_orders = await audit.query({"actor": "system", "subject_type": "order"})
        assert len(system_orders) == 3

        rejected = await audit.query({"action": "order_rejected"})
        assert len(rejected) == 1
        assert rejected[0]["payload"]["reason"] == "kill switch active"
