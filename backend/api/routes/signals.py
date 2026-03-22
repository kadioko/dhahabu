"""Signal endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.common import SignalSchema
from backend.db.base import get_db
from backend.db.models import Signal

router = APIRouter()


@router.get("", response_model=List[SignalSchema])
async def list_signals(
    symbol: str = Query(default="XAU/USD"),
    approval_status: Optional[str] = Query(default=None),
    strategy_name: Optional[str] = Query(default=None),
    hours: int = Query(default=24),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Return recent signals with optional filters."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    conditions = [Signal.symbol == symbol, Signal.created_at >= cutoff]
    if approval_status:
        conditions.append(Signal.approval_status == approval_status)
    if strategy_name:
        conditions.append(Signal.strategy_name == strategy_name)

    result = await db.execute(
        select(Signal).where(and_(*conditions)).order_by(Signal.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.get("/active", response_model=List[SignalSchema])
async def get_active_signals(
    symbol: str = Query(default="XAU/USD"),
    db: AsyncSession = Depends(get_db),
):
    """Return approved signals from the last 4 hours (not yet expired)."""
    cutoff = datetime.utcnow() - timedelta(hours=4)
    result = await db.execute(
        select(Signal)
        .where(
            and_(
                Signal.symbol == symbol,
                Signal.approval_status == "approved",
                Signal.created_at >= cutoff,
            )
        )
        .order_by(Signal.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{signal_id}", response_model=SignalSchema)
async def get_signal(signal_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal
