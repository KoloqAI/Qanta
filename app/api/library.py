from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.deps import DB, CurrentUser
from app import state
from app.schemas.library import (
    ArchetypeDetail,
    ArchetypeResponse,
    ExploreBody,
    ScanBody,
    ScanResult,
)

router = APIRouter()

# In-memory archetype store until DB-backed (populated by loader on init)
_archetypes: dict[str, dict] = {}
_exploration_runs: dict[str, list[dict]] = {}


def register_archetypes(archetypes: dict[str, dict]) -> None:
    _archetypes.update(archetypes)


@router.get("")
async def list_archetypes(
    user: CurrentUser,
    family: str | None = None,
    horizon: str | None = None,
) -> list[dict]:
    """List all library archetypes with optional family/horizon filter."""
    results = []
    for a in _archetypes.values():
        if family and a.get("family") != family:
            continue
        if horizon and a.get("horizon") != horizon and a.get("horizon") != "both":
            continue
        results.append({
            "id": a["id"],
            "name": a["name"],
            "family": a["family"],
            "horizon": a["horizon"],
            "thesis": a["thesis"],
            "status": a.get("status", "unexplored"),
            "source": a.get("source", "seed"),
        })
    return results


@router.get("/{archetype_id}")
async def get_archetype(archetype_id: str, user: CurrentUser) -> dict:
    """Get archetype detail including exploration funnel."""
    a = _archetypes.get(archetype_id)
    if not a:
        raise HTTPException(status_code=404, detail="Archetype not found")

    runs = _exploration_runs.get(archetype_id, [])
    total_trials = sum(r.get("trials", 0) for r in runs)
    total_survivors = sum(r.get("survivors", 0) for r in runs)

    return {
        **a,
        "exploration_funnel": {
            "runs": len(runs),
            "total_trials": total_trials,
            "total_survivors": total_survivors,
        },
    }


@router.post("/{archetype_id}/scan")
async def scan_archetype(
    archetype_id: str, body: ScanBody, user: CurrentUser
) -> dict:
    """Run an archetype's scan block against the universe to surface candidates.
    Logged to search_ledger (read-only tool — no deployment)."""
    a = _archetypes.get(archetype_id)
    if not a:
        raise HTTPException(status_code=404, detail="Archetype not found")

    scan_block = a.get("scan", {})
    universe = body.universe
    if not universe:
        from app.modules.data.providers import SAMPLE_UNIVERSE
        universe = SAMPLE_UNIVERSE

    candidates = _run_scan(scan_block, universe, a)

    # Log to search ledger
    await state.audit_log.log(
        actor="system",
        action="archetype_scan",
        subject_type="library_archetype",
        subject_id=archetype_id,
        payload={"n_candidates": len(candidates), "as_of": body.as_of},
        user_id=user.get("id"),
    )

    return {"archetype_id": archetype_id, "candidates": candidates}


@router.post("/{archetype_id}/explore")
async def explore_archetype(
    archetype_id: str, body: ExploreBody, db: DB, user: CurrentUser
) -> dict:
    """Queue an exploration sweep for this archetype.
    Budget-governed, ledger-tracked. Returns a job_id."""
    a = _archetypes.get(archetype_id)
    if not a:
        raise HTTPException(status_code=404, detail="Archetype not found")

    job_id = str(uuid.uuid4())
    run = {
        "id": str(uuid.uuid4()),
        "archetype_id": archetype_id,
        "budget": body.budget,
        "param_grid": body.param_grid or a.get("param_grid", {}),
        "trials": 0,
        "survivors": 0,
        "status": "queued",
    }
    _exploration_runs.setdefault(archetype_id, []).append(run)

    await state.audit_log.log(
        actor="system",
        action="exploration_queued",
        subject_type="library_archetype",
        subject_id=archetype_id,
        payload={"job_id": job_id, "budget": body.budget},
        user_id=user.get("id"),
    )

    return {"job_id": job_id, "archetype_id": archetype_id, "status": "queued"}


def _run_scan(
    scan_block: dict, universe: list[str], archetype: dict
) -> list[dict]:
    """Evaluate a scan block against the universe.
    Returns ranked candidates with a fit score."""
    candidates = []
    for symbol in universe:
        score = _evaluate_scan_conditions(scan_block, symbol)
        if score > 0:
            candidates.append({
                "ticker": symbol,
                "fit_score": round(score, 4),
                "archetype": archetype.get("name", ""),
                "family": archetype.get("family", ""),
            })
    candidates.sort(key=lambda c: c["fit_score"], reverse=True)
    return candidates


def _evaluate_scan_conditions(scan_block: dict, symbol: str) -> float:
    """Placeholder scan evaluator. Returns a deterministic score per symbol
    based on the scan conditions. Full DSL evaluation in a later batch."""
    import hashlib
    h = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)
    score = (h % 100) / 100.0
    conditions = scan_block.get("all_of", [])
    if conditions:
        score *= min(1.0, len(conditions) / 3.0)
    return score if score > 0.3 else 0.0
