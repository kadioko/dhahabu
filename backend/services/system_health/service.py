"""System health monitoring service."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

from backend.core.logging import get_logger
from backend.db.base import get_db_session
from backend.db.models import Candle, SchedulerJobRun, SystemState

logger = get_logger(__name__)


async def run_health_check() -> None:
    """
    Check health of all tracked components and update system_state.
    """
    now = datetime.utcnow()
    checks = {
        "market_data": await _check_market_data(now),
        "trading_brain": await _check_scheduler_job("trading_brain", max_age_minutes=35),
        "trade_reconcile": await _check_scheduler_job("trade_reconcile", max_age_minutes=10),
        "self_healing_backtest": await _check_scheduler_job("self_healing_backtest", max_age_minutes=250),
        "risk_monitor": await _check_scheduler_job("risk_monitor", max_age_minutes=3),
    }

    async with get_db_session() as db:
        for component, (status, score, error) in checks.items():
            result = await db.execute(
                select(SystemState).where(SystemState.component_name == component)
            )
            state = result.scalar_one_or_none()
            if state:
                state.status = status
                state.health_score = score
                state.last_error = error
                state.updated_at = now
            else:
                db.add(SystemState(
                    component_name=component,
                    status=status,
                    health_score=score,
                    last_error=error,
                    updated_at=now,
                ))

    healthy = sum(1 for s, _, _ in checks.values() if s == "healthy")
    logger.info("health_check.done", healthy=healthy, total=len(checks))


async def _check_market_data(now: datetime) -> tuple[str, float, str | None]:
    """Check if market data is fresh (last candle within 2 hours)."""
    async with get_db_session() as db:
        result = await db.execute(
            select(func.max(Candle.timestamp))
        )
        last_ts = result.scalar()

    if not last_ts:
        return "down", 0.0, "No candle data found"

    age_minutes = (now - last_ts.replace(tzinfo=None)).total_seconds() / 60
    if age_minutes < 20:
        return "healthy", 1.0, None
    elif age_minutes < 60:
        return "degraded", 0.6, f"Last candle {age_minutes:.0f}m ago"
    else:
        return "down", 0.0, f"Last candle {age_minutes:.0f}m ago — stale"


async def _check_scheduler_job(job_name: str, max_age_minutes: int) -> tuple[str, float, str | None]:
    """Check if a scheduler job ran recently and successfully."""
    async with get_db_session() as db:
        result = await db.execute(
            select(SchedulerJobRun)
            .where(SchedulerJobRun.job_name == job_name)
            .order_by(SchedulerJobRun.started_at.desc())
            .limit(1)
        )
        run = result.scalar_one_or_none()

    if not run:
        return "unknown", 0.5, "No runs found"

    now = datetime.utcnow()
    age_minutes = (now - run.started_at.replace(tzinfo=None)).total_seconds() / 60

    if run.status == "success" and age_minutes <= max_age_minutes:
        return "healthy", 1.0, None
    elif run.status == "failed":
        return "degraded", 0.3, run.error_message
    elif age_minutes > max_age_minutes * 2:
        return "down", 0.0, f"No successful run in {age_minutes:.0f}m"
    else:
        return "degraded", 0.6, f"Last run {age_minutes:.0f}m ago"
