"""Test that all seed archetypes load and pass the DSL type-checker."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
import yaml

from app.modules.registry.library_loader import (
    load_archetypes, _build_template, _validate_template,
    _fill_placeholders, _extract_defaults, _validate_param_bindings,
    _validate_variant_distinctness, resolve_grid_values, LIBRARY_DIR,
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
        """Every archetype template must be a valid DSL spec."""
        archetypes = load_archetypes(validate=False)
        all_errors = []
        for aid, a in archetypes.items():
            errors = _validate_template(a["template"], aid)
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
                          "action": "enter_long", "sizing": {"fixed_pct": 5.0}},
                "exits": [{"stop_loss": {"atr_mult": 1.0}}],
                "risk": {"per_trade_stop_pct": 3.0, "max_position_pct": 5.0},
                "param_grid": {"ghost_param": {"min": 1, "max": 5, "step": 1, "default": 3}},
                "scan": {"all_of": [{"gt": ["avg_volume(20)", 500000]}]},
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
                          "action": "enter_long", "sizing": {"fixed_pct": 5.0}},
                "exits": [{"stop_loss": {"atr_mult": 1.0}}],
                "risk": {"per_trade_stop_pct": 3.0, "max_position_pct": 5.0},
                "param_grid": {"rsi_period": {"min": 7, "max": 21, "step": 2}},
                "scan": {"all_of": [{"gt": ["avg_volume(20)", 500000]}]},
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
