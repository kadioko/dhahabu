"""Risk management endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.common import RiskEventSchema, ShutdownEventSchema
from backend.db.base import get_db
from backend.db.models import RiskEvent, ShutdownEvent

router = APIRouter()


@router.get("/state")
async def get_risk_state(db: AsyncSession = Depends(get_db)):
    """Return current risk state: shutdown status, daily loss, consecutive losses."""
    from backend.services.risk_guardian.service import get_current_risk_state
    return await get_current_risk_state(db)


@router.get("/events", response_model=List[RiskEventSchema])
async def get_risk_events(
    hours: int = Query(default=24),
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Return recent risk events."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = select(RiskEvent).where(RiskEvent.created_at >= cutoff)
    if severity:
        q = q.where(RiskEvent.severity == severity)
    result = await db.execute(q.order_by(RiskEvent.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/shutdown", response_model=List[ShutdownEventSchema])
async def get_shutdown_events(
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    """Return shutdown events."""
    q = select(ShutdownEvent)
    if active_only:
        q = q.where(ShutdownEvent.active == True)
    result = await db.execute(q.order_by(ShutdownEvent.started_at.desc()).limit(20))
    return result.scalars().all()
