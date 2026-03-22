"""Candle data endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.common import CandleSchema, PaginatedResponse
from backend.db.base import get_db
from backend.db.models import Candle

router = APIRouter()


@router.get("/latest", response_model=dict)
async def get_latest_candles(
    symbol: str = Query(default="XAU/USD"),
    timeframe: str = Query(default="15min"),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Return the N most recent candles for a symbol/timeframe."""
    result = await db.execute(
        select(Candle)
        .where(and_(Candle.symbol == symbol, Candle.timeframe == timeframe))
        .order_by(Candle.timestamp.desc())
        .limit(limit)
    )
    candles = result.scalars().all()
    candles_sorted = sorted(candles, key=lambda c: c.timestamp)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(candles_sorted),
        "candles": [c.to_dict() for c in candles_sorted],
    }


@router.get("/timeframes", response_model=List[str])
async def get_available_timeframes(
    symbol: str = Query(default="XAU/USD"),
    db: AsyncSession = Depends(get_db),
):
    """Return available timeframes for a symbol."""
    from sqlalchemy import distinct
    result = await db.execute(
        select(distinct(Candle.timeframe)).where(Candle.symbol == symbol)
    )
    return result.scalars().all()


@router.get("/symbols", response_model=List[str])
async def get_available_symbols(db: AsyncSession = Depends(get_db)):
    """Return all symbols with candle data."""
    from sqlalchemy import distinct
    result = await db.execute(select(distinct(Candle.symbol)))
    return result.scalars().all()
