"""
Volatility Regime Detection Service.

Computes ATR-based volatility regimes and detects market structure.
Used by the trading brain to adjust position sizing and strategy selection.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.core.constants import MarketRegime, Timeframe, VolatilityRegime
from backend.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VolatilityState:
    atr: float
    atr_percentile: float       # ATR percentile vs its own 20-period history
    regime: VolatilityRegime
    market_regime: MarketRegime
    ema_fast: float
    ema_slow: float
    ema_trend: str              # "up" | "down" | "flat"
    description: str


def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """True Range and ATR calculation."""
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _classify_volatility_regime(atr_pct: float) -> VolatilityRegime:
    """
    Classify volatility based on ATR percentile.
      < 25th percentile → LOW
      25–75th           → NORMAL
      75–90th           → HIGH
      > 90th            → EXTREME
    """
    if atr_pct < 25:
        return VolatilityRegime.LOW
    elif atr_pct < 75:
        return VolatilityRegime.NORMAL
    elif atr_pct < 90:
        return VolatilityRegime.HIGH
    else:
        return VolatilityRegime.EXTREME


def _classify_market_regime(
    df: pd.DataFrame,
    ema_fast: float,
    ema_slow: float,
    atr: float,
) -> MarketRegime:
    """
    Classify market regime using EMA slope and price structure.
    """
    close = df["close"].iloc[-1]
    high_20 = df["high"].rolling(20).max().iloc[-1]
    low_20 = df["low"].rolling(20).min().iloc[-1]
    range_20 = high_20 - low_20

    # EMA separation relative to ATR
    ema_gap = abs(ema_fast - ema_slow)
    ema_gap_atr_ratio = ema_gap / max(atr, 0.001)

    if ema_gap_atr_ratio > 1.5:
        # Strong trend
        if ema_fast > ema_slow:
            return MarketRegime.TRENDING_UP
        else:
            return MarketRegime.TRENDING_DOWN
    elif ema_gap_atr_ratio < 0.3:
        # Tight range
        return MarketRegime.RANGING
    else:
        # Medium conditions — check if near edge of range (breakout potential)
        range_position = (close - low_20) / max(range_20, 0.001)
        if range_position > 0.85 or range_position < 0.15:
            return MarketRegime.BREAKOUT
        return MarketRegime.CHOPPY


def compute_volatility_state(df: pd.DataFrame, symbol: str = "XAU/USD") -> VolatilityState:
    """
    Compute full volatility and market regime state from a candle DataFrame.

    Expects df with columns: open, high, low, close, volume
    Index: datetime
    """
    if len(df) < 30:
        return VolatilityState(
            atr=0.0,
            atr_percentile=50.0,
            regime=VolatilityRegime.NORMAL,
            market_regime=MarketRegime.CHOPPY,
            ema_fast=df["close"].iloc[-1] if len(df) > 0 else 0.0,
            ema_slow=df["close"].iloc[-1] if len(df) > 0 else 0.0,
            ema_trend="flat",
            description="insufficient_data",
        )

    atr_series = _calc_atr(df, 14)
    current_atr = atr_series.iloc[-1]

    # Percentile of current ATR vs past 20 periods
    atr_history = atr_series.dropna().tail(20).values
    atr_pct = float(np.percentile(atr_history, np.searchsorted(np.sort(atr_history), current_atr) / len(atr_history) * 100))

    ema_fast_series = _calc_ema(df["close"], 9)
    ema_slow_series = _calc_ema(df["close"], 21)
    ema_fast = ema_fast_series.iloc[-1]
    ema_slow = ema_slow_series.iloc[-1]

    # EMA trend direction
    ema_fast_slope = ema_fast - ema_fast_series.iloc[-3]
    if ema_fast_slope > current_atr * 0.1:
        ema_trend = "up"
    elif ema_fast_slope < -current_atr * 0.1:
        ema_trend = "down"
    else:
        ema_trend = "flat"

    vol_regime = _classify_volatility_regime(atr_pct)
    market_regime = _classify_market_regime(df, ema_fast, ema_slow, current_atr)

    description = f"{vol_regime.value}_volatility_{market_regime.value}"

    state = VolatilityState(
        atr=float(current_atr),
        atr_percentile=float(atr_pct),
        regime=vol_regime,
        market_regime=market_regime,
        ema_fast=float(ema_fast),
        ema_slow=float(ema_slow),
        ema_trend=ema_trend,
        description=description,
    )

    logger.debug(
        "volatility_regime.computed",
        symbol=symbol,
        atr=round(state.atr, 4),
        regime=state.regime.value,
        market_regime=state.market_regime.value,
    )
    return state
