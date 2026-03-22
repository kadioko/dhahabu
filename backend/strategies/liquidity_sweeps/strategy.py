"""
Liquidity Sweeps Strategy.

Logic:
  1. Identify recent swing highs and lows using a configurable lookback
  2. Detect when price sweeps (wicks through) a swing level
  3. Confirm rejection: candle body closes back inside the prior range
  4. Enter in the direction of the rejection with ATR-based SL/TP

This captures Stop Hunt / Liquidity Grab setups — common in XAUUSD.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backend.core.constants import SignalDirection, StrategyName, Timeframe, VolatilityRegime
from backend.strategies.base import BaseStrategy, StrategyContext, StrategySignal

DEFAULT_PARAMS = {
    "swing_lookback": 10,           # bars to look back for swing hi/lo
    "confirmation_bars": 2,         # bars after sweep to confirm rejection
    "atr_sl_multiplier": 1.5,       # SL = ATR * multiplier beyond sweep level
    "atr_tp_multiplier": 3.0,       # TP = ATR * multiplier
    "min_sweep_pips": 0.5,          # minimum sweep distance (price units)
    "require_close_inside": True,   # body must close back inside range
    "primary_timeframe": "1h",      # timeframe for signal generation
    "confirmation_timeframe": "4h", # higher TF for context
    "min_confidence": 0.5,
}


class LiquiditySweepsStrategy(BaseStrategy):
    name = StrategyName.LIQUIDITY_SWEEPS

    def _calc_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        high, low, close_prev = df["high"], df["low"], df["close"].shift(1)
        tr = pd.concat([
            high - low,
            (high - close_prev).abs(),
            (low - close_prev).abs(),
        ], axis=1).max(axis=1)
        return float(tr.rolling(period).mean().iloc[-1])

    def _find_swing_levels(
        self, df: pd.DataFrame, lookback: int
    ) -> tuple[list[float], list[float]]:
        """Return lists of swing highs and swing lows in the recent lookback window."""
        recent = df.tail(lookback * 3)
        highs = []
        lows = []
        for i in range(lookback, len(recent) - lookback):
            window_h = recent["high"].iloc[i - lookback: i + lookback + 1]
            window_l = recent["low"].iloc[i - lookback: i + lookback + 1]
            if recent["high"].iloc[i] == window_h.max():
                highs.append(float(recent["high"].iloc[i]))
            if recent["low"].iloc[i] == window_l.min():
                lows.append(float(recent["low"].iloc[i]))
        return highs, lows

    def _detect_sweep_rejection(
        self,
        df: pd.DataFrame,
        swing_highs: list[float],
        swing_lows: list[float],
        atr: float,
        min_sweep: float,
        require_close_inside: bool,
    ) -> Optional[dict]:
        """
        Check the last 2 candles for a liquidity sweep + rejection.

        Returns dict with sweep_type, sweep_level, direction if found.
        """
        if len(df) < 3:
            return None

        last = df.iloc[-1]
        prev = df.iloc[-2]
        body_high = max(last["open"], last["close"])
        body_low = min(last["open"], last["close"])

        # Check for upward sweep (wick above swing high, close back below)
        for sh in sorted(swing_highs, reverse=True)[:5]:
            wick_above = last["high"] - sh
            if wick_above >= min_sweep:
                if require_close_inside and last["close"] < sh:
                    return {
                        "sweep_type": "high_sweep",
                        "sweep_level": sh,
                        "direction": SignalDirection.SHORT,
                        "wick_distance": wick_above,
                    }
                elif not require_close_inside and last["close"] < last["open"]:
                    return {
                        "sweep_type": "high_sweep",
                        "sweep_level": sh,
                        "direction": SignalDirection.SHORT,
                        "wick_distance": wick_above,
                    }

        # Check for downward sweep (wick below swing low, close back above)
        for sl in sorted(swing_lows)[:5]:
            wick_below = sl - last["low"]
            if wick_below >= min_sweep:
                if require_close_inside and last["close"] > sl:
                    return {
                        "sweep_type": "low_sweep",
                        "sweep_level": sl,
                        "direction": SignalDirection.LONG,
                        "wick_distance": wick_below,
                    }
                elif not require_close_inside and last["close"] > last["open"]:
                    return {
                        "sweep_type": "low_sweep",
                        "sweep_level": sl,
                        "direction": SignalDirection.LONG,
                        "wick_distance": wick_below,
                    }
        return None

    def generate_signals(self, ctx: StrategyContext) -> list[StrategySignal]:
        primary_tf_str = self._get_param("primary_timeframe", "1h")
        primary_tf = Timeframe(primary_tf_str)

        if primary_tf not in ctx.candles or len(ctx.candles[primary_tf]) < 30:
            return []

        df = ctx.candles[primary_tf]
        lookback = self._get_param("swing_lookback", 10)
        atr_sl_mult = self._get_param("atr_sl_multiplier", 1.5)
        atr_tp_mult = self._get_param("atr_tp_multiplier", 3.0)
        min_sweep = self._get_param("min_sweep_pips", 0.5)
        require_close = self._get_param("require_close_inside", True)

        atr = self._calc_atr(df)
        if atr <= 0:
            return []

        swing_highs, swing_lows = self._find_swing_levels(df, lookback)
        sweep = self._detect_sweep_rejection(
            df, swing_highs, swing_lows, atr, min_sweep, require_close
        )
        if not sweep:
            return []

        current_price = float(df["close"].iloc[-1])
        direction = sweep["direction"]
        sweep_level = sweep["sweep_level"]

        if direction == SignalDirection.LONG:
            entry = current_price
            stop_loss = sweep_level - atr * atr_sl_mult
            take_profit = current_price + atr * atr_tp_mult
        else:
            entry = current_price
            stop_loss = sweep_level + atr * atr_sl_mult
            take_profit = current_price - atr * atr_tp_mult

        # Confidence: stronger wick = higher confidence
        wick_atr_ratio = sweep["wick_distance"] / atr
        confidence = min(0.4 + wick_atr_ratio * 0.2, 0.9)

        # Reduce confidence in extreme volatility
        if ctx.volatility_regime == VolatilityRegime.EXTREME:
            confidence *= 0.7

        signal = StrategySignal(
            strategy_name=self.name,
            symbol=ctx.symbol,
            timeframe=primary_tf,
            direction=direction,
            entry=round(entry, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            confidence=round(confidence, 3),
            rationale={
                "sweep_type": sweep["sweep_type"],
                "sweep_level": sweep_level,
                "wick_distance": round(sweep["wick_distance"], 4),
                "atr": round(atr, 4),
                "regime": ctx.volatility_regime.value,
            },
            parameter_set_id=self.parameter_set_id,
            debug={
                "swing_highs": swing_highs[:5],
                "swing_lows": swing_lows[:5],
                "lookback": lookback,
            },
        )
        return [signal]
