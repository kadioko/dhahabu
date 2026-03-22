"""
APScheduler-based job orchestration.

Every job:
  1. Logs its start with a SchedulerJobRun record
  2. Executes the domain logic via the relevant service
  3. Updates the run record with success/failure
  4. Updates system_state for its component
  5. Handles its own exceptions — a failed job never crashes the scheduler

Jobs are defined as independent async functions and registered below.
"""

from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from typing import Any, Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.core.config import settings
from backend.core.constants import JobName, JobStatus
from backend.core.logging import get_logger

logger = get_logger(__name__)
_scheduler: AsyncIOScheduler | None = None


def _serialize_job_result(result: Any) -> dict[str, Any] | None:
    if result is None:
        return None
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        return {"items": result, "count": len(result)}
    if isinstance(result, (str, int, float, bool)):
        return {"value": result}
    return {"value": str(result)}


# ── Job wrapper ───────────────────────────────────────────────────────────────

async def _run_job(job_name: str, fn: Callable[[], Awaitable[Any]]) -> dict[str, Any]:
    """
    Wraps a job function with:
      - DB run record creation/update
      - Structured logging
      - Exception isolation
    """
    from backend.db.base import get_db_session
    from backend.db.models import SchedulerJobRun, SystemState

    run_id = None
    started_at = datetime.utcnow()

    async with get_db_session() as db:
        run = SchedulerJobRun(
            job_name=job_name,
            started_at=started_at,
            status=JobStatus.STARTED,
        )
        db.add(run)
        await db.flush()
        run_id = run.id
        logger.info("scheduler.job.start", job=job_name, run_id=run_id)

    try:
        result_payload = await fn()
        status = JobStatus.SUCCESS
        error_msg = None
        logger.info("scheduler.job.success", job=job_name, run_id=run_id)
    except Exception as exc:
        result_payload = None
        status = JobStatus.FAILED
        error_msg = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        logger.error("scheduler.job.failed", job=job_name, run_id=run_id, error=str(exc))

    finished_at = datetime.utcnow()
    duration_s = (finished_at - started_at).total_seconds()
    serialized_result = _serialize_job_result(result_payload)
    details_json = {"duration_seconds": duration_s}
    if serialized_result is not None:
        details_json["result"] = serialized_result

    async with get_db_session() as db:
        from sqlalchemy import select, update
        await db.execute(
            update(SchedulerJobRun)
            .where(SchedulerJobRun.id == run_id)
            .values(
                finished_at=finished_at,
                status=status,
                error_message=error_msg,
                details_json=details_json,
            )
        )
        # Upsert system_state
        result = await db.execute(
            select(SystemState).where(SystemState.component_name == job_name)
        )
        state = result.scalar_one_or_none()
        if state:
            state.status = "healthy" if status == JobStatus.SUCCESS else "degraded"
            state.last_run_at = finished_at
            state.last_error = error_msg
            state.metadata_json = details_json
        else:
            db.add(
                SystemState(
                    component_name=job_name,
                    status="healthy" if status == JobStatus.SUCCESS else "degraded",
                    last_run_at=finished_at,
                    last_error=error_msg,
                    metadata_json=details_json,
                    updated_at=finished_at,
                )
            )

    return {
        "job_name": job_name,
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "details": details_json,
        "error_message": error_msg,
    }


# ── Job implementations ───────────────────────────────────────────────────────

async def _market_data_ingest_job() -> None:
    from backend.services.market_data.service import ingest_all_timeframes
    return await ingest_all_timeframes()


async def _trading_brain_job() -> None:
    from backend.services.risk_guardian.brain import run_trading_brain
    return await run_trading_brain()


async def _trade_reconcile_job() -> None:
    from backend.services.trade_lifecycle.service import reconcile_open_trades
    return await reconcile_open_trades()


async def _self_healing_backtest_job() -> None:
    from backend.services.self_healing.engine import run_backtest_validation_cycle
    return await run_backtest_validation_cycle()


async def _param_search_monte_carlo_job() -> None:
    from backend.services.self_healing.engine import run_optimization_cycle
    return await run_optimization_cycle()


async def _risk_monitor_job() -> None:
    from backend.services.risk_guardian.service import run_risk_monitor
    return await run_risk_monitor()


async def _daily_reset_job() -> None:
    from backend.services.pnl.service import perform_daily_reset
    return await perform_daily_reset()


async def _health_check_job() -> None:
    from backend.services.system_health.service import run_health_check
    return await run_health_check()


async def _dashboard_refresh_job() -> None:
    """Lightweight job that pre-computes cached dashboard metrics."""
    pass  # Phase 6: hook into caching layer


JOB_FUNCTIONS: dict[str, Callable[[], Awaitable[Any]]] = {
    JobName.MARKET_DATA_INGEST: _market_data_ingest_job,
    JobName.TRADING_BRAIN: _trading_brain_job,
    JobName.TRADE_RECONCILE: _trade_reconcile_job,
    JobName.SELF_HEALING_BACKTEST: _self_healing_backtest_job,
    JobName.PARAM_SEARCH_MONTE_CARLO: _param_search_monte_carlo_job,
    JobName.RISK_MONITOR: _risk_monitor_job,
    JobName.DAILY_RESET: _daily_reset_job,
    JobName.HEALTH_CHECK: _health_check_job,
    JobName.DASHBOARD_REFRESH: _dashboard_refresh_job,
}


def get_job_names() -> list[str]:
    return list(JOB_FUNCTIONS.keys())


async def run_job_now(job_name: str) -> dict[str, Any]:
    if job_name not in JOB_FUNCTIONS:
        raise KeyError(job_name)
    return await _run_job(job_name, JOB_FUNCTIONS[job_name])


# ── Scheduler setup ───────────────────────────────────────────────────────────

async def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")

    # Market data — every N minutes
    _scheduler.add_job(
        lambda: asyncio.create_task(
            _run_job(JobName.MARKET_DATA_INGEST, _market_data_ingest_job)
        ),
        trigger=IntervalTrigger(minutes=settings.market_data_ingestion_interval_minutes),
        id=JobName.MARKET_DATA_INGEST,
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    # Trading brain — every 30 min
    _scheduler.add_job(
        lambda: asyncio.create_task(
            _run_job(JobName.TRADING_BRAIN, _trading_brain_job)
        ),
        trigger=IntervalTrigger(minutes=settings.brain_interval_minutes),
        id=JobName.TRADING_BRAIN,
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=120,
    )

    # Trade reconciliation — every 5 min
    _scheduler.add_job(
        lambda: asyncio.create_task(
            _run_job(JobName.TRADE_RECONCILE, _trade_reconcile_job)
        ),
        trigger=IntervalTrigger(minutes=settings.trade_reconcile_interval_minutes),
        id=JobName.TRADE_RECONCILE,
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )

    # Self-healing backtest — every 4 hours
    _scheduler.add_job(
        lambda: asyncio.create_task(
            _run_job(JobName.SELF_HEALING_BACKTEST, _self_healing_backtest_job)
        ),
        trigger=IntervalTrigger(hours=settings.backtest_interval_hours),
        id=JobName.SELF_HEALING_BACKTEST,
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )

    # Parameter search + Monte Carlo — every 6 hours (configurable)
    _scheduler.add_job(
        lambda: asyncio.create_task(
            _run_job(JobName.PARAM_SEARCH_MONTE_CARLO, _param_search_monte_carlo_job)
        ),
        trigger=IntervalTrigger(hours=settings.param_search_interval_hours),
        id=JobName.PARAM_SEARCH_MONTE_CARLO,
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )

    # Risk monitor — every 1 min
    _scheduler.add_job(
        lambda: asyncio.create_task(
            _run_job(JobName.RISK_MONITOR, _risk_monitor_job)
        ),
        trigger=IntervalTrigger(minutes=1),
        id=JobName.RISK_MONITOR,
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )

    # Daily reset — midnight UTC
    _scheduler.add_job(
        lambda: asyncio.create_task(
            _run_job(JobName.DAILY_RESET, _daily_reset_job)
        ),
        trigger=CronTrigger(hour=0, minute=0),
        id=JobName.DAILY_RESET,
        replace_existing=True,
        max_instances=1,
    )

    # Health check — every 10 min
    _scheduler.add_job(
        lambda: asyncio.create_task(
            _run_job(JobName.HEALTH_CHECK, _health_check_job)
        ),
        trigger=IntervalTrigger(minutes=settings.health_check_interval_minutes),
        id=JobName.HEALTH_CHECK,
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    # Dashboard refresh — every 2 min
    _scheduler.add_job(
        lambda: asyncio.create_task(
            _run_job(JobName.DASHBOARD_REFRESH, _dashboard_refresh_job)
        ),
        trigger=IntervalTrigger(minutes=2),
        id=JobName.DASHBOARD_REFRESH,
        replace_existing=True,
        max_instances=1,
    )

    _scheduler.start()
    logger.info("scheduler.started", jobs=len(_scheduler.get_jobs()))


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler.stopped")
    _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
