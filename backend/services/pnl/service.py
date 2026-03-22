"""PnL Service — daily reset and snapshot management."""

from __future__ import annotations

from datetime import date, datetime

from backend.core.config import settings
from backend.core.constants import RiskEventType, RiskSeverity
from backend.core.logging import get_logger
from backend.db.base import get_db_session
from backend.db.models import DailyPnLSnapshot

logger = get_logger(__name__)


async def perform_daily_reset() -> None:
    """
    Midnight reset job.

    Creates a fresh DailyPnLSnapshot for the new trading day and
    unlocks trading if it was blocked by the previous day's loss cap.
    """
    today_str = date.today().isoformat()
    now = datetime.utcnow()

    async with get_db_session() as db:
        from sqlalchemy import select
        existing = await db.execute(
            select(DailyPnLSnapshot).where(
                DailyPnLSnapshot.date == today_str,
                DailyPnLSnapshot.symbol == settings.market_data_symbol,
            )
        )
        if not existing.scalar_one_or_none():
            db.add(DailyPnLSnapshot(
                date=today_str,
                symbol=settings.market_data_symbol,
                realized_pnl=0.0,
                realized_pnl_pct=0.0,
                max_drawdown=0.0,
                trade_count=0,
                win_count=0,
                loss_count=0,
                trading_blocked=False,
                created_at=now,
                updated_at=now,
            ))

    from backend.services.risk_guardian.service import record_risk_event
    await record_risk_event(
        RiskEventType.DAILY_RESET,
        RiskSeverity.INFO,
        f"Daily reset complete for {today_str}",
    )
    logger.info("pnl.daily_reset.done", date=today_str)
