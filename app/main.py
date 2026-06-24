from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, strategies, research, deployments
from app.api import portfolio, performance, monitor, evolution
from app.api import assistant, settings as settings_router, ws
from app.api import library, backtest
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from app.deps import async_session_factory
    from app.modules.auth.service import AuthServiceImpl
    from app.modules.registry.library_loader import load_archetypes
    from app.api.library import register_archetypes
    import logging

    logger = logging.getLogger(__name__)

    if settings.owner_email and settings.owner_password:
        async with async_session_factory() as db:
            auth = AuthServiceImpl(db, settings.session_expire_minutes)
            count = await auth.user_count()
            if count == 0:
                try:
                    await auth.register(settings.owner_email, settings.owner_password)
                    logger.info("Owner account seeded: %s", settings.owner_email)
                except Exception as exc:
                    logger.error("Failed to seed owner account: %s", exc)

    archetypes = load_archetypes(validate=True)
    register_archetypes(archetypes)

    from app.modules.validation.service import invalidate_stale_reports
    from app import state
    invalidate_stale_reports(state.validation_reports)

    try:
        from arq import create_pool as _arq_create_pool
        from arq.connections import RedisSettings as _ArqRedisSettings
        pool = await _arq_create_pool(
            _ArqRedisSettings.from_dsn(settings.redis_url)
        )
        app.state.arq_pool = pool
    except Exception as exc:
        app.state.arq_pool = None
        logger.warning("Arq pool unavailable — job enqueue disabled: %s", exc)

    yield

    if getattr(app.state, "arq_pool", None):
        await app.state.arq_pool.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Quanta",
        description="Personal AI Trading Research & Execution Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
    app.include_router(research.router, prefix="/research", tags=["research"])
    app.include_router(deployments.router, prefix="/deployments", tags=["deployments"])
    app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
    app.include_router(performance.router, prefix="/performance", tags=["performance"])
    app.include_router(monitor.router, prefix="/monitor", tags=["monitor"])
    app.include_router(evolution.router, prefix="/evolution", tags=["evolution"])
    app.include_router(assistant.router, prefix="/assistant", tags=["assistant"])
    app.include_router(settings_router.router, prefix="/settings", tags=["settings"])
    app.include_router(library.router, prefix="/library", tags=["library"])
    app.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
    app.include_router(ws.router, prefix="/ws", tags=["websocket"])

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
