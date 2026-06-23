"""Test that all seed archetypes load and pass the DSL type-checker."""
from __future__ import annotations

import pytest

from app.modules.registry.library_loader import load_archetypes, _build_template, _validate_template


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
