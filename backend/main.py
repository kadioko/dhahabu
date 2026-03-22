"""
Dhahabu Trading Platform — FastAPI entry point.

Lifecycle:
  startup → configure logging → init DB engine → start scheduler
  shutdown → stop scheduler → dispose DB engine
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from backend.core.config import settings
from backend.core.logging import configure_logging, get_logger
from backend.db.base import engine
from backend.db.models import Base  # ensure models are registered

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown logic."""
    configure_logging()
    logger.info("dhahabu.startup", version=settings.app_version, env=settings.environment)

    # Initialize DB tables (Alembic handles schema; this covers dev fallback)
    async with engine.begin() as conn:
        # Only create if running in dev without running alembic
        if settings.environment == "development":
            await conn.run_sync(Base.metadata.create_all)

    # Start scheduler
    from backend.scheduler.service import start_scheduler
    await start_scheduler()

    logger.info("dhahabu.ready")
    yield

    # Shutdown
    from backend.scheduler.service import stop_scheduler
    await stop_scheduler()

    await engine.dispose()
    logger.info("dhahabu.shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production XAUUSD Trading Intelligence Platform",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment != "production" else [
        "https://dhahabu.railway.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

from backend.api.routes import (
    health,
    candles,
    signals,
    trades,
    strategies,
    risk,
    pnl,
    validation,
    scheduler,
    dashboard,
    system,
)

app.include_router(health.router, tags=["health"])
app.include_router(system.router, prefix="/system", tags=["system"])
app.include_router(candles.router, prefix="/candles", tags=["candles"])
app.include_router(signals.router, prefix="/signals", tags=["signals"])
app.include_router(trades.router, prefix="/trades", tags=["trades"])
app.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
app.include_router(risk.router, prefix="/risk", tags=["risk"])
app.include_router(pnl.router, prefix="/pnl", tags=["pnl"])
app.include_router(validation.router, prefix="/validation", tags=["validation"])
app.include_router(scheduler.router, prefix="/scheduler", tags=["scheduler"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
