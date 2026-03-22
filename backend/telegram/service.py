"""
Telegram Delivery Service.

All outbound Telegram messages route through this module.
Features:
  - Retry with exponential backoff (4 attempts)
  - Delivery logging to telegram_delivery_logs table
  - Message formatting for signals, risk alerts, and system events
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.core.config import settings
from backend.core.constants import TelegramMessageType
from backend.core.logging import get_logger
from backend.db.base import get_db_session
from backend.db.models import TelegramDeliveryLog

logger = get_logger(__name__)

_TELEGRAM_API = "https://api.telegram.org"


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=1, min=2, max=16),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def _send_message(text: str) -> str:
    """Send a message to the configured Telegram chat. Returns message_id."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("telegram.not_configured")
        return ""

    url = f"{_TELEGRAM_API}/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json={
            "chat_id": settings.telegram_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        response.raise_for_status()
        data = response.json()
        return str(data.get("result", {}).get("message_id", ""))


async def _deliver_and_log(
    text: str,
    message_type: TelegramMessageType,
    signal_id: Optional[str] = None,
) -> None:
    """Send message and log delivery result."""
    if not settings.telegram_enabled:
        return

    now = datetime.utcnow()
    telegram_msg_id = None
    delivered = False
    error_msg = None

    try:
        telegram_msg_id = await _send_message(text)
        delivered = True
        logger.info("telegram.delivered", message_type=message_type.value)
    except Exception as exc:
        error_msg = str(exc)
        logger.error("telegram.failed", message_type=message_type.value, error=error_msg)

    async with get_db_session() as db:
        db.add(TelegramDeliveryLog(
            signal_id=signal_id,
            message_type=message_type.value,
            message_text=text[:4000],  # Telegram limit
            delivered=delivered,
            attempts=4 if error_msg else 1,
            telegram_message_id=telegram_msg_id,
            error_message=error_msg,
            created_at=now,
            delivered_at=now if delivered else None,
        ))


def _format_signal(signal) -> str:
    """Format a Signal record for Telegram delivery."""
    direction_emoji = "🟢 LONG" if signal.direction == "long" else "🔴 SHORT"
    approval = signal.approval_status.upper()

    rationale = signal.rationale_json or {}
    regime = rationale.get("regime", "unknown")
    rationale_text = " | ".join(
        f"{k}: {v}" for k, v in rationale.items()
        if k not in ("atr",) and isinstance(v, (str, int, float, bool))
    )

    risk_meta = signal.risk_metadata_json or {}
    rr = risk_meta.get("risk_reward", 0)

    return (
        f"<b>📊 DHAHABU SIGNAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Strategy:</b> {signal.strategy_name.upper()}\n"
        f"<b>Symbol:</b> {signal.symbol} | <b>TF:</b> {signal.timeframe}\n"
        f"<b>Direction:</b> {direction_emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Entry:</b>  {signal.entry:.2f}\n"
        f"<b>SL:</b>     {signal.stop_loss:.2f}\n"
        f"<b>TP:</b>     {signal.take_profit:.2f}\n"
        f"<b>R:R:</b>    1:{rr:.1f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Confidence:</b> {signal.confidence:.1%}\n"
        f"<b>Brain Score:</b> {signal.brain_score:.1f}/100\n"
        f"<b>Regime:</b> {regime}\n"
        f"<b>Reason:</b> {rationale_text[:200]}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Status:</b> {approval}\n"
        f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"
    )


async def send_signal_batch(signals: list) -> None:
    """Send all approved signals to Telegram."""
    for signal in signals:
        if signal.approval_status == "approved":
            text = _format_signal(signal)
            await _deliver_and_log(text, TelegramMessageType.SIGNAL, signal_id=signal.id)
            await asyncio.sleep(0.5)  # Respect rate limits


async def send_risk_halt_alert(reason: str, ends_at: datetime) -> None:
    """Send a critical risk halt alert."""
    text = (
        f"🚨 <b>RISK HALT — 24H SHUTDOWN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Reason:</b> {reason}\n"
        f"<b>Resumes:</b> {ends_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"<b>Status:</b> All trading suspended\n"
        f"<i>No new signals will be generated during shutdown period.</i>"
    )
    await _deliver_and_log(text, TelegramMessageType.RISK_HALT)


async def send_daily_loss_alert(pnl_pct: float) -> None:
    """Send daily loss cap reached alert."""
    text = (
        f"⛔ <b>DAILY LOSS CAP REACHED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Daily PnL:</b> {pnl_pct:.2%}\n"
        f"<b>Cap:</b> {-settings.max_daily_loss_pct:.2%}\n"
        f"<b>Status:</b> Trading blocked for today\n"
        f"<i>Will reset at midnight UTC.</i>"
    )
    await _deliver_and_log(text, TelegramMessageType.RISK_HALT)


async def send_system_alert(message: str) -> None:
    """Send a general system alert (overfit flags, promotions, etc.)."""
    text = (
        f"⚙️ <b>DHAHABU SYSTEM ALERT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{message}\n"
        f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"
    )
    await _deliver_and_log(text, TelegramMessageType.SYSTEM_ALERT)
