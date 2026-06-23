"""End-to-end exploration integration tests (Tasks 0-6).

Drives the real T2 pipeline: scan_universe → backtest(param grid) →
validate(competing_returns) across seed archetypes on the SampleDataProvider.

Verifies: archetype templates are used, param grids are swept, the
search_ledger is populated, deflation tightens as n_eff rises,
survivors are registered, staleness gate is server-enforced, and
the full run is deterministic.
"""
from __future__ import annotations

import copy
from datetime import datetime

import pytest

from app.modules.evolution.service import EvolutionLoopImpl
from app.modules.registry.library_loader import load_archetypes, _fill_placeholders, _extract_defaults
from app.modules.registry.service import StrategyRegistryImpl
from app.modules.monitoring.service import MonitoringServiceImpl
from app.modules.validation.service import ValidationHarnessImpl, GATES_VERSION
from app.modules.data.providers import create_data_provider, SampleDataProvider, scan_universe
from app.core.dsl.parser import parse_spec
from app.modules.backtest.service import BacktesterImpl


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SUBSET = ["rsi_reversion", "donchian_breakout", "zscore_reversion"]
BUDGET = 6
AS_OF = datetime(2024, 6, 1)
CANDIDATES_PER_ARCHETYPE = 2


@pytest.fixture
def registry():
    return StrategyRegistryImpl()


@pytest.fixture
def monitoring():
    return MonitoringServiceImpl()


@pytest.fixture
def evolution(monitoring, registry):
    return EvolutionLoopImpl(monitoring=monitoring, registry=registry)


# ---------------------------------------------------------------------------
# Task 0: Pre-flight
# ---------------------------------------------------------------------------


class TestPreflight:
    def test_sample_data_provider_active(self):
        provider = create_data_provider()
        assert isinstance(provider, SampleDataProvider)

    def test_archetypes_load_without_exclusions(self):
        archetypes = load_archetypes(validate=True)
        assert len(archetypes) >= 20
        for aid in SUBSET:
            assert aid in archetypes, f"{aid} not found"
            assert archetypes[aid]["status"] == "unexplored"

    def test_archetype_templates_parse_after_fill(self):
        archetypes = load_archetypes(validate=True)
        for aid in SUBSET:
            a = archetypes[aid]
            template = copy.deepcopy(a["template"])
            template["tickers"] = ["AAPL"]
            template.setdefault("universe", {})["primary"] = "AAPL"
            template.setdefault("validation", {"targets": [{"R": 0.02, "H": 7}]})
            defaults = _extract_defaults(a["param_grid"])
            filled = _fill_placeholders(template, defaults)
            result = parse_spec(filled)
            assert result.success, f"{aid} failed parse: {result.errors}"

    @pytest.mark.asyncio
    async def test_scan_returns_candidates(self):
        archetypes = load_archetypes(validate=True)
        a = archetypes["rsi_reversion"]
        result = await scan_universe(a, as_of=AS_OF)
        assert result["is_sample_fallback"] is True
        assert len(result["candidates"]) > 0


# ---------------------------------------------------------------------------
# Task 1: Run one bounded T2 cycle, capture the full funnel
# ---------------------------------------------------------------------------


class TestT2Cycle:
    @pytest.fixture(autouse=True)
    async def run_cycle(self, evolution):
        self.result = await evolution.run_tier2(
            budget=BUDGET,
            archetype_subset=SUBSET,
            as_of=AS_OF,
            candidates_per_archetype=CANDIDATES_PER_ARCHETYPE,
        )
        self.evolution = evolution

    def test_trials_run_within_budget(self):
        assert self.result["trials_run"] <= BUDGET
        assert self.result["trials_run"] > 0

    def test_ledger_populated(self):
        ledger = self.result["ledger"]
        assert len(ledger) > 0, "No ledger entries — pipeline didn't log trials"
        for entry in ledger:
            assert "spec_hash" in entry
            assert "hypothesis_family" in entry
            assert "archetype_id" in entry
            assert "ticker" in entry
            assert "n_configs_swept" in entry
            assert "n_configs_distinct" in entry
            assert entry["archetype_id"] in SUBSET

    def test_ledger_has_hypothesis_family(self):
        ledger = self.result["ledger"]
        families = {e["hypothesis_family"] for e in ledger}
        assert len(families) >= 1
        for f in families:
            assert f in ("mean_reversion", "momentum_trend")

    def test_n_configs_distinct_gt_1(self):
        ledger = self.result["ledger"]
        has_multi = any(e["n_configs_distinct"] > 1 for e in ledger)
        assert has_multi, "No trial used multi-config sweep — archetype grids not reaching backtest"

    def test_n_configs_swept_gt_1(self):
        ledger = self.result["ledger"]
        has_multi = any(e["n_configs_swept"] > 1 for e in ledger)
        assert has_multi, "No trial swept multiple configs — param grid not working"

    def test_families_seen_matches_archetypes(self):
        families = self.result["families_seen"]
        assert len(families) >= 1

    def test_is_sample_fallback(self):
        assert self.result["is_sample_fallback"] is True

    def test_instance_ledger_matches(self):
        assert len(self.evolution.get_ledger()) == len(self.result["ledger"])

    def test_n_eff_equals_trials_run(self):
        assert self.result["n_eff"] == self.result["trials_run"]


# ---------------------------------------------------------------------------
# Task 2: Verify deflation behaves as N grows
# ---------------------------------------------------------------------------


class TestDeflation:
    def test_dsr_bar_rises_with_n_eff(self):
        harness = ValidationHarnessImpl()
        sigma_sr = 1.0
        bar_1 = harness._expected_max_sharpe(1, sigma_sr)
        bar_3 = harness._expected_max_sharpe(3, sigma_sr)
        bar_10 = harness._expected_max_sharpe(10, sigma_sr)
        assert bar_1 == 0.0, "n_eff=1 should have zero expected max Sharpe"
        assert bar_3 > bar_1
        assert bar_10 > bar_3
        assert bar_10 > 1.0, f"With n_eff=10, bar should be substantial, got {bar_10}"

    @pytest.mark.asyncio
    async def test_n_eff_increments_per_family_not_per_config(self, evolution):
        result = await evolution.run_tier2(
            budget=BUDGET,
            archetype_subset=SUBSET,
            as_of=AS_OF,
            candidates_per_archetype=CANDIDATES_PER_ARCHETYPE,
        )
        n_eff = result["n_eff"]
        trials = result["trials_run"]
        assert n_eff == trials
        for entry in result["ledger"]:
            assert entry["n_configs_swept"] >= 1
            if entry["n_configs_swept"] > 1:
                assert n_eff < entry["n_configs_swept"] * trials, \
                    "n_eff should NOT count individual param configs"

    @pytest.mark.asyncio
    async def test_budget_cap_pauses_exploration(self, evolution):
        small_budget = 2
        result = await evolution.run_tier2(
            budget=small_budget,
            archetype_subset=SUBSET,
            as_of=AS_OF,
            candidates_per_archetype=5,
        )
        assert result["trials_run"] <= small_budget


# ---------------------------------------------------------------------------
# Task 3: Survivor surfacing + Review Queue + gates_version=3
# ---------------------------------------------------------------------------


class TestSurvivorSurfacing:
    @pytest.fixture(autouse=True)
    async def run_cycle(self, evolution, registry):
        self.result = await evolution.run_tier2(
            budget=BUDGET,
            archetype_subset=SUBSET,
            as_of=AS_OF,
            candidates_per_archetype=CANDIDATES_PER_ARCHETYPE,
        )
        self.evolution = evolution
        self.registry = registry

    def test_zero_survivors_is_honest_suppression(self):
        survivors = self.result["survivors"]
        ledger = self.result["ledger"]
        if len(survivors) == 0:
            validated = [e for e in ledger if e.get("validation_passed") is not None]
            assert len(validated) > 0, "No trials reached validation"
            all_failed = all(not e["validation_passed"] for e in validated)
            assert all_failed
            all_have_reason = all(len(e["failed_gates"]) > 0 for e in validated)
            assert all_have_reason, "Suppressed trials missing failure reasons"

    def test_survivors_have_gates_version_3(self):
        for s in self.result["survivors"]:
            assert s["gates_version"] == 3

    @pytest.mark.asyncio
    async def test_survivors_registered_in_registry(self):
        strategies = await self.registry.list_all({})
        for s in self.result["survivors"]:
            if s.get("strategy_id"):
                found = any(st["id"] == s["strategy_id"] for st in strategies)
                assert found, f"Survivor {s['strategy_id']} not in registry"

    @pytest.mark.asyncio
    async def test_digest_reflects_run(self):
        digest = await self.evolution.get_digest()
        assert digest["n_eff"] == self.result["n_eff"]
        assert len(digest["discoveries"]) == len(self.result["survivors"])
        assert digest["ledger_count"] == len(self.result["ledger"])


# ---------------------------------------------------------------------------
# Task 5: Staleness gate is server-enforced (not just UI)
# ---------------------------------------------------------------------------


class TestStalenessGate:
    @pytest.mark.asyncio
    async def test_approve_rejects_stale_report(self, client):
        from app import state

        await client.post("/auth/register", json={
            "email": "stale@test.com", "password": "TestPass123!"
        })
        login = await client.post("/auth/login", json={
            "email": "stale@test.com", "password": "TestPass123!"
        })
        csrf = login.cookies.get("csrf_token", "")

        spec = {
            "id": "", "version": 1, "tickers": ["AAPL"],
            "thesis": "Test staleness",
            "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
            "entry": {"when": {"crosses_above": ["sma(20)", "sma(50)"]},
                      "action": "enter_long", "sizing": {"fixed_pct": 5.0}},
            "exits": [{"stop_loss": {"pct": 3.0}}, {"take_profit": {"pct": 6.0}}],
            "risk": {"max_position_pct": 5.0, "per_trade_stop_pct": 3.0,
                     "max_gross_exposure": 40.0},
            "universe": {"primary": "AAPL"},
            "validation": {"targets": [{"R": 0.02, "H": 7}]},
        }
        strategy = await state.registry.create(spec, "test-user")
        sid = strategy["id"]

        state.validation_reports[sid] = {
            "passed": True,
            "dsr": 0.98,
            "pbo": 0.10,
            "peer_hit": 0.70,
            "gates_version": 2,
            "sharpe": 1.5,
            "net_edge": 0.05,
            "n_trades": 200,
            "confidence_curve": [],
        }

        resp = await client.post(
            f"/strategies/{sid}/approve",
            json={"approved": True, "reason": "test"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        body = resp.json()
        assert "stale" in body["detail"].lower() or "gates_version" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_approve_succeeds_with_current_gates(self, client):
        from app import state

        await client.post("/auth/register", json={
            "email": "current@test.com", "password": "TestPass123!"
        })
        login = await client.post("/auth/login", json={
            "email": "current@test.com", "password": "TestPass123!"
        })
        csrf = login.cookies.get("csrf_token", "")

        spec = {
            "id": "", "version": 1, "tickers": ["MSFT"],
            "thesis": "Test current gates",
            "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
            "entry": {"when": {"crosses_above": ["sma(20)", "sma(50)"]},
                      "action": "enter_long", "sizing": {"fixed_pct": 5.0}},
            "exits": [{"stop_loss": {"pct": 3.0}}, {"take_profit": {"pct": 6.0}}],
            "risk": {"max_position_pct": 5.0, "per_trade_stop_pct": 3.0,
                     "max_gross_exposure": 40.0},
            "universe": {"primary": "MSFT"},
            "validation": {"targets": []},
        }
        strategy = await state.registry.create(spec, "test-user")
        sid = strategy["id"]

        state.validation_reports[sid] = {
            "passed": True,
            "dsr": 0.98,
            "pbo": 0.10,
            "peer_hit": 0.70,
            "gates_version": GATES_VERSION,
            "sharpe": 1.5,
            "net_edge": 0.05,
            "n_trades": 200,
            "confidence_curve": [],
        }

        resp = await client.post(
            f"/strategies/{sid}/approve",
            json={"approved": True, "reason": "test"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Task 6: Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    @pytest.mark.asyncio
    async def test_two_runs_produce_identical_results(self):
        reg1 = StrategyRegistryImpl()
        mon1 = MonitoringServiceImpl()
        evo1 = EvolutionLoopImpl(monitoring=mon1, registry=reg1)
        r1 = await evo1.run_tier2(
            budget=3,
            archetype_subset=["rsi_reversion", "donchian_breakout"],
            as_of=AS_OF,
            candidates_per_archetype=1,
        )

        reg2 = StrategyRegistryImpl()
        mon2 = MonitoringServiceImpl()
        evo2 = EvolutionLoopImpl(monitoring=mon2, registry=reg2)
        r2 = await evo2.run_tier2(
            budget=3,
            archetype_subset=["rsi_reversion", "donchian_breakout"],
            as_of=AS_OF,
            candidates_per_archetype=1,
        )

        assert r1["trials_run"] == r2["trials_run"]
        assert r1["n_eff"] == r2["n_eff"]
        assert len(r1["ledger"]) == len(r2["ledger"])
        assert len(r1["survivors"]) == len(r2["survivors"])

        for e1, e2 in zip(r1["ledger"], r2["ledger"]):
            assert e1["spec_hash"] == e2["spec_hash"], "Spec hashes differ between runs"
            assert e1["hypothesis_family"] == e2["hypothesis_family"]
            assert e1["ticker"] == e2["ticker"]
            assert e1["n_configs_swept"] == e2["n_configs_swept"]
            assert e1["n_configs_distinct"] == e2["n_configs_distinct"]
            assert e1["winner_sharpe"] == e2["winner_sharpe"]
            assert e1["validation_passed"] == e2["validation_passed"]


# ---------------------------------------------------------------------------
# Task 4: Approve → Paper → Monitor (discovered strategy path)
# ---------------------------------------------------------------------------


class TestApproveDeployPath:
    @pytest.mark.asyncio
    async def test_discovered_strategy_through_approve_paper(self, client):
        from app import state

        registry = StrategyRegistryImpl()
        monitoring = MonitoringServiceImpl()
        evo = EvolutionLoopImpl(monitoring=monitoring, registry=registry)
        result = await evo.run_tier2(
            budget=BUDGET,
            archetype_subset=SUBSET,
            as_of=AS_OF,
            candidates_per_archetype=CANDIDATES_PER_ARCHETYPE,
        )

        all_strategies = await registry.list_all({})
        if not all_strategies:
            pytest.skip("No strategies registered — all trials failed parse/backtest")

        target = all_strategies[0]
        sid = target["id"]

        orig_registry = state.registry
        state.registry = registry
        state.validation_reports[sid] = {
            "passed": True,
            "dsr": 0.98,
            "pbo": 0.15,
            "peer_hit": 0.65,
            "gates_version": GATES_VERSION,
            "sharpe": 1.2,
            "net_edge": 0.04,
            "n_trades": 150,
            "confidence_curve": [],
        }

        try:
            await client.post("/auth/register", json={
                "email": "deploy@test.com", "password": "TestPass123!"
            })
            login = await client.post("/auth/login", json={
                "email": "deploy@test.com", "password": "TestPass123!"
            })
            csrf = login.cookies.get("csrf_token", "")

            resp = await client.post(
                f"/strategies/{sid}/approve",
                json={"approved": True, "reason": "Integration test"},
                headers={"X-CSRF-Token": csrf},
            )
            assert resp.status_code == 200, f"Approve failed: {resp.text}"
            assert resp.json()["detail"] == "approved"

            resp = await client.post(
                "/deployments",
                json={
                    "strategy_version_id": sid,
                    "mode": "paper",
                    "capital_budget": 10000,
                    "guardrails": {},
                },
                headers={"X-CSRF-Token": csrf},
            )
            assert resp.status_code == 200, f"Deploy failed: {resp.text}"
            dep = resp.json()
            assert dep["mode"] == "paper"
            assert dep["status"] == "active"

            audit_entries = state.audit_log._entries
            approve_entries = [e for e in audit_entries if e["action"] == "strategy_approved"]
            assert len(approve_entries) >= 1

            resp = await client.get("/deployments")
            deps = resp.json()
            assert any(d["id"] == dep["id"] for d in deps)
        finally:
            state.registry = orig_registry


# ---------------------------------------------------------------------------
# Integration bug regression: archetype template sizing
# ---------------------------------------------------------------------------


class TestArchetypeTemplateSizing:
    @pytest.mark.asyncio
    async def test_nested_fixed_pct_sizing(self):
        archetypes = load_archetypes(validate=True)
        a = archetypes["rsi_reversion"]
        template = copy.deepcopy(a["template"])
        template["tickers"] = ["AAPL"]
        template.setdefault("universe", {})["primary"] = "AAPL"
        template.setdefault("validation", {"targets": [{"R": 0.02, "H": 7}]})
        defaults = _extract_defaults(a["param_grid"])
        filled = _fill_placeholders(template, defaults)

        result = parse_spec(filled)
        assert result.success

        provider = SampleDataProvider()
        bars = await provider.bars("AAPL", datetime(2023, 1, 1), datetime(2024, 1, 1))
        bt = BacktesterImpl()
        bt_result = await bt.run(result.spec, bars)
        assert bt_result.n_trades >= 0

    @pytest.mark.asyncio
    async def test_nested_vol_scaled_sizing(self):
        archetypes = load_archetypes(validate=True)
        a = archetypes["donchian_breakout"]
        template = copy.deepcopy(a["template"])
        template["tickers"] = ["MSFT"]
        template.setdefault("universe", {})["primary"] = "MSFT"
        template.setdefault("validation", {"targets": [{"R": 0.02, "H": 7}]})
        defaults = _extract_defaults(a["param_grid"])
        filled = _fill_placeholders(template, defaults)

        result = parse_spec(filled)
        assert result.success

        provider = SampleDataProvider()
        bars = await provider.bars("MSFT", datetime(2023, 1, 1), datetime(2024, 1, 1))
        bt = BacktesterImpl()
        bt_result = await bt.run(result.spec, bars)
        assert bt_result.n_trades >= 0
