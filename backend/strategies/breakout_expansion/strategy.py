"""
Breakout Expansion Strategy.

Logic:
  1. Detect range compression: ATR contracting over N bars
  2. Identify the key range boundary (consolidation high/low)
  3. Detect breakout: close beyond boundary with minimum ATR expansion
  4. Confirm with volume expansion or volatility pop (optional)
  5. Enter on the breakout candle or first pullback after breakout
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backend.core.constants import SignalDirection, StrategyName, Timeframe, VolatilityRegime
from backend.strategies.base import BaseStrategy, StrategyContext, StrategySignal

DEFAULT_PARAMS = {
    "compression_lookback": 20,         # bars to measure range compression
    "compression_atr_ratio": 0.7,       # ATR must be < X * baseline ATR
    "breakout_confirmation_atr": 0.3,   # close must be >= X * ATR beyond boundary
    "range_lookback": 15,               # bars defining the range boundary
    "atr_sl_multiplier": 1.2,           # SL inside range below breakout
    "rr_target": 2.0,
    "signal_timeframe": "1h",
    "require_volume_expansion": False,
    "volume_expansion_ratio": 1.5,
    "min_confidence": 0.5,
}


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([(h - l), (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


class BreakoutExpansionStrategy(BaseStrategy):
    name = StrategyName.BREAKOUT_EXPANSION

    def _is_compressed(
        self, atr_series: pd.Series, lookback: int, ratio: float
    ) -> bool:
        """Check if ATR is compressed relative to its baseline."""
        if len(atr_series.dropna()) < lookback + 14:
            return False
        current_atr = float(atr_series.iloc[-1])
        baseline_atr = float(atr_series.iloc[-(lookback + 14): -lookback].mean())
        return current_atr < baseline_atr * ratio

    def _get_range_boundaries(
        self, df: pd.DataFrame, lookback: int
    ) -> tuple[float, float]:
        """Return (range_high, range_low) of the consolidation zone."""
        range_df = df.iloc[-(lookback + 1): -1]
        return float(range_df["high"].max()), float(range_df["low"].min())

    def _detect_breakout(
        self,
        df: pd.DataFrame,
        range_high: float,
        range_low: float,
        atr: float,
        confirmation_atr: float,
    ) -> Optional[dict]:
        """Detect if the current candle has broken out of the range with confirmation."""
        last = df.iloc[-1]
        close = float(last["close"])
        min_extension = atr * confirmation_atr

        if close > range_high + min_extension:
            return {
                "direction": SignalDirection.LONG,
                "breakout_level": range_high,
                "extension": close - range_high,
            }
        elif close < range_low - min_extension:
            return {
                "direction": SignalDirection.SHORT,
                "breakout_level": range_low,
                "extension": range_low - close,
            }
        return None

    def generate_signals(self, ctx: StrategyContext) -> list[StrategySignal]:
        sig_tf = Timeframe(self._get_param("signal_timeframe", "1h"))
        if sig_tf not in ctx.candles or len(ctx.candles[sig_tf]) < 50:
            return []

        df = ctx.candles[sig_tf]
        compression_lookback = self._get_param("compression_lookback", 20)
        range_lookback = self._get_param("range_lookback", 15)
        compression_ratio = self._get_param("compression_atr_ratio", 0.7)
        breakout_conf_atr = self._get_param("breakout_confirmation_atr", 0.3)
        atr_sl_mult = self._get_param("atr_sl_multiplier", 1.2)
        rr_target = self._get_param("rr_target", 2.0)

        atr_series = _atr(df)
        current_atr = float(atr_series.iloc[-1])
        if current_atr <= 0:
            return []

        # Step 1: Confirm compression preceded the current bar
        compressed = self._is_compressed(atr_series, compression_lookback, compression_ratio)

        range_high, range_low = self._get_range_boundaries(df, range_lookback)
        breakout = self._detect_breakout(
            df, range_high, range_low, current_atr, breakout_conf_atr
        )

        if not breakout:
            return []

        # Volume confirmation (optional)
        volume_ok = True
        if self._get_param("require_volume_expansion", False):
            vol_ratio = self._get_param("volume_expansion_ratio", 1.5)
            avg_vol = float(df["volume"].tail(20).mean())
            last_vol = float(df["volume"].iloc[-1])
            volume_ok = last_vol >= avg_vol * vol_ratio

        if not volume_ok:
            return []

        current_price = float(df["close"].iloc[-1])
        direction = breakout["direction"]
        breakout_level = breakout["breakout_level"]

        if direction == SignalDirection.LONG:
            stop_loss = range_low - current_atr * atr_sl_mult
            take_profit = current_price + (current_price - stop_loss) * rr_target
        else:
            stop_loss = range_high + current_atr * atr_sl_mult
            take_profit = current_price - (stop_loss - current_price) * rr_target

        # Confidence: compressed setups score higher
        confidence = 0.5
        if compressed:
            confidence += 0.20
        extension_atr = breakout["extension"] / current_atr
        confidence += min(extension_atr * 0.15, 0.15)
        if ctx.volatility_regime in (VolatilityRegime.NORMAL, VolatilityRegime.HIGH):
            confidence += 0.05
        confidence = max(0.3, min(0.9, confidence))

        return [StrategySignal(
            strategy_name=self.name,
            symbol=ctx.symbol,
            timeframe=sig_tf,
            direction=direction,
            entry=round(current_price, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            confidence=round(confidence, 3),
            rationale={
                "compression_detected": compressed,
                "breakout_level": round(breakout_level, 2),
                "range_high": round(range_high, 2),
                "range_low": round(range_low, 2),
                "extension_atr_ratio": round(extension_atr, 3),
                "atr": round(current_atr, 4),
            },
            parameter_set_id=self.parameter_set_id,
        )]
