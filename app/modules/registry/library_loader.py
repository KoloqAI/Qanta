"""Load seed strategy archetypes from config/library/*.yaml on init.

Each YAML is validated through the DSL parser to ensure the template
is a valid spec (stop_loss required, regime non-empty, params in range).

Templates use explicit ``{param_name}`` placeholders that the param_grid
fills — substitution is exact, and an unfilled placeholder or unbound
param is a load error.
"""
from __future__ import annotations

import copy
import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

LIBRARY_DIR = Path(__file__).parents[3] / "config" / "library"

DSL_TEMPLATE_FIELDS = {"thesis", "regime", "entry", "exits", "risk", "universe", "validation"}

VALID_EDGE_TYPES = frozenset({"forced_flow", "behavioral", "risk_premium", "smallness"})
MIN_CONTENT_LENGTH = 40

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


# ---------------------------------------------------------------------------
# Placeholder engine
# ---------------------------------------------------------------------------


def _fmt_num(v: float | int) -> str:
    """Format numeric for string embedding. 14.0 → '14', 1.2 → '1.2'."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _coerce_numeric(v: float | int) -> float | int:
    """Coerce whole floats to int: 14.0 → 14, 1.2 → 1.2.

    Uses ``float.is_integer()`` — never truncates a fractional value.
    """
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _fill_placeholders(template: dict, values: dict[str, float | int]) -> dict:
    """Recursively fill ``{param_name}`` placeholders in *template*.

    - Pure-value placeholder (entire string is ``"{param}"``): replaced with
      the raw numeric value, whole floats coerced to int (25.0 → 25).
    - Embedded placeholder (``"rsi({rsi_period})"``): string-formatted with
      int-coerced numerics so ``14.0`` becomes ``"rsi(14)"``.
    """

    def _walk(obj: Any) -> Any:
        if isinstance(obj, str):
            m = re.fullmatch(r"\{(\w+)\}", obj)
            if m and m.group(1) in values:
                return _coerce_numeric(values[m.group(1)])
            def _repl(match: re.Match) -> str:
                name = match.group(1)
                if name in values:
                    return _fmt_num(values[name])
                return match.group(0)
            return _PLACEHOLDER_RE.sub(_repl, obj)
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk(item) for item in obj]
        return obj

    return _walk(copy.deepcopy(template))


def _extract_defaults(param_grid: dict[str, dict]) -> dict[str, float | int]:
    """Extract ``default`` values from each param_grid entry."""
    defaults: dict[str, float | int] = {}
    for name, entry in param_grid.items():
        if "default" in entry:
            defaults[name] = entry["default"]
    return defaults


def resolve_grid_values(entry: dict) -> list[float]:
    """Convert ``{min, max, step}`` to an explicit list of values."""
    lo = float(entry.get("min", 0))
    hi = float(entry.get("max", lo))
    step = float(entry.get("step", 1))
    if step <= 0 or lo > hi:
        return [lo]
    vals: list[float] = []
    v = lo
    while v <= hi + 1e-9:
        vals.append(round(v, 6))
        v += step
    return vals or [lo]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _death_condition_maps_to_dsl(
    death_conditions: list[str],
    regime: dict[str, Any],
) -> bool:
    """Check if any death_condition references a DSL feature primitive or regime field."""
    from app.core.dsl.primitives import FEATURE_PRIMITIVES

    known = set(FEATURE_PRIMITIVES.keys())
    regime_text = json.dumps(regime, default=str).lower()
    for name in list(known):
        if name in regime_text:
            known.add(name)

    for dc in death_conditions:
        dc_lower = dc.lower()
        for name in known:
            if name in dc_lower:
                return True
    return False


def _validate_persistence_thesis(
    raw: dict[str, Any],
    archetype_id: str,
) -> list[str]:
    """Validate the persistence_thesis block (rules 1-6 of the schema gate)."""
    errors: list[str] = []
    pt = raw.get("persistence_thesis")

    if not pt or not isinstance(pt, dict):
        errors.append(f"[{archetype_id}] persistence_thesis block absent")
        return errors

    edge_type = pt.get("edge_type")
    if not edge_type or edge_type not in VALID_EDGE_TYPES:
        errors.append(
            f"[{archetype_id}] persistence_thesis.edge_type missing or "
            f"invalid (got {edge_type!r}, expected one of {sorted(VALID_EDGE_TYPES)})"
        )

    for field_name in ("structural_reason", "forced_counterparty"):
        content = (pt.get(field_name) or "").strip()
        if len(content) < MIN_CONTENT_LENGTH:
            errors.append(
                f"[{archetype_id}] persistence_thesis.{field_name} "
                f"too short ({len(content)} chars, min {MIN_CONTENT_LENGTH})"
            )

    death_conditions = pt.get("death_condition")
    has_valid_death_conditions = True
    if not death_conditions or not isinstance(death_conditions, list) or len(death_conditions) == 0:
        errors.append(
            f"[{archetype_id}] persistence_thesis.death_condition absent or empty"
        )
        has_valid_death_conditions = False
    elif any(not (dc if isinstance(dc, str) else "").strip() for dc in death_conditions):
        errors.append(
            f"[{archetype_id}] persistence_thesis.death_condition contains empty entry"
        )

    capacity = pt.get("capacity_ceiling_usd")
    if capacity is None or not isinstance(capacity, (int, float)) or capacity <= 0:
        errors.append(
            f"[{archetype_id}] persistence_thesis.capacity_ceiling_usd "
            f"absent or <= 0 (got {capacity!r})"
        )

    monitorable = pt.get("monitorable_as_regime")
    if monitorable is None or not isinstance(monitorable, bool):
        errors.append(
            f"[{archetype_id}] persistence_thesis.monitorable_as_regime "
            f"missing or not a bool (got {monitorable!r})"
        )
    elif monitorable and has_valid_death_conditions:
        regime = raw.get("regime", {})
        if not _death_condition_maps_to_dsl(death_conditions, regime):
            errors.append(
                f"[{archetype_id}] monitorable_as_regime is true but no "
                f"death_condition references a DSL primitive or regime field"
            )

    return errors


def _validate_param_bindings(
    template: dict[str, Any],
    param_grid: dict[str, dict],
    archetype_id: str,
) -> list[str]:
    """Validate that every param_grid key binds to a placeholder and vice versa."""
    errors: list[str] = []
    template_str = json.dumps(template, default=str)

    for pname in param_grid:
        placeholder = "{" + pname + "}"
        if placeholder not in template_str:
            errors.append(
                f"[{archetype_id}] param_grid key '{pname}' has no "
                f"{{{pname}}} placeholder in template"
            )

    found = set(_PLACEHOLDER_RE.findall(template_str))
    for ph in found:
        if ph not in param_grid:
            errors.append(
                f"[{archetype_id}] template placeholder '{{{ph}}}' "
                f"has no param_grid entry"
            )

    for pname, entry in param_grid.items():
        if "default" not in entry:
            errors.append(
                f"[{archetype_id}] param_grid '{pname}' missing 'default' value"
            )

    return errors


def _validate_variant_distinctness(
    template: dict[str, Any],
    param_grid: dict[str, dict],
    archetype_id: str,
    n_sample: int = 20,
) -> list[str]:
    """Spot-check that the grid produces distinct variants."""
    import itertools

    defaults = _extract_defaults(param_grid)
    if not defaults:
        return []

    param_names = list(param_grid.keys())
    param_values = [resolve_grid_values(param_grid[k]) for k in param_names]
    full_product = list(itertools.product(*param_values))

    if len(full_product) > n_sample:
        import numpy as np
        indices = np.round(np.linspace(0, len(full_product) - 1, n_sample)).astype(int)
        selected = [full_product[int(i)] for i in indices]
    else:
        selected = full_product

    base = _fill_placeholders(template, defaults)
    base_key = json.dumps(base, sort_keys=True, default=str)
    seen = {base_key}
    duplicates = 0

    for combo in selected:
        values = dict(zip(param_names, combo))
        if values == defaults:
            continue
        variant = _fill_placeholders(template, values)
        key = json.dumps(variant, sort_keys=True, default=str)
        if key in seen:
            duplicates += 1
        seen.add(key)

    errors: list[str] = []
    if duplicates > 0:
        errors.append(
            f"[{archetype_id}] {duplicates} duplicate variant(s) in "
            f"{len(selected)} sampled combos — a placeholder may be unbound"
        )
    return errors


def _build_template(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract DSL spec fields from the archetype YAML into a template dict."""
    template: dict[str, Any] = {}
    for field in DSL_TEMPLATE_FIELDS:
        if field in raw:
            template[field] = raw[field]
    template.setdefault("tickers", [])
    template.setdefault("id", raw.get("id", ""))
    template.setdefault("version", 1)
    return template


def _validate_template(template: dict[str, Any], archetype_id: str) -> list[str]:
    """Run the template through the DSL parser and return any errors."""
    from app.core.dsl.parser import parse_spec

    result = parse_spec(template)
    if result.success:
        return []
    return [
        f"[{archetype_id}] {e.field}: {e.message}"
        for e in (result.errors or [])
    ]


def load_archetypes(validate: bool = True) -> dict[str, dict[str, Any]]:
    """Load all archetype YAMLs from config/library/.

    Returns a dict of archetype_id -> archetype dict suitable for
    registering with the library API.
    """
    archetypes: dict[str, dict[str, Any]] = {}

    if not LIBRARY_DIR.exists():
        logger.warning("Library directory not found: %s", LIBRARY_DIR)
        return archetypes

    all_errors: list[str] = []
    excluded: list[str] = []

    for path in sorted(LIBRARY_DIR.glob("*.yaml")):
        try:
            with open(path) as f:
                raw = yaml.safe_load(f)
        except Exception:
            logger.exception("Failed to load archetype: %s", path.name)
            continue

        if not raw or not isinstance(raw, dict):
            logger.warning("Empty or invalid YAML: %s", path.name)
            continue

        archetype_id = raw.get("id", path.stem)
        template = _build_template(raw)
        param_grid = raw.get("param_grid", {})

        # -- Persistence thesis gate --
        thesis_errors = _validate_persistence_thesis(raw, archetype_id)
        if thesis_errors:
            for err in thesis_errors:
                logger.error("Persistence thesis error: %s", err)
            all_errors.extend(thesis_errors)
            excluded.append(archetype_id)
            archetypes[archetype_id] = {
                "id": archetype_id,
                "name": raw.get("name", archetype_id),
                "family": raw.get("family", ""),
                "horizon": raw.get("horizon", "both"),
                "thesis": raw.get("thesis", ""),
                "template": template,
                "scan": raw.get("scan", {}),
                "param_grid": param_grid,
                "source": "seed",
                "status": "excluded",
                "exclusion_reason": "; ".join(thesis_errors),
                "watches": raw.get("watches", []),
                "peers_hint": raw.get("peers_hint", ""),
                "default_universe": raw.get("default_universe", {}),
                "persistence_thesis": raw.get("persistence_thesis"),
            }
            continue

        # -- Param binding safety net --
        if param_grid:
            binding_errors = _validate_param_bindings(template, param_grid, archetype_id)
            if binding_errors:
                for err in binding_errors:
                    logger.error("Param binding error: %s", err)
                all_errors.extend(binding_errors)
                excluded.append(archetype_id)
                archetypes[archetype_id] = {
                    "id": archetype_id,
                    "name": raw.get("name", archetype_id),
                    "family": raw.get("family", ""),
                    "horizon": raw.get("horizon", "both"),
                    "thesis": raw.get("thesis", ""),
                    "template": template,
                    "scan": raw.get("scan", {}),
                    "param_grid": param_grid,
                    "source": "seed",
                    "status": "excluded",
                    "exclusion_reason": "; ".join(binding_errors),
                    "watches": raw.get("watches", []),
                    "peers_hint": raw.get("peers_hint", ""),
                    "default_universe": raw.get("default_universe", {}),
                    "persistence_thesis": raw.get("persistence_thesis"),
                }
                continue

            distinct_errors = _validate_variant_distinctness(
                template, param_grid, archetype_id,
            )
            if distinct_errors:
                for err in distinct_errors:
                    logger.error("Variant distinctness error: %s", err)
                all_errors.extend(distinct_errors)
                excluded.append(archetype_id)
                archetypes[archetype_id] = {
                    "id": archetype_id,
                    "name": raw.get("name", archetype_id),
                    "family": raw.get("family", ""),
                    "horizon": raw.get("horizon", "both"),
                    "thesis": raw.get("thesis", ""),
                    "template": template,
                    "scan": raw.get("scan", {}),
                    "param_grid": param_grid,
                    "source": "seed",
                    "status": "excluded",
                    "exclusion_reason": "; ".join(distinct_errors),
                    "watches": raw.get("watches", []),
                    "peers_hint": raw.get("peers_hint", ""),
                    "default_universe": raw.get("default_universe", {}),
                    "persistence_thesis": raw.get("persistence_thesis"),
                }
                continue

        # Fill defaults before DSL validation
        if param_grid:
            defaults = _extract_defaults(param_grid)
            filled_template = _fill_placeholders(template, defaults)
        else:
            filled_template = template

        if validate:
            errors = _validate_template(filled_template, archetype_id)
            if errors:
                all_errors.extend(errors)
                logger.warning(
                    "Archetype %s has %d validation error(s) — loading anyway",
                    archetype_id, len(errors),
                )

        archetypes[archetype_id] = {
            "id": archetype_id,
            "name": raw.get("name", archetype_id),
            "family": raw.get("family", ""),
            "horizon": raw.get("horizon", "both"),
            "thesis": raw.get("thesis", ""),
            "template": template,
            "scan": raw.get("scan", {}),
            "param_grid": param_grid,
            "source": "seed",
            "status": "unexplored",
            "watches": raw.get("watches", []),
            "peers_hint": raw.get("peers_hint", ""),
            "default_universe": raw.get("default_universe", {}),
            "persistence_thesis": raw.get("persistence_thesis"),
        }

    if excluded:
        logger.error(
            "Excluded %d archetype(s) from exploration: %s",
            len(excluded), ", ".join(excluded),
        )

    total_files = len(list(LIBRARY_DIR.glob("*.yaml")))
    if all_errors:
        logger.warning(
            "Library loaded: %d/%d archetypes OK, %d excluded, %d warning(s)",
            len(archetypes), total_files, len(excluded), len(all_errors),
        )
    else:
        logger.info(
            "Library loaded: %d/%d archetypes OK, 0 excluded",
            len(archetypes), total_files,
        )

    return archetypes
