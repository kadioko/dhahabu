"""
Trade Lifecycle Service.

Simulates broker execution using candle data.

State machine:
  pending   → triggered  (when current price reaches entry zone)
  triggered → open       (confirmed fill)
  open      → tp_hit     (high reaches take_profit for longs / low for shorts)
  open      → sl_hit     (low reaches stop_loss for longs / high for shorts)
  open      → expired    (trade exceeds max holding period)
  pending   → cancelled  (signal expired before triggering)

Each state change updates the trade record and feeds outcomes back into
the PnL service and consecutive loss tracker.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.base import get_db_session
from backend.db.models import Candle, DailyPnLSnapshot, Signal, Trade
from backend.services.broker import get_broker
from backend.services.broker.base import OrderSide, PlaceOrderRequest

logger = get_logger(__name__)

MAX_TRADE_HOURS = 48  # Auto-expire after 48h


async def reconcile_open_trades() -> dict:
    """
    Check all open/pending trades against the latest candles and update states.

    Called every 5 minutes by the scheduler.
    Returns stats dict.
    """
    stats = {"checked": 0, "updated": 0, "tp_hit": 0, "sl_hit": 0, "expired": 0}

    async with get_db_session() as db:
        active_res = await db.execute(
            select(Trade).where(Trade.status.in_(["pending", "triggered", "open"]))
        )
        active_trades = active_res.scalars().all()
        stats["checked"] = len(active_trades)

        for trade in active_trades:
            original_status = trade.status
            updated = await _process_trade(trade, db)
            if updated:
                stats["updated"] += 1
                if trade.status == "tp_hit":
                    stats["tp_hit"] += 1
                elif trade.status == "sl_hit":
                    stats["sl_hit"] += 1
                elif trade.status == "expired":
                    stats["expired"] += 1

    logger.info("trade_lifecycle.reconcile.done", **stats)
    return stats


async def _process_trade(trade: Trade, db) -> bool:
    """Process a single trade against latest candle. Returns True if state changed."""
    sig_res = await db.execute(select(Signal).where(Signal.id == trade.signal_id))
    signal = sig_res.scalar_one_or_none()
    if not signal:
        return False

    candle_res = await db.execute(
        select(Candle)
        .where(
            and_(
                Candle.symbol == signal.symbol,
                Candle.timeframe == signal.timeframe,
            )
        )
        .order_by(Candle.timestamp.desc())
        .limit(1)
    )
    latest_candle = candle_res.scalar_one_or_none()
    if not latest_candle:
        return False

    now = datetime.utcnow()
    changed = False
    direction = signal.direction

    # ── Pending → Triggered ───────────────────────────────────────────────────
    if trade.status == "pending":
        if (now - trade.created_at).total_seconds() > 24 * 3600:
            trade.status = "cancelled"
            trade.closed_reason = "no_trigger_expired"
            trade.updated_at = now
            changed = True
        else:
            candle_high = latest_candle.high
            candle_low = latest_candle.low
            entry = signal.entry
            triggered = False

            if direction == "long" and candle_low <= entry <= candle_high:
                triggered = True
            elif direction == "short" and candle_low <= entry <= candle_high:
                triggered = True
            elif direction == "long" and latest_candle.close >= entry * 0.999:
                triggered = True
            elif direction == "short" and latest_candle.close <= entry * 1.001:
                triggered = True

            if triggered:
                trade.status = "open"
                trade.entry_time = latest_candle.timestamp
                trade.entry_price = signal.entry
                trade.updated_at = now
                changed = True
                logger.info("trade.triggered", trade_id=trade.id, entry=signal.entry)

                # Submit to live broker (no-op for paper mode)
                broker = get_broker()
                if broker.name != "paper":
                    try:
                        req = PlaceOrderRequest(
                            signal_id=trade.signal_id,
                            side=OrderSide.BUY if direction == "long" else OrderSide.SELL,
                            units=trade.position_size,
                            entry=signal.entry,
                            stop_loss=trade.stop_loss,
                            take_profit=trade.take_profit,
                            symbol=signal.symbol,
                        )
                        result = await broker.place_order(req)
                        trade.broker_order_id = result.broker_order_id
                        if result.fill_price:
                            trade.entry_price = result.fill_price
                        logger.info(
                            "broker.order_placed",
                            broker=broker.name,
                            order_id=result.broker_order_id,
                            fill_price=result.fill_price,
                        )
                    except Exception as exc:
                        logger.error("broker.place_order.error", error=str(exc), trade_id=trade.id)

    # ── Open → Resolution ─────────────────────────────────────────────────────
    elif trade.status in ("triggered", "open"):
        entry_price = trade.entry_price or signal.entry
        candle_high = latest_candle.high
        candle_low = latest_candle.low

        tp_hit = (
            (direction == "long" and candle_high >= trade.take_profit) or
            (direction == "short" and candle_low <= trade.take_profit)
        )
        sl_hit = (
            (direction == "long" and candle_low <= trade.stop_loss) or
            (direction == "short" and candle_high >= trade.stop_loss)
        )
        entry_time = trade.entry_time or trade.created_at
        expired = (now - entry_time).total_seconds() > MAX_TRADE_HOURS * 3600

        # Worst-case: both on same candle → SL wins
        if sl_hit and tp_hit:
            tp_hit = False

        if tp_hit:
            exit_price = trade.take_profit
            pnl = _calc_pnl(direction, entry_price, exit_price, trade.position_size)
            trade.status = "tp_hit"
            trade.exit_time = latest_candle.timestamp
            trade.exit_price = exit_price
            trade.pnl = pnl
            trade.pnl_pct = pnl / settings.account_balance
            trade.closed_reason = "tp_hit"
            trade.updated_at = now
            changed = True
            await _update_daily_pnl(signal.symbol, pnl, is_win=True, db=db)

        elif sl_hit:
            exit_price = trade.stop_loss
            pnl = _calc_pnl(direction, entry_price, exit_price, trade.position_size)
            trade.status = "sl_hit"
            trade.exit_time = latest_candle.timestamp
            trade.exit_price = exit_price
            trade.pnl = pnl
            trade.pnl_pct = pnl / settings.account_balance
            trade.closed_reason = "sl_hit"
            trade.updated_at = now
            changed = True
            await _update_daily_pnl(signal.symbol, pnl, is_win=False, db=db)

        elif expired:
            exit_price = float(latest_candle.close)
            pnl = _calc_pnl(direction, entry_price, exit_price, trade.position_size)
            is_win = pnl > 0
            trade.status = "expired"
            trade.exit_time = latest_candle.timestamp
            trade.exit_price = exit_price
            trade.pnl = pnl
            trade.pnl_pct = pnl / settings.account_balance
            trade.closed_reason = "max_hold_expired"
            trade.updated_at = now
            changed = True
            await _update_daily_pnl(signal.symbol, pnl, is_win=is_win, db=db)

    return changed


def _calc_pnl(direction: str, entry: float, exit_price: float, lot_size: float) -> float:
    """
    PnL for XAUUSD: 1 lot = 100 oz.
    Long PnL = (exit - entry) * 100 * lots
    Short PnL = (entry - exit) * 100 * lots
    """
    if direction == "long":
        return round((exit_price - entry) * 100 * lot_size, 2)
    else:
        return round((entry - exit_price) * 100 * lot_size, 2)


async def _update_daily_pnl(symbol: str, pnl: float, is_win: bool, db) -> None:
    """Upsert daily PnL snapshot."""
    today_str = date.today().isoformat()
    now = datetime.utcnow()

    snap_res = await db.execute(
        select(DailyPnLSnapshot).where(
            DailyPnLSnapshot.date == today_str,
            DailyPnLSnapshot.symbol == symbol,
        )
    )
    snap = snap_res.scalar_one_or_none()

    if snap:
        snap.realized_pnl += pnl
        snap.realized_pnl_pct = snap.realized_pnl / settings.account_balance
        snap.trade_count += 1
        if is_win:
            snap.win_count += 1
        else:
            snap.loss_count += 1
        snap.max_drawdown = min(snap.max_drawdown, snap.realized_pnl_pct)
        snap.trading_blocked = snap.realized_pnl_pct <= -settings.max_daily_loss_pct
        snap.updated_at = now
    else:
        pnl_pct = pnl / settings.account_balance
        snap = DailyPnLSnapshot(
            date=today_str,
            symbol=symbol,
            realized_pnl=pnl,
            realized_pnl_pct=pnl_pct,
            max_drawdown=min(0.0, pnl_pct),
            trade_count=1,
            win_count=1 if is_win else 0,
            loss_count=0 if is_win else 1,
            trading_blocked=pnl_pct <= -settings.max_daily_loss_pct,
            created_at=now,
            updated_at=now,
        )
        db.add(snap)

    logger.info(
        "pnl.updated",
        symbol=symbol,
        pnl=pnl,
        is_win=is_win,
        daily_total=snap.realized_pnl,
    )
