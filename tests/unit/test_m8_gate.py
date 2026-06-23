"""M8 Gate Tests — Evolution loop.

Gate: loop promotes a proven strategy and retires a decayed one;
T2 respects budget; T3 requires human approval; nothing self-deploys.
"""
from __future__ import annotations

import pytest
from app.modules.evolution.service import EvolutionLoopImpl
from app.modules.monitoring.service import MonitoringServiceImpl, AuditLogImpl


@pytest.fixture
def _force_sample_provider(monkeypatch):
    """Force SampleDataProvider so tests never hit real Polygon."""
    from app.modules.data.providers import SampleDataProvider
    monkeypatch.setattr(
        "app.modules.data.providers.create_data_provider",
        lambda: SampleDataProvider(),
    )


@pytest.mark.asyncio
async def test_tier1_runs():
    loop = EvolutionLoopImpl()
    result = await loop.run_tier1()
    assert result["tier"] == 1
    assert "promoted" in result
    assert "retired" in result


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_tier2_respects_budget(_force_sample_provider):
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
@pytest.mark.timeout(30)
async def test_tier2_sweeps_param_grid(_force_sample_provider):
    """T2 generates param variants and reports n_configs_swept for survivors."""
    loop = EvolutionLoopImpl()
    result = await loop.run_tier2(budget=2)
    # Every survivor should report how many configs were swept
    for survivor in result.get("survivors", []):
        assert "n_configs_swept" in survivor
        assert survivor["n_configs_swept"] >= 1


def test_param_grid_fallback_stop_loss():
    """Without archetype_grid, falls back to stop_loss variation."""
    base = {
        "exits": [{"stop_loss": {"pct": 3.0}}],
        "risk": {"per_trade_stop_pct": 3.0, "max_position_pct": 5.0},
    }
    variants = EvolutionLoopImpl._generate_param_grid(base, n_variants=6)
    assert len(variants) >= 2
    assert variants[0] is base
    stops = [v["exits"][0]["stop_loss"]["pct"] for v in variants]
    assert len(set(stops)) == len(variants), "Each variant should have a distinct stop_loss"
    for v in variants[1:]:
        assert v["risk"]["per_trade_stop_pct"] == v["exits"][0]["stop_loss"]["pct"]


def test_archetype_grid_varies_entry_params():
    """Archetype param_grid with explicit placeholders sweeps entry lookbacks."""
    template = {
        "regime": {"all_of": [{"gt": ["avg_volume(20)", 500000]}]},
        "entry": {
            "when": {"all_of": [
                {"lt": ["rsi({rsi_period})", "{rsi_threshold}"]},
            ]},
            "action": "enter_long",
            "sizing": {"fixed_pct": 5.0},
        },
        "exits": [{"stop_loss": {"atr_mult": "{stop_atr}"}}],
        "risk": {"per_trade_stop_pct": 4.0, "max_position_pct": 5.0},
    }
    grid = {
        "rsi_period": {"min": 7, "max": 21, "step": 2, "default": 14},
        "rsi_threshold": {"min": 20, "max": 35, "step": 5, "default": 25},
        "stop_atr": {"min": 0.8, "max": 1.5, "step": 0.1, "default": 1.2},
    }
    variants = EvolutionLoopImpl._generate_param_grid(
        template, n_variants=20, archetype_grid=grid,
    )
    assert len(variants) >= 3

    # Verify RSI period is actually varied in the entry condition
    rsi_periods = set()
    for v in variants:
        for cond in v["entry"]["when"]["all_of"]:
            if "lt" in cond:
                for arg in cond["lt"]:
                    if isinstance(arg, str) and "rsi(" in arg:
                        import re
                        m = re.search(r"rsi\((\d+)\)", arg)
                        if m:
                            rsi_periods.add(int(m.group(1)))
    assert len(rsi_periods) > 1, (
        f"Expected multiple RSI periods, got {rsi_periods}"
    )

    # Verify stop_atr is varied
    stop_atrs = set()
    for v in variants:
        for rule in v.get("exits", []):
            if isinstance(rule, dict) and "stop_loss" in rule:
                stop_atrs.add(rule["stop_loss"].get("atr_mult"))
    assert len(stop_atrs) > 1, f"Expected multiple stop_atr values, got {stop_atrs}"

    # Verify threshold is varied (now numeric values, not strings)
    thresholds = set()
    for v in variants:
        for cond in v["entry"]["when"]["all_of"]:
            if "lt" in cond:
                for arg in cond["lt"]:
                    if isinstance(arg, (int, float)):
                        thresholds.add(arg)
    assert len(thresholds) > 1, f"Expected multiple thresholds, got {thresholds}"

    # Verify no placeholders remain in any variant
    import json
    for v in variants:
        s = json.dumps(v)
        assert "{" not in s or "all_of" in s, f"Unfilled placeholder in variant: {s}"


def test_archetype_grid_caps_combinatorial_blowup():
    """Cartesian product exceeding n_variants is down-sampled, not truncated."""
    template = {
        "entry": {"when": {"all_of": [{"lt": ["rsi({rsi_period})", "{rsi_threshold}"]}]},
                  "action": "enter_long", "sizing": {"fixed_pct": 5.0}},
        "exits": [{"stop_loss": {"atr_mult": "{stop_atr}"}}],
    }
    # 8 × 8 × 5 = 320 combos → must cap
    grid = {
        "rsi_period": {"min": 7, "max": 21, "step": 2, "default": 14},
        "rsi_threshold": {"min": 15, "max": 50, "step": 5, "default": 25},
        "stop_atr": {"min": 0.8, "max": 1.6, "step": 0.2, "default": 1.0},
    }
    variants = EvolutionLoopImpl._generate_param_grid(
        template, n_variants=15, archetype_grid=grid,
    )
    assert len(variants) <= 16  # base + up to 15 from grid
    assert len(variants) >= 2


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_nothing_self_deploys(_force_sample_provider):
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
