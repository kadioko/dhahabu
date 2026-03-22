"""
Market Data Service — Twelve Data API integration.

Responsibilities:
  - Fetch OHLCV candle data for XAUUSD across all configured timeframes
  - Persist new candles (deduplicate by symbol/timeframe/timestamp)
  - Retry failed requests with exponential backoff
  - Report ingestion status to system_state
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.core.config import settings
from backend.core.constants import LIVE_TIMEFRAMES, Symbol, Timeframe
from backend.core.logging import get_logger
from backend.db.base import get_db_session
from backend.db.models import Candle

logger = get_logger(__name__)

# Twelve Data outputsize per request
_OUTPUT_SIZE = 200


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=1, min=2, max=32),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def _fetch_candles_from_api(
    client: httpx.AsyncClient,
    symbol: str,
    interval: str,
    outputsize: int = _OUTPUT_SIZE,
) -> list[dict]:
    """
    Fetch candles from Twelve Data.

    Returns a list of OHLCV dicts sorted oldest-first.
    """
    if not settings.twelve_data_api_key:
        logger.warning("market_data.no_api_key", symbol=symbol, interval=interval)
        return []

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": settings.twelve_data_api_key,
        "format": "JSON",
        "timezone": "UTC",
    }

    response = await client.get(
        f"{settings.twelve_data_base_url}/time_series",
        params=params,
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()

    if "values" not in data:
        logger.warning(
            "market_data.unexpected_response",
            symbol=symbol,
            interval=interval,
            status=data.get("status"),
            message=data.get("message"),
        )
        return []

    # Twelve Data returns newest-first; reverse to oldest-first
    return list(reversed(data["values"]))


async def _upsert_candles(raw_candles: list[dict], symbol: str, timeframe: str) -> int:
    """
    Persist candles to the database.

    Uses a simple SELECT-then-INSERT deduplication strategy keyed on
    (symbol, timeframe, timestamp). Returns the count of newly inserted rows.
    """
    if not raw_candles:
        return 0

    from sqlalchemy import and_, select

    inserted = 0
    async with get_db_session() as db:
        for raw in raw_candles:
            try:
                ts = datetime.fromisoformat(raw["datetime"].replace(" ", "T"))
            except (KeyError, ValueError) as exc:
                logger.warning("market_data.bad_candle", error=str(exc), raw=raw)
                continue

            # Dedup check
            existing = await db.execute(
                select(Candle).where(
                    and_(
                        Candle.symbol == symbol,
                        Candle.timeframe == timeframe,
                        Candle.timestamp == ts,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            candle = Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=ts,
                open=float(raw["open"]),
                high=float(raw["high"]),
                low=float(raw["low"]),
                close=float(raw["close"]),
                volume=float(raw.get("volume", 0) or 0),
                source="twelve_data",
                created_at=datetime.utcnow(),
            )
            db.add(candle)
            inserted += 1

    return inserted


async def ingest_timeframe(symbol: str, timeframe: Timeframe) -> dict:
    """Ingest a single symbol/timeframe combination. Returns ingestion stats."""
    logger.info("market_data.ingest.start", symbol=symbol, timeframe=timeframe.value)

    async with httpx.AsyncClient() as client:
        try:
            raw = await _fetch_candles_from_api(client, symbol, timeframe.value)
        except Exception as exc:
            logger.error(
                "market_data.ingest.fetch_failed",
                symbol=symbol,
                timeframe=timeframe.value,
                error=str(exc),
            )
            return {"symbol": symbol, "timeframe": timeframe.value, "inserted": 0, "error": str(exc)}

    inserted = await _upsert_candles(raw, symbol, timeframe.value)
    logger.info(
        "market_data.ingest.done",
        symbol=symbol,
        timeframe=timeframe.value,
        fetched=len(raw),
        inserted=inserted,
    )
    return {"symbol": symbol, "timeframe": timeframe.value, "fetched": len(raw), "inserted": inserted}


async def ingest_all_timeframes() -> list[dict]:
    """
    Ingest all configured timeframes concurrently.

    Rate-limits to avoid hitting Twelve Data's per-second limits.
    """
    symbol = settings.market_data_symbol
    results = []

    # Stagger requests slightly to respect Twelve Data rate limits
    for tf in LIVE_TIMEFRAMES:
        result = await ingest_timeframe(symbol, tf)
        results.append(result)
        await asyncio.sleep(0.5)

    total_inserted = sum(r.get("inserted", 0) for r in results)
    logger.info("market_data.ingest.all_done", total_inserted=total_inserted, symbol=symbol)
    return results


async def get_latest_candles_df(
    symbol: str,
    timeframe: Timeframe,
    limit: int = 200,
) -> "pd.DataFrame":
    """
    Return the latest N candles as a pandas DataFrame.

    Used by strategies and analysis services internally.
    Columns: timestamp, open, high, low, close, volume
    """
    import pandas as pd
    from sqlalchemy import select, and_

    async with get_db_session() as db:
        result = await db.execute(
            select(Candle)
            .where(and_(Candle.symbol == symbol, Candle.timeframe == timeframe.value))
            .order_by(Candle.timestamp.desc())
            .limit(limit)
        )
        candles = result.scalars().all()

    if not candles:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    rows = [
        {
            "timestamp": c.timestamp,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume or 0.0,
        }
        for c in reversed(candles)  # oldest first
    ]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp")
    return df
