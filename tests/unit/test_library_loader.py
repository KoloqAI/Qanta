"""Test that all seed archetypes load and pass the DSL type-checker."""
from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

import pytest
import yaml

from app.modules.registry.library_loader import (
    load_archetypes, _build_template, _validate_template,
    _fill_placeholders, _extract_defaults, _validate_param_bindings,
    _validate_variant_distinctness, _validate_persistence_thesis,
    resolve_grid_values, LIBRARY_DIR,
)


class TestLibraryLoader:
    def test_all_archetypes_load(self):
        """Every YAML in config/library/ must load without errors."""
        archetypes = load_archetypes(validate=False)
        assert len(archetypes) >= 22, f"Expected >= 22 archetypes, got {len(archetypes)}"

    def test_all_archetypes_have_required_fields(self):
        archetypes = load_archetypes(validate=False)
        for aid, a in archetypes.items():
            assert a["name"], f"{aid}: missing name"
            assert a["family"], f"{aid}: missing family"
            assert a["horizon"], f"{aid}: missing horizon"
            assert a["thesis"], f"{aid}: missing thesis"
            assert a["template"], f"{aid}: missing template"
            assert a["scan"], f"{aid}: missing scan"
            assert a["param_grid"], f"{aid}: missing param_grid"

    def test_all_templates_pass_dsl_parser(self):
        """Every archetype template (after placeholder fill) must be a valid DSL spec."""
        archetypes = load_archetypes(validate=False)
        all_errors = []
        for aid, a in archetypes.items():
            template = a["template"]
            if a["param_grid"]:
                defaults = _extract_defaults(a["param_grid"])
                template = _fill_placeholders(template, defaults)
            errors = _validate_template(template, aid)
            all_errors.extend(errors)
        assert not all_errors, (
            f"{len(all_errors)} validation error(s):\n" + "\n".join(all_errors)
        )

    def test_all_families_represented(self):
        archetypes = load_archetypes(validate=False)
        families = {a["family"] for a in archetypes.values()}
        expected = {
            "mean_reversion", "momentum_trend", "volatility",
            "time_microstructure", "cross_sectional", "structural_filter",
        }
        assert expected.issubset(families), f"Missing families: {expected - families}"

    def test_stop_loss_required_in_every_template(self):
        archetypes = load_archetypes(validate=False)
        for aid, a in archetypes.items():
            exits = a["template"].get("exits", [])
            has_stop = any("stop_loss" in e for e in exits)
            assert has_stop, f"{aid}: template missing stop_loss exit"

    def test_regime_non_empty_in_every_template(self):
        archetypes = load_archetypes(validate=False)
        for aid, a in archetypes.items():
            regime = a["template"].get("regime", {})
            all_of = regime.get("all_of", [])
            assert len(all_of) > 0, f"{aid}: template regime.all_of is empty"

    def test_risk_within_guardrails(self):
        archetypes = load_archetypes(validate=False)
        for aid, a in archetypes.items():
            risk = a["template"].get("risk", {})
            assert risk.get("per_trade_stop_pct", 0) <= 5.0, f"{aid}: stop > 5%"
            assert risk.get("max_position_pct", 0) <= 10.0, f"{aid}: position > 10%"
            assert risk.get("max_gross_exposure", 0) <= 100.0, f"{aid}: exposure > 100%"


class TestParamBindings:
    """CI guard: every shipped YAML passes binding validation."""

    def test_all_param_bindings_valid(self):
        """Every param_grid key binds to a placeholder; every placeholder has a default."""
        for path in sorted(LIBRARY_DIR.glob("*.yaml")):
            with open(path) as f:
                raw = yaml.safe_load(f)
            template = _build_template(raw)
            grid = raw.get("param_grid", {})
            errors = _validate_param_bindings(template, grid, raw.get("id", path.stem))
            assert not errors, f"{path.stem}: {errors}"

    def test_all_variants_distinct(self):
        """No archetype produces duplicate variants from its grid."""
        for path in sorted(LIBRARY_DIR.glob("*.yaml")):
            with open(path) as f:
                raw = yaml.safe_load(f)
            template = _build_template(raw)
            grid = raw.get("param_grid", {})
            if not grid:
                continue
            errors = _validate_variant_distinctness(template, grid, raw.get("id", path.stem), n_sample=50)
            assert not errors, f"{path.stem}: {errors}"

    def test_all_filled_templates_pass_dsl(self):
        """Fill defaults → DSL type-check passes for every archetype."""
        from app.core.dsl.parser import parse_spec
        for path in sorted(LIBRARY_DIR.glob("*.yaml")):
            with open(path) as f:
                raw = yaml.safe_load(f)
            template = _build_template(raw)
            grid = raw.get("param_grid", {})
            if grid:
                defaults = _extract_defaults(grid)
                filled = _fill_placeholders(template, defaults)
            else:
                filled = template
            result = parse_spec(filled)
            assert result.success, f"{path.stem}: {[f'{e.field}: {e.message}' for e in (result.errors or [])]}"

    def test_malformed_archetype_excluded(self, caplog):
        """A grid key with no placeholder is excluded at load time."""
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        try:
            bad_yaml = {
                "id": "bad_test",
                "name": "Bad test",
                "family": "test",
                "horizon": "both",
                "thesis": "test",
                "watches": ["close"],
                "regime": {"all_of": [{"gt": ["avg_volume(20)", 500000]}]},
                "entry": {"when": {"all_of": [{"lt": ["rsi(14)", 30]}]},
                          "action": "enter_long", "sizing": {"fixed_pct": {"pct": 5.0}}},
                "exits": [{"stop_loss": {"atr_mult": 1.0}}],
                "risk": {"per_trade_stop_pct": 3.0, "max_position_pct": 5.0},
                "param_grid": {"ghost_param": {"min": 1, "max": 5, "step": 1, "default": 3}},
                "scan": {"all_of": [{"gt": ["avg_volume(20)", 500000]}]},
                "persistence_thesis": {
                    "edge_type": "behavioral",
                    "structural_reason": "Retail traders overreact to short-term extremes creating temporary mispricings.",
                    "forced_counterparty": "Algorithmic stop-loss cascades mechanically sell at oversold levels regardless of value.",
                    "death_condition": ["avg_volume(20) > capacity_ceiling_usd"],
                    "capacity_ceiling_usd": 20000000,
                    "monitorable_as_regime": True,
                },
            }
            bad_path = Path(tmp) / "bad_test.yaml"
            with open(bad_path, "w") as f:
                yaml.dump(bad_yaml, f)

            from app.modules.registry import library_loader
            orig_dir = library_loader.LIBRARY_DIR
            library_loader.LIBRARY_DIR = Path(tmp)
            try:
                with caplog.at_level(logging.ERROR):
                    archetypes = load_archetypes(validate=True)
                assert archetypes["bad_test"]["status"] == "excluded"
                assert "ghost_param" in archetypes["bad_test"]["exclusion_reason"]
                assert any("ghost_param" in r.message for r in caplog.records)
            finally:
                library_loader.LIBRARY_DIR = orig_dir
        finally:
            shutil.rmtree(tmp)

    def test_missing_default_excluded(self, caplog):
        """A grid entry without default is excluded at load time."""
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        try:
            bad_yaml = {
                "id": "no_default",
                "name": "No default",
                "family": "test",
                "horizon": "both",
                "thesis": "test",
                "watches": ["close"],
                "regime": {"all_of": [{"gt": ["avg_volume(20)", 500000]}]},
                "entry": {"when": {"all_of": [{"lt": ["rsi({rsi_period})", 30]}]},
                          "action": "enter_long", "sizing": {"fixed_pct": {"pct": 5.0}}},
                "exits": [{"stop_loss": {"atr_mult": 1.0}}],
                "risk": {"per_trade_stop_pct": 3.0, "max_position_pct": 5.0},
                "param_grid": {"rsi_period": {"min": 7, "max": 21, "step": 2}},
                "scan": {"all_of": [{"gt": ["avg_volume(20)", 500000]}]},
                "persistence_thesis": {
                    "edge_type": "behavioral",
                    "structural_reason": "Retail traders overreact to short-term extremes creating temporary mispricings.",
                    "forced_counterparty": "Algorithmic stop-loss cascades mechanically sell at oversold levels regardless of value.",
                    "death_condition": ["avg_volume(20) > capacity_ceiling_usd"],
                    "capacity_ceiling_usd": 20000000,
                    "monitorable_as_regime": True,
                },
            }
            bad_path = Path(tmp) / "no_default.yaml"
            with open(bad_path, "w") as f:
                yaml.dump(bad_yaml, f)

            from app.modules.registry import library_loader
            orig_dir = library_loader.LIBRARY_DIR
            library_loader.LIBRARY_DIR = Path(tmp)
            try:
                with caplog.at_level(logging.ERROR):
                    archetypes = load_archetypes(validate=True)
                assert archetypes["no_default"]["status"] == "excluded"
                assert "default" in archetypes["no_default"]["exclusion_reason"]
                assert any("default" in r.message for r in caplog.records)
            finally:
                library_loader.LIBRARY_DIR = orig_dir
        finally:
            shutil.rmtree(tmp)

    def test_int_period_no_float_leak(self):
        """Integer period params format as 'rsi(14)', never 'rsi(14.0)'."""
        template = {
            "entry": {"when": {"all_of": [{"lt": ["rsi({rsi_period})", "{threshold}"]}]}},
            "exits": [{"stop_loss": {"atr_mult": "{stop_atr}"}}],
        }
        grid = {
            "rsi_period": {"min": 7, "max": 21, "step": 2, "default": 14},
            "threshold": {"min": 20, "max": 35, "step": 5, "default": 25},
            "stop_atr": {"min": 0.8, "max": 1.5, "step": 0.1, "default": 1.2},
        }
        import itertools
        param_names = list(grid.keys())
        param_values = [resolve_grid_values(grid[k]) for k in param_names]
        for combo in itertools.product(*param_values):
            values = dict(zip(param_names, combo))
            filled = _fill_placeholders(template, values)
            s = json.dumps(filled)
            assert ".0)" not in s, f"Float leaked into period arg: {s}"
            assert ".0," not in s, f"Float leaked: {s}"
            # Pure-value placeholders: threshold should be int when whole
            threshold_val = filled["entry"]["when"]["all_of"][0]["lt"][1]
            if float(threshold_val) == int(float(threshold_val)):
                assert isinstance(threshold_val, int), (
                    f"Whole float not coerced to int: {threshold_val!r}"
                )

    def test_fractional_params_never_truncated(self):
        """Fractional stop multiplier 0.8 must survive binding, never become 0."""
        from app.modules.registry.library_loader import _coerce_numeric
        # Direct unit check on _coerce_numeric
        assert _coerce_numeric(0.8) == 0.8
        assert isinstance(_coerce_numeric(0.8), float)
        assert _coerce_numeric(14.0) == 14
        assert isinstance(_coerce_numeric(14.0), int)
        assert _coerce_numeric(7) == 7
        assert isinstance(_coerce_numeric(7), int)

        # End-to-end through _fill_placeholders
        template = {
            "exits": [{"stop_loss": {"atr_mult": "{stop_atr}"}},
                      {"take_profit": {"atr_mult": "{tp_atr}"}}],
        }
        filled = _fill_placeholders(template, {"stop_atr": 0.8, "tp_atr": 1.5})
        assert filled["exits"][0]["stop_loss"]["atr_mult"] == 0.8
        assert isinstance(filled["exits"][0]["stop_loss"]["atr_mult"], float)
        assert filled["exits"][1]["take_profit"]["atr_mult"] == 1.5
        assert isinstance(filled["exits"][1]["take_profit"]["atr_mult"], float)

        # Verify via resolve_grid_values → _fill_placeholders round-trip
        grid_vals = resolve_grid_values({"min": 0.5, "max": 1.0, "step": 0.1})
        for v in grid_vals:
            coerced = _coerce_numeric(v)
            if not v.is_integer():
                assert isinstance(coerced, float), f"{v} was truncated to {coerced!r}"
                assert abs(coerced - v) < 1e-9, f"{v} was changed to {coerced}"


def _valid_archetype_yaml() -> dict:
    """A complete archetype with a valid persistence_thesis for testing."""
    return {
        "id": "test_valid",
        "name": "Test valid archetype",
        "family": "mean_reversion",
        "horizon": "both",
        "thesis": "Test thesis for validation.",
        "watches": ["close", "rsi"],
        "regime": {"all_of": [{"gt": ["avg_volume(20)", 500000]}]},
        "entry": {
            "when": {"all_of": [{"lt": ["rsi(14)", 30]}]},
            "action": "enter_long",
            "sizing": {"fixed_pct": {"pct": 5.0}},
        },
        "exits": [{"stop_loss": {"atr_mult": 1.0}}],
        "risk": {
            "per_trade_stop_pct": 3.0,
            "max_position_pct": 5.0,
            "max_gross_exposure": 40.0,
        },
        "scan": {"all_of": [{"gt": ["avg_volume(20)", 500000]}]},
        "persistence_thesis": {
            "edge_type": "behavioral",
            "structural_reason": (
                "Retail traders consistently overreact to short-term RSI extremes, "
                "creating temporary mispricings that revert within days."
            ),
            "forced_counterparty": (
                "Retail day-traders and algorithmic stop-loss cascades "
                "mechanically sell at RSI oversold levels regardless of fundamental value."
            ),
            "death_condition": [
                "avg_volume(20) > capacity_ceiling_usd",
            ],
            "capacity_ceiling_usd": 20000000,
            "monitorable_as_regime": True,
        },
    }


class TestPersistenceThesis:
    """Validate the persistence_thesis load-time gate."""

    @staticmethod
    def _load_single(raw: dict, tmp_path: Path) -> dict:
        yaml_path = tmp_path / f"{raw['id']}.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(raw, f)
        from app.modules.registry import library_loader
        orig = library_loader.LIBRARY_DIR
        library_loader.LIBRARY_DIR = tmp_path
        try:
            return load_archetypes(validate=True)
        finally:
            library_loader.LIBRARY_DIR = orig

    def test_valid_thesis_loads(self, tmp_path):
        raw = _valid_archetype_yaml()
        result = self._load_single(raw, tmp_path)
        assert result["test_valid"]["status"] == "unexplored"
        assert result["test_valid"]["persistence_thesis"]["edge_type"] == "behavioral"

    def test_seed_archetypes_excluded(self):
        """Existing seed archetypes lack persistence_thesis — all excluded."""
        archetypes = load_archetypes(validate=True)
        for aid, a in archetypes.items():
            assert a["status"] == "excluded", (
                f"{aid}: expected excluded (no persistence_thesis), got {a['status']}"
            )
            assert "persistence_thesis" in a.get("exclusion_reason", ""), (
                f"{aid}: expected 'persistence_thesis' in exclusion_reason"
            )

    def test_monitorable_false_no_dsl_ref_ok(self, tmp_path):
        """monitorable_as_regime=false doesn't require DSL-mappable death_conditions."""
        raw = _valid_archetype_yaml()
        raw["persistence_thesis"]["monitorable_as_regime"] = False
        raw["persistence_thesis"]["death_condition"] = ["analyst_coverage > 50"]
        result = self._load_single(raw, tmp_path)
        assert result["test_valid"]["status"] == "unexplored"

    @pytest.mark.parametrize("label,modify,fragment", [
        (
            "block_absent",
            lambda r: r.pop("persistence_thesis"),
            "persistence_thesis block absent",
        ),
        (
            "bad_edge_type",
            lambda r: r["persistence_thesis"].update(edge_type="made_up"),
            "edge_type",
        ),
        (
            "no_edge_type",
            lambda r: r["persistence_thesis"].pop("edge_type"),
            "edge_type",
        ),
        (
            "short_reason",
            lambda r: r["persistence_thesis"].update(structural_reason="Too short"),
            "structural_reason",
        ),
        (
            "empty_reason",
            lambda r: r["persistence_thesis"].update(structural_reason=""),
            "structural_reason",
        ),
        (
            "short_counterparty",
            lambda r: r["persistence_thesis"].update(forced_counterparty="Short"),
            "forced_counterparty",
        ),
        (
            "no_death_condition",
            lambda r: r["persistence_thesis"].pop("death_condition"),
            "death_condition",
        ),
        (
            "empty_death_list",
            lambda r: r["persistence_thesis"].update(death_condition=[]),
            "death_condition",
        ),
        (
            "empty_death_entry",
            lambda r: r["persistence_thesis"].update(
                death_condition=["avg_volume(20) > cap", ""]
            ),
            "empty entry",
        ),
        (
            "zero_capacity",
            lambda r: r["persistence_thesis"].update(capacity_ceiling_usd=0),
            "capacity_ceiling_usd",
        ),
        (
            "negative_capacity",
            lambda r: r["persistence_thesis"].update(capacity_ceiling_usd=-1),
            "capacity_ceiling_usd",
        ),
        (
            "no_capacity",
            lambda r: r["persistence_thesis"].pop("capacity_ceiling_usd"),
            "capacity_ceiling_usd",
        ),
        (
            "no_monitorable",
            lambda r: r["persistence_thesis"].pop("monitorable_as_regime"),
            "monitorable_as_regime",
        ),
        (
            "monitorable_no_dsl",
            lambda r: (
                r["persistence_thesis"].update(monitorable_as_regime=True),
                r["persistence_thesis"].update(
                    death_condition=["analyst_coverage_count > 50"]
                ),
            ),
            "no death_condition references",
        ),
    ])
    def test_exclusion_rule(self, label, modify, fragment, tmp_path, caplog):
        raw = _valid_archetype_yaml()
        raw["id"] = f"test_{label}"
        modify(raw)
        with caplog.at_level(logging.ERROR):
            result = self._load_single(raw, tmp_path)
        aid = f"test_{label}"
        assert result[aid]["status"] == "excluded", (
            f"Expected excluded for {label}"
        )
        assert fragment in result[aid]["exclusion_reason"], (
            f"Expected '{fragment}' in reason for {label}, "
            f"got: {result[aid]['exclusion_reason']}"
        )

    def test_validate_persistence_thesis_unit(self):
        """Direct unit test of _validate_persistence_thesis."""
        raw = _valid_archetype_yaml()
        errors = _validate_persistence_thesis(raw, "test_unit")
        assert errors == [], f"Expected no errors, got: {errors}"

        raw_bad = copy.deepcopy(raw)
        del raw_bad["persistence_thesis"]
        errors = _validate_persistence_thesis(raw_bad, "test_missing")
        assert any("block absent" in e for e in errors)
