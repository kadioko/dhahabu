"""
Shared Pydantic schemas used across multiple routes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard envelope for all API responses."""

    success: bool = True
    data: T
    message: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    items: List[T]
    total: int
    page: int
    page_size: int
    has_more: bool


class CandleSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class SignalSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    strategy_name: str
    parameter_set_id: Optional[str] = None
    symbol: str
    timeframe: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    confidence: float
    rationale_json: Optional[dict] = None
    brain_score: Optional[float] = None
    approval_status: str
    suppression_reason: Optional[str] = None
    risk_metadata_json: Optional[dict] = None
    created_at: datetime


class TradeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    signal_id: str
    status: str
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    stop_loss: float
    take_profit: float
    position_size: float
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    closed_reason: Optional[str] = None
    consecutive_loss_seq_snapshot: int
    created_at: datetime


class StrategyParametersSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    strategy_name: str
    parameter_json: dict
    source_window: Optional[str] = None
    score: Optional[float] = None
    status: str
    is_live: bool
    overfit_flag: bool
    suppressed_flag: bool
    promoted_at: Optional[datetime] = None
    discarded_at: Optional[datetime] = None
    discard_reason: Optional[str] = None
    created_at: datetime


class BacktestRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    strategy_name: str
    parameter_set_id: str
    window_days: int
    start_at: datetime
    end_at: datetime
    total_trades: int
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    sharpe_score: Optional[float] = None
    expectancy: Optional[float] = None
    max_drawdown: Optional[float] = None
    metrics_json: Optional[dict] = None
    created_at: datetime


class WalkForwardRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    strategy_name: str
    parameter_set_id: str
    train_ratio: float
    test_ratio: float
    train_metrics_json: Optional[dict] = None
    test_metrics_json: Optional[dict] = None
    oos_degradation_score: Optional[float] = None
    overfit_flag: bool
    oos_collapse_details: Optional[dict] = None
    created_at: datetime


class MonteCarloRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    strategy_name: str
    parameter_set_id: str
    source_backtest_run_id: str
    simulation_count: int
    robustness_score: float
    random_beats_original: float
    pass_flag: bool
    distribution_json: Optional[dict] = None
    created_at: datetime


class RiskEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    severity: str
    message: str
    metadata_json: Optional[dict] = None
    created_at: datetime


class DailyPnLSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    date: str
    symbol: str
    realized_pnl: float
    realized_pnl_pct: float
    max_drawdown: float
    trade_count: int
    win_count: int
    loss_count: int
    trading_blocked: bool
    updated_at: datetime


class ShutdownEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trigger_type: str
    trigger_value: Optional[str] = None
    started_at: datetime
    ends_at: datetime
    active: bool
    reason: str
    reset_at: Optional[datetime] = None


class SchedulerJobRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_name: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    details_json: Optional[dict] = None
    error_message: Optional[str] = None


class SystemStateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    component_name: str
    status: str
    health_score: Optional[float] = None
    last_run_at: Optional[datetime] = None
    last_error: Optional[str] = None
    metadata_json: Optional[dict] = None
    updated_at: datetime
