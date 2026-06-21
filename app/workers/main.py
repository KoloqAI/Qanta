from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.workers.tasks import (
    run_research,
    run_backtest,
    run_validation,
    run_evolution_tier1,
    run_evolution_tier2,
)


async def startup(ctx: dict) -> None:
    pass


async def shutdown(ctx: dict) -> None:
    pass


class WorkerSettings:
    functions = [
        run_research,
        run_backtest,
        run_validation,
        run_evolution_tier1,
        run_evolution_tier2,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 3600
