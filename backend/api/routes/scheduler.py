"""Scheduler job monitoring endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.common import SchedulerJobRunSchema
from backend.db.base import get_db
from backend.db.models import SchedulerJobRun

router = APIRouter()


@router.get("/jobs/names")
async def get_scheduler_job_names():
    from backend.scheduler.service import get_job_names

    return {"jobs": get_job_names()}


@router.get("/jobs", response_model=List[SchedulerJobRunSchema])
async def get_job_runs(
    job_name: str | None = Query(default=None),
    hours: int = Query(default=24),
    limit: int = Query(default=50),
    db: AsyncSession = Depends(get_db),
):
    """Return recent scheduler job executions."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = select(SchedulerJobRun).where(SchedulerJobRun.started_at >= cutoff)
    if job_name:
        q = q.where(SchedulerJobRun.job_name == job_name)
    result = await db.execute(q.order_by(SchedulerJobRun.started_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/jobs/latest")
async def get_latest_job_status(db: AsyncSession = Depends(get_db)):
    """Return the most recent run for each job."""
    from sqlalchemy import func
    # Get the latest run per job name
    subq = (
        select(
            SchedulerJobRun.job_name,
            func.max(SchedulerJobRun.started_at).label("max_started"),
        )
        .group_by(SchedulerJobRun.job_name)
        .subquery()
    )
    result = await db.execute(
        select(SchedulerJobRun).join(
            subq,
            (SchedulerJobRun.job_name == subq.c.job_name)
            & (SchedulerJobRun.started_at == subq.c.max_started),
        )
    )
    jobs = result.scalars().all()
    return {
        "jobs": [
            {
                "job_name": j.job_name,
                "started_at": j.started_at.isoformat(),
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
                "status": j.status,
                "details_json": j.details_json,
                "error_message": j.error_message,
            }
            for j in jobs
        ]
    }


@router.post("/jobs/{job_name}/run")
async def run_scheduler_job(job_name: str):
    from backend.scheduler.service import get_job_names, run_job_now

    if job_name not in get_job_names():
        raise HTTPException(status_code=404, detail=f"Unknown job {job_name!r}")

    result = await run_job_now(job_name)
    return {"success": True, **result}
