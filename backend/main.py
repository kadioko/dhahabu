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
from sqlalchemy import func, select

from backend.core.config import settings
from backend.core.constants import JobName
from backend.core.logging import configure_logging, get_logger
from backend.db.base import engine, get_db_session
from backend.db.models import Base, Candle  # ensure models are registered

logger = get_logger(__name__)


async def _bootstrap_market_data_if_empty() -> None:
    from backend.scheduler.service import run_job_now

    async with get_db_session() as db:
        candle_count = await db.scalar(select(func.count()).select_from(Candle))

    if candle_count and candle_count > 0:
        logger.info("market_data.bootstrap.skipped", candle_count=candle_count)
    else:
        logger.info("market_data.bootstrap.start")
        try:
            result = await run_job_now(JobName.MARKET_DATA_INGEST)
            logger.info("market_data.bootstrap.done", result=result)
        except Exception as exc:
            logger.error("market_data.bootstrap.failed", error=str(exc))

    try:
        await run_job_now(JobName.HEALTH_CHECK)
    except Exception as exc:
        logger.error("health_check.bootstrap.failed", error=str(exc))


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
    asyncio.create_task(_bootstrap_market_data_if_empty())

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
