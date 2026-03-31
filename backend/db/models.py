"""
All SQLAlchemy ORM models for Dhahabu.

Tables are grouped logically:
  - Market Data
  - Signals & Trades
  - Strategy Parameters
  - Validation (Backtest, Walk-Forward, Monte Carlo, Optimization)
  - Risk & PnL
  - System / Scheduler / Audit
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET DATA
# ═══════════════════════════════════════════════════════════════════════════════

class Candle(Base):
    """OHLCV candle data for any symbol / timeframe."""

    __tablename__ = "candles"
    __table_args__ = (
        Index("ix_candles_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
        Index("ix_candles_timestamp", "timestamp"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=True, default="twelve_data")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

class StrategyParameters(Base):
    """
    Versioned parameter sets for each strategy.

    Each strategy may have multiple parameter sets at different lifecycle stages.
    Only one set per strategy has is_live=True at any time.
    """

    __tablename__ = "strategy_parameters"
    __table_args__ = (
        Index("ix_sp_strategy_live", "strategy_name", "is_live"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    parameter_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_window: Mapped[str] = mapped_column(String(20), nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="candidate")
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    overfit_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    suppressed_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discard_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    # Relationships
    signals: Mapped[list["Signal"]] = relationship("Signal", back_populates="parameter_set")
    backtest_runs: Mapped[list["BacktestRun"]] = relationship(
        "BacktestRun", back_populates="parameter_set"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNALS & TRADES
# ═══════════════════════════════════════════════════════════════════════════════

class Signal(Base):
    """
    Trading signal emitted by a strategy.

    Every signal produced by the trading brain is persisted, whether approved
    or suppressed. The brain_score and approval_status fields capture the
    full decision audit trail.
    """

    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signals_strategy_created", "strategy_name", "created_at"),
        Index("ix_signals_approval", "approval_status"),
        Index("ix_signals_symbol_created", "symbol", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    parameter_set_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("strategy_parameters.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    entry: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rationale_json: Mapped[dict] = mapped_column(JSONB, nullable=True)
    brain_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    suppression_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Relationships
    parameter_set: Mapped["StrategyParameters | None"] = relationship(
        "StrategyParameters", back_populates="signals"
    )
    trade: Mapped["Trade | None"] = relationship("Trade", back_populates="signal", uselist=False)
    telegram_delivery: Mapped["TelegramDeliveryLog | None"] = relationship(
        "TelegramDeliveryLog", back_populates="signal", uselist=False
    )


class Trade(Base):
    """
    Live trade lifecycle record linked to a signal.

    Candle-driven execution updates the status through the defined state machine:
    pending -> triggered -> open -> (tp_hit | sl_hit | expired | cancelled)
    """

    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_status", "status"),
        Index("ix_trades_signal_id", "signal_id"),
        Index("ix_trades_entry_time", "entry_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("signals.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    entry_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False)
    position_size: Mapped[float] = mapped_column(Float, nullable=False, default=0.01)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    closed_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consecutive_loss_seq_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    # Relationships
    signal: Mapped["Signal"] = relationship("Signal", back_populates="trade")


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION (BACKTEST / WALK-FORWARD / MONTE CARLO / OPTIMIZATION)
# ═══════════════════════════════════════════════════════════════════════════════

class BacktestRun(Base):
    """A single backtest execution result for a strategy parameter set."""

    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_br_strategy_created", "strategy_name", "created_at"),
        Index("ix_br_param_set", "parameter_set_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    parameter_set_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("strategy_parameters.id"), nullable=False
    )
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[float] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[float] = mapped_column(Float, nullable=True)
    sharpe_score: Mapped[float] = mapped_column(Float, nullable=True)
    expectancy: Mapped[float] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=True)
    metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Relationships
    parameter_set: Mapped["StrategyParameters"] = relationship(
        "StrategyParameters", back_populates="backtest_runs"
    )
    monte_carlo_runs: Mapped[list["MonteCarloRun"]] = relationship(
        "MonteCarloRun", back_populates="source_backtest_run"
    )


class WalkForwardRun(Base):
    """Walk-forward validation result comparing in-sample vs out-of-sample."""

    __tablename__ = "walk_forward_runs"
    __table_args__ = (
        Index("ix_wfr_strategy_created", "strategy_name", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    parameter_set_id: Mapped[str] = mapped_column(String(36), nullable=False)
    train_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    test_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    train_metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=True)
    test_metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=True)
    oos_degradation_score: Mapped[float] = mapped_column(Float, nullable=True)
    overfit_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    oos_collapse_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MonteCarloRun(Base):
    """Monte Carlo robustness test result for a backtest run."""

    __tablename__ = "monte_carlo_runs"
    __table_args__ = (
        Index("ix_mcr_strategy_created", "strategy_name", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    parameter_set_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_backtest_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("backtest_runs.id"), nullable=False
    )
    simulation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    robustness_score: Mapped[float] = mapped_column(Float, nullable=False)
    random_beats_original: Mapped[float] = mapped_column(Float, nullable=False)
    pass_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)
    distribution_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Relationships
    source_backtest_run: Mapped["BacktestRun"] = relationship(
        "BacktestRun", back_populates="monte_carlo_runs"
    )


class OptimizationRun(Base):
    """Records a complete parameter search optimization cycle."""

    __tablename__ = "optimization_runs"
    __table_args__ = (
        Index("ix_or_strategy_created", "strategy_name", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    combos_tested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    winner_parameter_set_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    metrics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    all_results_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════════
# RISK & PNL
# ═══════════════════════════════════════════════════════════════════════════════

class RiskEvent(Base):
    """Audit log for all risk management decisions."""

    __tablename__ = "risk_events"
    __table_args__ = (
        Index("ix_re_type_created", "event_type", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DailyPnLSnapshot(Base):
    """End-of-day (and intraday) PnL snapshot per symbol."""

    __tablename__ = "daily_pnl_snapshots"
    __table_args__ = (
        Index("ix_dpnl_date_symbol", "date", "symbol"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, default="XAU/USD")
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    realized_pnl_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    loss_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trading_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM STATE & SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════════

class SystemState(Base):
    """
    Per-component runtime state. Each named component has exactly one row,
    updated in-place (upsert pattern).
    """

    __tablename__ = "system_state"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    component_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    health_score: Mapped[float] = mapped_column(Float, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class SchedulerJobRun(Base):
    """Execution record for every scheduler job invocation."""

    __tablename__ = "scheduler_job_runs"
    __table_args__ = (
        Index("ix_sjr_job_started", "job_name", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="started")
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEvent(Base):
    """
    General purpose audit log.

    Any significant platform decision (signal approval, suppression, promotion,
    circuit breaker, risk halt) is stored here for full observability.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_ae_event_type_created", "event_type", "created_at"),
        Index("ix_ae_entity_type_id", "entity_type", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor: Mapped[str] = mapped_column(String(50), nullable=False, default="system")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TelegramDeliveryLog(Base):
    """Delivery tracking for every Telegram message attempt."""

    __tablename__ = "telegram_delivery_logs"
    __table_args__ = (
        Index("ix_tdl_signal_id", "signal_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("signals.id"), nullable=True
    )
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    telegram_message_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    signal: Mapped["Signal | None"] = relationship("Signal", back_populates="telegram_delivery")


class ShutdownEvent(Base):
    """Circuit breaker shutdown record."""

    __tablename__ = "shutdown_events"
    __table_args__ = (
        Index("ix_se_active", "active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
