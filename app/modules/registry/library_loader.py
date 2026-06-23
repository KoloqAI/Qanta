"""Load seed strategy archetypes from config/library/*.yaml on init.

Each YAML is validated through the DSL parser to ensure the template
is a valid spec (stop_loss required, regime non-empty, params in range).
The archetype's DSL-relevant fields become the template; metadata fields
(scan, param_grid, etc.) are stored separately.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

LIBRARY_DIR = Path(__file__).parents[3] / "config" / "library"

DSL_TEMPLATE_FIELDS = {"thesis", "regime", "entry", "exits", "risk", "universe", "validation"}


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

        if validate:
            errors = _validate_template(template, archetype_id)
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
            "param_grid": raw.get("param_grid", {}),
            "source": "seed",
            "status": "unexplored",
            "watches": raw.get("watches", []),
            "peers_hint": raw.get("peers_hint", ""),
            "default_universe": raw.get("default_universe", {}),
        }

    if all_errors:
        logger.warning(
            "Library loaded with %d validation warning(s) across %d archetype(s)",
            len(all_errors), len(archetypes),
        )
    else:
        logger.info("Loaded %d archetype(s) from %s", len(archetypes), LIBRARY_DIR)

    return archetypes
