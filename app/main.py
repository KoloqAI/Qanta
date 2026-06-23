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
    from app.modules.registry.library_loader import load_archetypes
    from app.api.library import register_archetypes

    archetypes = load_archetypes(validate=True)
    register_archetypes(archetypes)

    yield


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
