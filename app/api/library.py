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
        entry = {
            "id": a["id"],
            "name": a["name"],
            "family": a["family"],
            "horizon": a["horizon"],
            "thesis": a["thesis"],
            "status": a.get("status", "unexplored"),
            "source": a.get("source", "seed"),
        }
        if a.get("exclusion_reason"):
            entry["exclusion_reason"] = a["exclusion_reason"]
        results.append(entry)
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
    from datetime import datetime as _dt
    from app.modules.data.providers import scan_universe

    a = _archetypes.get(archetype_id)
    if not a:
        raise HTTPException(status_code=404, detail="Archetype not found")

    as_of = _dt.fromisoformat(body.as_of) if body.as_of else None

    result = await scan_universe(a, as_of=as_of)

    await state.audit_log.log(
        actor="system",
        action="archetype_scan",
        subject_type="library_archetype",
        subject_id=archetype_id,
        payload={
            "n_candidates": len(result["candidates"]),
            "as_of": body.as_of,
            "is_sample_fallback": result["is_sample_fallback"],
        },
        user_id=user.get("id"),
    )

    return {
        "archetype_id": archetype_id,
        "candidates": result["candidates"],
        "is_sample_fallback": result["is_sample_fallback"],
    }


@router.post("/{archetype_id}/explore")
async def explore_archetype(
    archetype_id: str, body: ExploreBody, db: DB, user: CurrentUser
) -> dict:
    """Queue an exploration sweep for this archetype.
    Budget-governed, ledger-tracked. Returns a job_id."""
    import asyncio
    from app.workers.tasks import run_explore
    from app.workers.job_events import init_job

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

    init_job(job_id)

    asyncio.create_task(run_explore(
        ctx={},
        job_id=job_id,
        archetype_id=archetype_id,
        budget=body.budget,
        param_grid=body.param_grid or a.get("param_grid", {}),
        registry=state.registry,
    ))

    await state.audit_log.log(
        actor="system",
        action="exploration_queued",
        subject_type="library_archetype",
        subject_id=archetype_id,
        payload={"job_id": job_id, "budget": body.budget},
        user_id=user.get("id"),
    )

    return {"job_id": job_id, "archetype_id": archetype_id, "status": "queued"}


