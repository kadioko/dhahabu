"""
Platform-wide constants and enumerations.
"""

from __future__ import annotations

from enum import Enum


# ── Symbols ───────────────────────────────────────────────────────────────────

class Symbol(str, Enum):
    XAUUSD = "XAU/USD"

    def __str__(self) -> str:
        return self.value


# ── Timeframes ────────────────────────────────────────────────────────────────

class Timeframe(str, Enum):
    """Supported candle timeframes mapped to Twelve Data interval strings."""
    M1 = "1min"
    M15 = "15min"
    H1 = "1h"
    H4 = "4h"
    D1 = "1day"

    def __str__(self) -> str:
        return self.value

    @property
    def minutes(self) -> int:
        mapping = {
            "1min": 1,
            "15min": 15,
            "1h": 60,
            "4h": 240,
            "1day": 1440,
        }
        return mapping[self.value]

    @property
    def label(self) -> str:
        mapping = {
            "1min": "M1",
            "15min": "M15",
            "1h": "H1",
            "4h": "H4",
            "1day": "D1",
        }
        return mapping[self.value]


LIVE_TIMEFRAMES: list[Timeframe] = [
    Timeframe.M15,
    Timeframe.H1,
    Timeframe.H4,
    Timeframe.D1,
]


# ── Strategies ────────────────────────────────────────────────────────────────

class StrategyName(str, Enum):
    LIQUIDITY_SWEEPS = "liquidity_sweeps"
    TREND_CONTINUATION = "trend_continuation"
    BREAKOUT_EXPANSION = "breakout_expansion"
    EMA_MOMENTUM = "ema_momentum"

    def __str__(self) -> str:
        return self.value


# ── Signal / Trade States ─────────────────────────────────────────────────────

class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"

    def __str__(self) -> str:
        return self.value


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SUPPRESSED = "suppressed"
    DOWNGRADED = "downgraded"

    def __str__(self) -> str:
        return self.value


class TradeStatus(str, Enum):
    PENDING = "pending"
    TRIGGERED = "triggered"
    OPEN = "open"
    TP_HIT = "tp_hit"
    SL_HIT = "sl_hit"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        return self.value


# ── Risk Events ───────────────────────────────────────────────────────────────

class RiskEventType(str, Enum):
    DAILY_LOSS_CAP = "daily_loss_cap"
    SHUTDOWN_TRIGGERED = "shutdown_triggered"
    SHUTDOWN_RESET = "shutdown_reset"
    EXPOSURE_BREACH = "exposure_breach"
    DUPLICATE_DIRECTION = "duplicate_direction"
    OVERFIT_SUPPRESSION = "overfit_suppression"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    VOLATILITY_REDUCTION = "volatility_reduction"
    DAILY_RESET = "daily_reset"

    def __str__(self) -> str:
        return self.value


class RiskSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    def __str__(self) -> str:
        return self.value


# ── Self-Healing ──────────────────────────────────────────────────────────────

class ValidationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    CONTINUE = "continue"
    FLAG_OVERFITTED = "flag_overfitted"
    PROMOTE_LIVE = "promote_live"
    THROW_AWAY = "throw_away"

    def __str__(self) -> str:
        return self.value


class ParameterSetStatus(str, Enum):
    CANDIDATE = "candidate"
    LIVE = "live"
    SUPPRESSED = "suppressed"
    DISCARDED = "discarded"

    def __str__(self) -> str:
        return self.value


# ── Scheduler Jobs ────────────────────────────────────────────────────────────

class JobName(str, Enum):
    MARKET_DATA_INGEST = "market_data_ingest"
    TRADING_BRAIN = "trading_brain"
    TRADE_RECONCILE = "trade_reconcile"
    SELF_HEALING_BACKTEST = "self_healing_backtest"
    PARAM_SEARCH_MONTE_CARLO = "param_search_monte_carlo"
    RISK_MONITOR = "risk_monitor"
    DAILY_RESET = "daily_reset"
    HEALTH_CHECK = "health_check"
    DASHBOARD_REFRESH = "dashboard_refresh"

    def __str__(self) -> str:
        return self.value


class JobStatus(str, Enum):
    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

    def __str__(self) -> str:
        return self.value


# ── System / Health ───────────────────────────────────────────────────────────

class ComponentStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    SHUTDOWN = "shutdown"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


# ── Volatility Regimes ────────────────────────────────────────────────────────

class VolatilityRegime(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"

    def __str__(self) -> str:
        return self.value


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    BREAKOUT = "breakout"
    CHOPPY = "choppy"

    def __str__(self) -> str:
        return self.value


# ── Candle fields ─────────────────────────────────────────────────────────────

OHLCV_FIELDS = ("open", "high", "low", "close", "volume")

# Telegram message types
class TelegramMessageType(str, Enum):
    SIGNAL = "signal"
    RISK_HALT = "risk_halt"
    SHUTDOWN = "shutdown"
    OVERFIT_FLAG = "overfit_flag"
    PARAM_PROMOTION = "param_promotion"
    DAILY_RESET = "daily_reset"
    SYSTEM_ALERT = "system_alert"

    def __str__(self) -> str:
        return self.value
