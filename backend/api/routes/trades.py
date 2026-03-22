"""Trade lifecycle endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.common import TradeSchema
from backend.db.base import get_db
from backend.db.models import Trade

router = APIRouter()


@router.get("/open", response_model=List[TradeSchema])
async def get_open_trades(db: AsyncSession = Depends(get_db)):
    """Return all currently open trades."""
    result = await db.execute(
        select(Trade)
        .where(Trade.status.in_(["pending", "triggered", "open"]))
        .order_by(Trade.created_at.desc())
    )
    return result.scalars().all()


@router.get("/history", response_model=List[TradeSchema])
async def get_trade_history(
    days: int = Query(default=30),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Return closed trade history."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    conditions = [Trade.created_at >= cutoff]
    if status:
        conditions.append(Trade.status == status)
    else:
        conditions.append(Trade.status.in_(["tp_hit", "sl_hit", "expired", "cancelled"]))

    result = await db.execute(
        select(Trade).where(and_(*conditions)).order_by(Trade.exit_time.desc()).limit(limit)
    )
    return result.scalars().all()


@router.get("/{trade_id}", response_model=TradeSchema)
async def get_trade(trade_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade
