"""PnL endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.common import DailyPnLSchema
from backend.db.base import get_db
from backend.db.models import DailyPnLSnapshot

router = APIRouter()


@router.get("/daily", response_model=List[DailyPnLSchema])
async def get_daily_pnl(
    symbol: str = Query(default="XAU/USD"),
    days: int = Query(default=30),
    db: AsyncSession = Depends(get_db),
):
    """Return daily PnL snapshots for the given lookback period."""
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    result = await db.execute(
        select(DailyPnLSnapshot)
        .where(
            DailyPnLSnapshot.symbol == symbol,
            DailyPnLSnapshot.date >= cutoff,
        )
        .order_by(DailyPnLSnapshot.date.desc())
    )
    return result.scalars().all()


@router.get("/today")
async def get_today_pnl(
    symbol: str = Query(default="XAU/USD"),
    db: AsyncSession = Depends(get_db),
):
    """Return today's running PnL state."""
    from datetime import date
    today = date.today().isoformat()
    result = await db.execute(
        select(DailyPnLSnapshot).where(
            DailyPnLSnapshot.symbol == symbol,
            DailyPnLSnapshot.date == today,
        )
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        return {
            "date": today,
            "symbol": symbol,
            "realized_pnl": 0.0,
            "realized_pnl_pct": 0.0,
            "trading_blocked": False,
        }
    return {
        "date": snapshot.date,
        "symbol": snapshot.symbol,
        "realized_pnl": snapshot.realized_pnl,
        "realized_pnl_pct": snapshot.realized_pnl_pct,
        "max_drawdown": snapshot.max_drawdown,
        "trade_count": snapshot.trade_count,
        "win_count": snapshot.win_count,
        "loss_count": snapshot.loss_count,
        "trading_blocked": snapshot.trading_blocked,
    }
