"""System state and health endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.common import SystemStateSchema
from backend.db.base import get_db
from backend.db.models import Candle, SchedulerJobRun, SystemState

router = APIRouter()


@router.get("/state", response_model=List[SystemStateSchema])
async def get_system_state(db: AsyncSession = Depends(get_db)):
    """Return current state of all tracked system components."""
    result = await db.execute(
        select(SystemState).order_by(SystemState.component_name)
    )
    return result.scalars().all()


@router.get("/overview")
async def get_system_overview(db: AsyncSession = Depends(get_db)):
    candle_counts_res = await db.execute(
        select(Candle.timeframe, func.count(Candle.id))
        .group_by(Candle.timeframe)
        .order_by(Candle.timeframe)
    )
    candle_counts = {timeframe: count for timeframe, count in candle_counts_res.all()}

    latest_candle_res = await db.execute(select(func.max(Candle.timestamp)))
    latest_candle_at = latest_candle_res.scalar_one_or_none()

    latest_successful_job_res = await db.execute(
        select(SchedulerJobRun)
        .where(SchedulerJobRun.status == "success")
        .order_by(SchedulerJobRun.started_at.desc())
        .limit(1)
    )
    latest_successful_job = latest_successful_job_res.scalar_one_or_none()

    latest_failed_job_res = await db.execute(
        select(SchedulerJobRun)
        .where(SchedulerJobRun.status == "failed")
        .order_by(SchedulerJobRun.started_at.desc())
        .limit(1)
    )
    latest_failed_job = latest_failed_job_res.scalar_one_or_none()

    latest_market_data_run_res = await db.execute(
        select(SchedulerJobRun)
        .where(SchedulerJobRun.job_name == "market_data_ingest")
        .order_by(SchedulerJobRun.started_at.desc())
        .limit(1)
    )
    latest_market_data_run = latest_market_data_run_res.scalar_one_or_none()

    components_res = await db.execute(select(func.count(SystemState.id)))
    component_count = components_res.scalar() or 0

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "latest_candle_at": latest_candle_at.isoformat() if latest_candle_at else None,
        "candle_counts": candle_counts,
        "component_count": component_count,
        "latest_successful_job": {
            "job_name": latest_successful_job.job_name,
            "started_at": latest_successful_job.started_at.isoformat(),
            "finished_at": latest_successful_job.finished_at.isoformat() if latest_successful_job.finished_at else None,
            "status": latest_successful_job.status,
        } if latest_successful_job else None,
        "latest_failed_job": {
            "job_name": latest_failed_job.job_name,
            "started_at": latest_failed_job.started_at.isoformat(),
            "finished_at": latest_failed_job.finished_at.isoformat() if latest_failed_job.finished_at else None,
            "status": latest_failed_job.status,
            "error_message": latest_failed_job.error_message,
        } if latest_failed_job else None,
        "latest_market_data_run": {
            "job_name": latest_market_data_run.job_name,
            "started_at": latest_market_data_run.started_at.isoformat(),
            "finished_at": latest_market_data_run.finished_at.isoformat() if latest_market_data_run.finished_at else None,
            "status": latest_market_data_run.status,
            "details_json": latest_market_data_run.details_json,
            "error_message": latest_market_data_run.error_message,
        } if latest_market_data_run else None,
    }


@router.get("/state/{component_name}", response_model=SystemStateSchema)
async def get_component_state(component_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SystemState).where(SystemState.component_name == component_name)
    )
    state = result.scalar_one_or_none()
    if not state:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Component {component_name!r} not found")
    return state
