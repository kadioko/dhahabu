"""
Base strategy interface.

All strategies implement the BaseStrategy protocol. Each strategy:
  - Accepts a StrategyContext (candle DataFrames for all timeframes)
  - Returns a list of StrategySignal objects (or empty list)
  - Is stateless — parameters are injected, no internal mutable state
  - Must be backtest-compatible via the backtest_engine
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from backend.core.constants import (
    MarketRegime,
    SignalDirection,
    StrategyName,
    Timeframe,
    VolatilityRegime,
)


@dataclass
class StrategyContext:
    """
    Candle data and market state passed to each strategy.

    DataFrames are indexed by datetime, columns: open, high, low, close, volume
    """
    symbol: str
    candles: dict[Timeframe, pd.DataFrame]  # All timeframes
    volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL
    market_regime: MarketRegime = MarketRegime.CHOPPY
    atr: float = 0.0
    current_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StrategySignal:
    """
    A single signal produced by a strategy.

    All fields required for signal scoring, risk management, and Telegram delivery.
    """
    strategy_name: StrategyName
    symbol: str
    timeframe: Timeframe
    direction: SignalDirection
    entry: float
    stop_loss: float
    take_profit: float
    confidence: float           # 0.0 – 1.0
    rationale: dict             # Human-readable reasoning dict
    parameter_set_id: str | None = None
    risk_reward: float = 0.0    # Computed: (TP-entry) / (entry-SL)
    risk_pips: float = 0.0      # Distance to SL in price units
    debug: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.entry and self.stop_loss and self.take_profit:
            sl_dist = abs(self.entry - self.stop_loss)
            tp_dist = abs(self.take_profit - self.entry)
            self.risk_pips = sl_dist
            self.risk_reward = tp_dist / sl_dist if sl_dist > 0 else 0.0


class BaseStrategy(ABC):
    """Abstract base for all trading strategies."""

    name: StrategyName

    def __init__(self, parameters: dict) -> None:
        self.parameters = parameters
        self.parameter_set_id: str | None = None

    @abstractmethod
    def generate_signals(self, ctx: StrategyContext) -> list[StrategySignal]:
        """
        Analyze context and return candidate signals.

        Must be deterministic and side-effect-free.
        Returns [] if no valid setup is detected.
        """
        ...

    def _get_param(self, key: str, default: Any = None) -> Any:
        return self.parameters.get(key, default)
