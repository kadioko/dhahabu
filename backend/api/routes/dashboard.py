"""Dashboard summary endpoint — single call powers the main dashboard view."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.base import get_db
from backend.db.models import (
    DailyPnLSnapshot,
    ShutdownEvent,
    Signal,
    StrategyParameters,
    SystemState,
    Trade,
)

router = APIRouter()


@router.get("/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """
    Aggregated summary for the dashboard home page.
    Combines risk state, PnL, active signals, open trades, strategy rankings.
    """
    today_str = date.today().isoformat()
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)

    # ── Today's PnL ──────────────────────────────────────────────────────────
    pnl_res = await db.execute(
        select(DailyPnLSnapshot).where(
            DailyPnLSnapshot.date == today_str,
            DailyPnLSnapshot.symbol == "XAU/USD",
        )
    )
    pnl_snap = pnl_res.scalar_one_or_none()

    # ── Active shutdown ───────────────────────────────────────────────────────
    shutdown_res = await db.execute(
        select(ShutdownEvent).where(ShutdownEvent.active == True).limit(1)
    )
    active_shutdown = shutdown_res.scalar_one_or_none()

    # ── Open trades count ─────────────────────────────────────────────────────
    open_trades_res = await db.execute(
        select(func.count(Trade.id)).where(Trade.status.in_(["pending", "triggered", "open"]))
    )
    open_trades_count = open_trades_res.scalar() or 0

    # ── Active signals (approved, last 4h) ────────────────────────────────────
    cutoff_4h = datetime.utcnow() - timedelta(hours=4)
    active_signals_res = await db.execute(
        select(func.count(Signal.id)).where(
            and_(
                Signal.approval_status == "approved",
                Signal.created_at >= cutoff_4h,
            )
        )
    )
    active_signals_count = active_signals_res.scalar() or 0

    # ── Live strategy count ────────────────────────────────────────────────────
    live_strats_res = await db.execute(
        select(func.count(StrategyParameters.id)).where(StrategyParameters.is_live == True)
    )
    live_strats_count = live_strats_res.scalar() or 0

    # ── System health overview ────────────────────────────────────────────────
    components_res = await db.execute(select(SystemState))
    components = components_res.scalars().all()
    healthy_count = sum(1 for c in components if c.status == "healthy")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "trading_mode": "shutdown" if active_shutdown else "active",
        "shutdown": {
            "active": bool(active_shutdown),
            "reason": active_shutdown.reason if active_shutdown else None,
            "ends_at": active_shutdown.ends_at.isoformat() if active_shutdown else None,
        },
        "pnl_today": {
            "realized_pnl": pnl_snap.realized_pnl if pnl_snap else 0.0,
            "realized_pnl_pct": pnl_snap.realized_pnl_pct if pnl_snap else 0.0,
            "trading_blocked": pnl_snap.trading_blocked if pnl_snap else False,
            "trade_count": pnl_snap.trade_count if pnl_snap else 0,
            "win_count": pnl_snap.win_count if pnl_snap else 0,
            "loss_count": pnl_snap.loss_count if pnl_snap else 0,
        },
        "open_trades": open_trades_count,
        "active_signals": active_signals_count,
        "live_strategies": live_strats_count,
        "system_health": {
            "healthy_components": healthy_count,
            "total_components": len(components),
            "health_pct": round(healthy_count / max(len(components), 1) * 100, 1),
        },
    }
