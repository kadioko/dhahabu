"""
Risk Guardian Service.

Central risk state management. Checks:
  - Daily loss cap (max_daily_loss_pct)
  - Active shutdown (circuit breaker)
  - Consecutive stop-loss sequence
  - Total open exposure
  - Duplicate directional exposure
  - Max simultaneous trades

Also provides run_risk_monitor() for the scheduled risk monitoring job.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select

from backend.core.config import settings
from backend.core.constants import (
    RiskEventType,
    RiskSeverity,
    TradeStatus,
)
from backend.core.logging import get_logger
from backend.db.base import get_db_session
from backend.db.models import (
    DailyPnLSnapshot,
    RiskEvent,
    ShutdownEvent,
    Trade,
)

logger = get_logger(__name__)


@dataclass
class RiskState:
    """Snapshot of current risk environment."""
    # Daily PnL
    daily_realized_pnl: float
    daily_realized_pnl_pct: float
    daily_loss_cap_hit: bool
    trading_blocked: bool

    # Shutdown
    shutdown_active: bool
    shutdown_reason: Optional[str]
    shutdown_ends_at: Optional[datetime]
    shutdown_cooldown_remaining_hours: Optional[float]

    # Open positions
    open_trade_count: int
    open_trades_long: int
    open_trades_short: int
    estimated_open_exposure_pct: float

    # Consecutive losses
    consecutive_sl_hits: int

    # Derived
    can_trade: bool
    block_reason: Optional[str]


async def get_current_risk_state(db) -> dict:
    """Return current risk state as a serializable dict."""
    state = await _build_risk_state(db)
    return {
        "daily_realized_pnl": state.daily_realized_pnl,
        "daily_realized_pnl_pct": state.daily_realized_pnl_pct,
        "daily_loss_cap_hit": state.daily_loss_cap_hit,
        "trading_blocked": state.trading_blocked,
        "shutdown_active": state.shutdown_active,
        "shutdown_reason": state.shutdown_reason,
        "shutdown_ends_at": state.shutdown_ends_at.isoformat() if state.shutdown_ends_at else None,
        "shutdown_cooldown_remaining_hours": state.shutdown_cooldown_remaining_hours,
        "open_trade_count": state.open_trade_count,
        "open_trades_long": state.open_trades_long,
        "open_trades_short": state.open_trades_short,
        "estimated_open_exposure_pct": state.estimated_open_exposure_pct,
        "consecutive_sl_hits": state.consecutive_sl_hits,
        "can_trade": state.can_trade,
        "block_reason": state.block_reason,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def _build_risk_state(db) -> RiskState:
    today_str = date.today().isoformat()

    # ── Daily PnL ─────────────────────────────────────────────────────────────
    pnl_res = await db.execute(
        select(DailyPnLSnapshot).where(
            DailyPnLSnapshot.date == today_str,
            DailyPnLSnapshot.symbol == settings.market_data_symbol,
        )
    )
    pnl = pnl_res.scalar_one_or_none()
    daily_pnl = pnl.realized_pnl if pnl else 0.0
    daily_pnl_pct = pnl.realized_pnl_pct if pnl else 0.0
    trading_blocked = pnl.trading_blocked if pnl else False
    daily_cap_hit = trading_blocked or (daily_pnl_pct <= -settings.max_daily_loss_pct)

    # ── Shutdown ──────────────────────────────────────────────────────────────
    now = datetime.utcnow()
    shutdown_res = await db.execute(
        select(ShutdownEvent).where(ShutdownEvent.active == True).limit(1)
    )
    active_shutdown = shutdown_res.scalar_one_or_none()
    shutdown_active = False
    shutdown_reason = None
    shutdown_ends_at = None
    shutdown_cooldown = None

    if active_shutdown:
        if active_shutdown.ends_at > now:
            shutdown_active = True
            shutdown_reason = active_shutdown.reason
            shutdown_ends_at = active_shutdown.ends_at
            shutdown_cooldown = (active_shutdown.ends_at - now).total_seconds() / 3600
        else:
            # Auto-reset if configured
            if settings.auto_reset_after_shutdown:
                active_shutdown.active = False
                active_shutdown.reset_at = now
                await db.flush()

    # ── Open trades ───────────────────────────────────────────────────────────
    open_trades_res = await db.execute(
        select(Trade).where(Trade.status.in_(["pending", "triggered", "open"]))
    )
    open_trades = open_trades_res.scalars().all()
    open_count = len(open_trades)
    open_long = 0
    open_short = 0
    total_risk_pct = 0.0

    from backend.db.models import Signal
    for trade in open_trades:
        sig_res = await db.execute(select(Signal).where(Signal.id == trade.signal_id))
        sig = sig_res.scalar_one_or_none()
        if sig:
            if sig.direction == "long":
                open_long += 1
            else:
                open_short += 1
        # Estimate exposure from position size
        if trade.entry_price and trade.stop_loss and trade.position_size:
            sl_dist = abs(trade.entry_price - trade.stop_loss)
            risk = (sl_dist * 100 * trade.position_size) / settings.account_balance
            total_risk_pct += risk

    # ── Consecutive SL hits ───────────────────────────────────────────────────
    recent_trades_res = await db.execute(
        select(Trade)
        .where(Trade.status.in_(["sl_hit", "tp_hit"]))
        .order_by(Trade.exit_time.desc())
        .limit(20)
    )
    recent_trades = recent_trades_res.scalars().all()
    consecutive_sl = 0
    for t in recent_trades:
        if t.status == "sl_hit":
            consecutive_sl += 1
        else:
            break

    # ── Can trade? ────────────────────────────────────────────────────────────
    can_trade = True
    block_reason = None

    if shutdown_active:
        can_trade = False
        block_reason = f"24h shutdown: {shutdown_reason}"
    elif daily_cap_hit:
        can_trade = False
        block_reason = f"Daily loss cap hit ({daily_pnl_pct:.2%})"
    elif open_count >= settings.max_simultaneous_trades:
        can_trade = False
        block_reason = f"Max simultaneous trades reached ({open_count})"

    return RiskState(
        daily_realized_pnl=daily_pnl,
        daily_realized_pnl_pct=daily_pnl_pct,
        daily_loss_cap_hit=daily_cap_hit,
        trading_blocked=trading_blocked or daily_cap_hit,
        shutdown_active=shutdown_active,
        shutdown_reason=shutdown_reason,
        shutdown_ends_at=shutdown_ends_at,
        shutdown_cooldown_remaining_hours=shutdown_cooldown,
        open_trade_count=open_count,
        open_trades_long=open_long,
        open_trades_short=open_short,
        estimated_open_exposure_pct=round(total_risk_pct, 4),
        consecutive_sl_hits=consecutive_sl,
        can_trade=can_trade,
        block_reason=block_reason,
    )


async def record_risk_event(
    event_type: RiskEventType,
    severity: RiskSeverity,
    message: str,
    metadata: dict | None = None,
) -> None:
    """Persist a risk event to the database."""
    async with get_db_session() as db:
        db.add(RiskEvent(
            event_type=event_type.value,
            severity=severity.value,
            message=message,
            metadata_json=metadata,
            created_at=datetime.utcnow(),
        ))


async def trigger_shutdown(reason: str, trigger_type: str = "consecutive_losses") -> None:
    """
    Activate a 24h circuit breaker shutdown.

    Persists the shutdown event and sends a Telegram alert.
    """
    now = datetime.utcnow()
    ends_at = now + timedelta(hours=settings.shutdown_duration_hours)

    async with get_db_session() as db:
        # Deactivate any existing shutdown
        from sqlalchemy import update
        await db.execute(
            update(ShutdownEvent)
            .where(ShutdownEvent.active == True)
            .values(active=False, reset_at=now)
        )
        db.add(ShutdownEvent(
            trigger_type=trigger_type,
            started_at=now,
            ends_at=ends_at,
            active=True,
            reason=reason,
        ))

    await record_risk_event(
        RiskEventType.SHUTDOWN_TRIGGERED,
        RiskSeverity.CRITICAL,
        f"24h shutdown triggered: {reason}",
        {"ends_at": ends_at.isoformat(), "trigger_type": trigger_type},
    )

    logger.critical("risk.shutdown.triggered", reason=reason, ends_at=ends_at.isoformat())

    # Telegram alert (non-blocking)
    try:
        from backend.telegram.service import send_risk_halt_alert
        await send_risk_halt_alert(reason, ends_at)
    except Exception as exc:
        logger.error("risk.shutdown.telegram_failed", error=str(exc))


async def run_risk_monitor() -> None:
    """
    Scheduled job: check consecutive losses and enforce circuit breaker.
    """
    async with get_db_session() as db:
        state = await _build_risk_state(db)

        # Check circuit breaker
        if (
            state.consecutive_sl_hits >= settings.consecutive_stop_losses_limit
            and not state.shutdown_active
        ):
            reason = (
                f"{state.consecutive_sl_hits} consecutive stop losses hit. "
                f"Triggering {settings.shutdown_duration_hours}h shutdown."
            )
            logger.warning("risk.monitor.circuit_breaker", consecutive_sl=state.consecutive_sl_hits)
            await trigger_shutdown(reason, trigger_type="consecutive_losses")

        # Check daily cap
        if state.daily_loss_cap_hit and not state.trading_blocked:
            # Update snapshot to mark trading_blocked
            today_str = date.today().isoformat()
            snap_res = await db.execute(
                select(DailyPnLSnapshot).where(
                    DailyPnLSnapshot.date == today_str,
                    DailyPnLSnapshot.symbol == settings.market_data_symbol,
                )
            )
            snap = snap_res.scalar_one_or_none()
            if snap:
                snap.trading_blocked = True
            await record_risk_event(
                RiskEventType.DAILY_LOSS_CAP,
                RiskSeverity.CRITICAL,
                f"Daily loss cap reached: {state.daily_realized_pnl_pct:.2%}",
            )
