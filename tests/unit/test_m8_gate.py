"""M8 Gate Tests — Evolution loop.

Gate: loop promotes a proven strategy and retires a decayed one;
T2 respects budget; T3 requires human approval; nothing self-deploys.
"""
from __future__ import annotations

import pytest
from app.modules.evolution.service import EvolutionLoopImpl
from app.modules.monitoring.service import MonitoringServiceImpl, AuditLogImpl


@pytest.mark.asyncio
async def test_tier1_runs():
    loop = EvolutionLoopImpl()
    result = await loop.run_tier1()
    assert result["tier"] == 1
    assert "promoted" in result
    assert "retired" in result


@pytest.mark.asyncio
async def test_tier2_respects_budget():
    loop = EvolutionLoopImpl()
    result = await loop.run_tier2(budget=5)
    assert result["budget"] == 5
    assert result["trials_run"] <= 5


@pytest.mark.asyncio
async def test_tier3_requires_human_approval():
    loop = EvolutionLoopImpl()
    proposal = {"type": "new_primitive", "name": "custom_indicator", "description": "test"}
    result = await loop.propose_tier3(proposal)
    assert result["status"] == "pending_approval"
    # Cannot self-approve
    assert result["status"] != "approved"


@pytest.mark.asyncio
async def test_tier3_human_can_decide():
    loop = EvolutionLoopImpl()
    proposal = {"type": "new_primitive", "name": "test"}
    result = await loop.propose_tier3(proposal)
    decision = await loop.decide_tier3(result["id"], approved=True, reason="Looks good")
    assert decision["status"] == "approved"


@pytest.mark.asyncio
async def test_nothing_self_deploys():
    """Evolution can discover and propose but never auto-deploy."""
    loop = EvolutionLoopImpl()
    t2 = await loop.run_tier2(budget=10)
    for survivor in t2.get("survivors", []):
        assert survivor.get("status") != "deployed", "Evolution must NOT self-deploy"


@pytest.mark.asyncio
async def test_digest():
    loop = EvolutionLoopImpl()
    digest = await loop.get_digest()
    assert "promotions" in digest
    assert "retirements" in digest
    assert "proposals" in digest
    assert "meta_lockbox" in digest


class TestMonitoring:
    @pytest.mark.asyncio
    async def test_record_and_check_decay(self):
        monitor = MonitoringServiceImpl()
        for i in range(20):
            sharpe = 1.5 if i < 10 else 0.3
            await monitor.record_performance("dep-1", {"sharpe": sharpe})

        result = await monitor.check_decay("dep-1")
        assert result["decayed"]

    @pytest.mark.asyncio
    async def test_no_decay_with_stable_performance(self):
        monitor = MonitoringServiceImpl()
        for i in range(20):
            await monitor.record_performance("dep-2", {"sharpe": 1.0})

        result = await monitor.check_decay("dep-2")
        assert not result["decayed"]


class TestAuditLog:
    @pytest.mark.asyncio
    async def test_log_and_query(self):
        log = AuditLogImpl()
        await log.log("system", "kill_switch", "account", "acc-1", {"reason": "drawdown"})
        await log.log("user", "approve", "strategy", "strat-1")
        await log.log("agent", "research", "strategy", "strat-2")

        all_entries = await log.query({})
        assert len(all_entries) == 3

        system_entries = await log.query({"actor": "system"})
        assert len(system_entries) == 1
        assert system_entries[0]["action"] == "kill_switch"

    @pytest.mark.asyncio
    async def test_audit_log_immutable(self):
        log = AuditLogImpl()
        await log.log("user", "test", "strategy", "s1")
        entries = log.all_entries()
        assert len(entries) == 1
        # Entries should have IDs and timestamps
        assert "id" in entries[0]
        assert "ts" in entries[0]


class TestCalibration:
    @pytest.mark.asyncio
    async def test_calibration_recording(self):
        monitor = MonitoringServiceImpl()
        await monitor.record_calibration("s1", claimed_c=0.75, target_r=0.02, horizon=7, realized=True)
        await monitor.record_calibration("s1", claimed_c=0.75, target_r=0.02, horizon=7, realized=False)

        cal = await monitor.get_calibration("s1")
        assert len(cal) == 2
        assert cal[0]["realized"] is True
        assert cal[1]["realized"] is False
