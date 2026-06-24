from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.dsl.schema import StrategySpec, RiskEnvelope
from app.core.dsl.primitives import ALL_PRIMITIVES, DSLType


KNOWN_TOP_LEVEL_FIELDS = {
    "id", "version", "tickers", "thesis", "regime", "entry", "exits",
    "risk", "universe", "validation", "author", "dsl_version",
}

KNOWN_ENTRY_FIELDS = {"when", "action", "sizing"}
KNOWN_ACTIONS = {"enter_long", "enter_short"}
KNOWN_SIZING = {"fixed_pct", "vol_scaled", "kelly_capped"}
KNOWN_EXIT_TYPES = {
    "stop_loss", "take_profit", "trailing_stop", "time_stop", "regime_break_exit",
}
KNOWN_CONDITION_OPS = {
    "eq", "gt", "lt", "between", "within_band", "outside_band",
    "crosses_above", "crosses_below", "held_for",
    "all_of", "any_of", "not",
}

# Default guardrails (loaded from config if available)
DEFAULT_GUARDRAILS = {
    "per_trade_stop_pct": 5.0,
    "max_position_pct": 10.0,
    "max_gross_exposure": 100.0,
}


@dataclass
class ParseError:
    field: str
    message: str


@dataclass
class ParseResult:
    success: bool
    spec: StrategySpec | None = None
    errors: list[ParseError] | None = None


def _load_guardrails() -> dict:
    """Load guardrails from config file, fall back to defaults."""
    try:
        import yaml
        from pathlib import Path
        config_path = Path(__file__).parents[3] / "config" / "guardrails.yaml"
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
                return {
                    "per_trade_stop_pct": data.get(
                        "per_trade_stop_pct",
                        DEFAULT_GUARDRAILS["per_trade_stop_pct"],
                    ),
                    "max_position_pct": data.get(
                        "max_position_pct",
                        DEFAULT_GUARDRAILS["max_position_pct"],
                    ),
                    "max_gross_exposure": data.get(
                        "max_gross_exposure_pct",
                        data.get(
                            "max_gross_exposure",
                            DEFAULT_GUARDRAILS["max_gross_exposure"],
                        ),
                    ),
                }
    except Exception:
        pass
    return dict(DEFAULT_GUARDRAILS)


def _parse_feature_ref(ref: str) -> tuple[str, list[Any]] | None:
    """Parse 'sma(20)' -> ('sma', [20])."""
    m = re.match(r"(\w+)\(([^)]*)\)", ref)
    if not m:
        return None
    name = m.group(1)
    args_str = m.group(2)
    args: list[Any] = []
    for a in args_str.split(","):
        a = a.strip()
        if not a:
            continue
        try:
            args.append(int(a))
        except ValueError:
            try:
                args.append(float(a))
            except ValueError:
                args.append(a)
    return name, args


def _validate_primitive_ref(ref: str, errors: list[ParseError], field: str) -> None:
    """Validate that a primitive reference is in the catalog with correct args."""
    # Handle record field access like "bollinger(20,2).upper"
    base_ref = ref.split(".")[0] if "." in ref else ref

    parsed = _parse_feature_ref(base_ref)
    if parsed is None:
        # Not a function call -- could be a column name or scalar; skip
        return

    name, args = parsed
    # Check if primitive exists in catalog
    prim = ALL_PRIMITIVES.get(name)
    if prim is None:
        errors.append(ParseError(
            field,
            f"Unknown primitive '{name}' -- not in the DSL catalog",
        ))
        return

    # Check arg count (prim.args is list[tuple[str, DSLType]])
    expected_count = len(prim.args)
    if len(args) != expected_count:
        errors.append(ParseError(
            field,
            f"Primitive '{name}' expects {expected_count} arg(s), got {len(args)}",
        ))
        return

    # Validate arg values against constraints
    for i, (param_name, param_type) in enumerate(prim.args):
        if param_name in prim.constraints:
            constraint = prim.constraints[param_name]
            val = args[i]
            if isinstance(val, (int, float)):
                if "min" in constraint and val < constraint["min"]:
                    errors.append(ParseError(
                        field,
                        f"Primitive '{name}' param '{param_name}' value {val} "
                        f"is below minimum {constraint['min']}",
                    ))
                if "max" in constraint and val > constraint["max"]:
                    errors.append(ParseError(
                        field,
                        f"Primitive '{name}' param '{param_name}' value {val} "
                        f"exceeds maximum {constraint['max']}",
                    ))

    # Validate record field access
    if "." in ref:
        field_name = ref.split(".", 1)[1]
        if prim.output_type == DSLType.RECORD:
            if prim.output_fields and field_name not in prim.output_fields:
                errors.append(ParseError(
                    field,
                    f"Primitive '{name}' has no field '{field_name}'; "
                    f"valid fields: {prim.output_fields}",
                ))
        else:
            errors.append(ParseError(
                field,
                f"Primitive '{name}' returns {prim.output_type.value}, "
                f"not Record -- cannot access field '.{field_name}'",
            ))


def _validate_condition(cond: Any, errors: list[ParseError], field: str) -> None:
    """Recursively validate a condition dict."""
    if not isinstance(cond, dict):
        return

    for op, args in cond.items():
        if op not in KNOWN_CONDITION_OPS:
            errors.append(ParseError(field, f"Unknown condition operator '{op}'"))
            continue

        if op in ("all_of", "any_of"):
            if not isinstance(args, list):
                errors.append(ParseError(
                    field, f"'{op}' requires a list of conditions",
                ))
            else:
                for sub in args:
                    _validate_condition(sub, errors, field)
        elif op == "not":
            if isinstance(args, dict):
                _validate_condition(args, errors, field)
            elif isinstance(args, list) and len(args) == 1:
                _validate_condition(args[0], errors, field)
        elif op in ("eq", "gt", "lt", "crosses_above", "crosses_below"):
            if not isinstance(args, list) or len(args) != 2:
                errors.append(ParseError(
                    field, f"'{op}' requires exactly 2 arguments",
                ))
            else:
                for a in args:
                    if isinstance(a, str):
                        _validate_primitive_ref(a, errors, field)
        elif op in ("between", "within_band", "outside_band"):
            if not isinstance(args, list) or len(args) != 3:
                errors.append(ParseError(
                    field, f"'{op}' requires exactly 3 arguments",
                ))
            else:
                for a in args:
                    if isinstance(a, str):
                        _validate_primitive_ref(a, errors, field)
        elif op == "held_for":
            if not isinstance(args, list) or len(args) != 2:
                errors.append(ParseError(
                    field, f"'held_for' requires [condition, n_bars]",
                ))
            else:
                _validate_condition(args[0], errors, field)


SIZING_SCHEMAS: dict[str, list[str]] = {
    "fixed_pct": ["pct"],
    "vol_scaled": ["target_vol"],
    "kelly_capped": ["frac", "cap"],
}


def _validate_sizing_shape(sizing: dict, errors: list[ParseError]) -> None:
    """Enforce canonical nested-dict form for sizing primitives."""
    for method, required_keys in SIZING_SCHEMAS.items():
        if method not in sizing:
            continue
        val = sizing[method]
        if not isinstance(val, dict):
            errors.append(ParseError(
                "entry.sizing",
                f"'{method}' must be a dict with keys {required_keys}, "
                f"got {type(val).__name__}. Use {{{method}: {{{required_keys[0]}: ...}}}}",
            ))
            return
        for rk in required_keys:
            if rk not in val:
                errors.append(ParseError(
                    "entry.sizing",
                    f"'{method}' missing required key '{rk}'",
                ))
            elif not isinstance(val[rk], (int, float)):
                errors.append(ParseError(
                    "entry.sizing",
                    f"'{method}.{rk}' must be numeric, got {type(val[rk]).__name__}",
                ))


def parse_spec(raw: dict[str, Any]) -> ParseResult:
    """Parse and type-check a raw spec dict into a StrategySpec.

    Enforces: thesis present, all primitives known, arg types match,
    exactly one entry, stop_loss required, risk subset of guardrails,
    regime non-empty, no unknown fields.
    """
    errors: list[ParseError] = []

    # 1. Unknown top-level fields
    unknown = set(raw.keys()) - KNOWN_TOP_LEVEL_FIELDS
    for uf in sorted(unknown):
        errors.append(ParseError(uf, f"Unknown top-level field '{uf}'"))

    # 2. Thesis present and non-empty
    if not raw.get("thesis"):
        errors.append(ParseError("thesis", "thesis is required and must be non-empty"))

    # 3. Regime non-empty
    regime = raw.get("regime", {})
    all_of = regime.get("all_of", [])
    if not all_of:
        errors.append(ParseError("regime", "regime.all_of must be non-empty"))
    else:
        for cond in all_of:
            _validate_condition(cond, errors, "regime")

    # 4. Entry validation
    entry = raw.get("entry", {})
    if entry:
        entry_unknown = set(entry.keys()) - KNOWN_ENTRY_FIELDS
        for f in sorted(entry_unknown):
            errors.append(ParseError("entry", f"Unknown entry field '{f}'"))

        action = entry.get("action", "enter_long")
        if action not in KNOWN_ACTIONS:
            errors.append(ParseError(
                "entry.action",
                f"Unknown action '{action}'; must be one of {KNOWN_ACTIONS}",
            ))

        when = entry.get("when")
        if when:
            _validate_condition(when, errors, "entry.when")

        sizing = entry.get("sizing", {})
        if sizing:
            sizing_keys = set(sizing.keys())
            if not sizing_keys.intersection(KNOWN_SIZING):
                errors.append(ParseError(
                    "entry.sizing",
                    f"Unknown sizing method; must be one of {KNOWN_SIZING}",
                ))
            else:
                _validate_sizing_shape(sizing, errors)

    # 5. Exits -- at least one stop_loss
    exits = raw.get("exits", [])
    has_stop = any("stop_loss" in e for e in exits)
    if not has_stop:
        errors.append(ParseError("exits", "at least one stop_loss exit is required"))

    for i, exit_spec in enumerate(exits):
        exit_types_used = set(exit_spec.keys())
        unknown_exit = exit_types_used - KNOWN_EXIT_TYPES
        for et in sorted(unknown_exit):
            errors.append(ParseError(
                f"exits[{i}]", f"Unknown exit type '{et}'",
            ))

    # 6. Risk envelope <= global guardrails
    risk_raw = raw.get("risk", {})
    guardrails = _load_guardrails()

    max_pos = risk_raw.get("max_position_pct", 5.0)
    stop_pct = risk_raw.get("per_trade_stop_pct", 3.0)
    max_exp = risk_raw.get("max_gross_exposure", 40.0)

    if max_pos > guardrails["max_position_pct"]:
        errors.append(ParseError(
            "risk.max_position_pct",
            f"max_position_pct ({max_pos}) exceeds guardrail "
            f"({guardrails['max_position_pct']})",
        ))
    if stop_pct > guardrails["per_trade_stop_pct"]:
        errors.append(ParseError(
            "risk.per_trade_stop_pct",
            f"per_trade_stop_pct ({stop_pct}) exceeds guardrail "
            f"({guardrails['per_trade_stop_pct']})",
        ))
    if max_exp > guardrails["max_gross_exposure"]:
        errors.append(ParseError(
            "risk.max_gross_exposure",
            f"max_gross_exposure ({max_exp}) exceeds guardrail "
            f"({guardrails['max_gross_exposure']})",
        ))

    if errors:
        return ParseResult(success=False, errors=errors)

    risk = RiskEnvelope(
        max_position_pct=max_pos,
        per_trade_stop_pct=stop_pct,
        max_gross_exposure=max_exp,
    )

    spec = StrategySpec(
        id=raw.get("id", ""),
        version=raw.get("version", 1),
        tickers=raw.get("tickers", []),
        thesis=raw["thesis"],
        regime=raw.get("regime", {}),
        entry=raw.get("entry", {}),
        exits=exits,
        risk=risk,
        universe=raw.get("universe", {}),
        validation=raw.get("validation", {}),
        author=raw.get("author", {}),
        dsl_version=raw.get("dsl_version", 1),
    )
    return ParseResult(success=True, spec=spec)
