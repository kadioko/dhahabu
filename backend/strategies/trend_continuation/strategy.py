"""
Trend Continuation Strategy.

Logic:
  1. Establish directional bias from higher timeframe (H4/D1) EMA alignment
  2. On lower timeframe (H1/M15), wait for pullback to EMA or structure
  3. Confirm continuation via:
     - Price reclaiming the pullback EMA
     - Structure holding (higher low in uptrend, lower high in downtrend)
  4. Enter with ATR-based stops targeting the prior swing extreme
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backend.core.constants import SignalDirection, StrategyName, Timeframe, VolatilityRegime
from backend.strategies.base import BaseStrategy, StrategyContext, StrategySignal

DEFAULT_PARAMS = {
    "htf_ema_fast": 21,
    "htf_ema_slow": 50,
    "ltf_ema_pullback": 21,
    "pullback_atr_tolerance": 1.0,
    "atr_sl_multiplier": 1.5,
    "rr_target": 2.5,
    "htf_timeframe": "4h",
    "signal_timeframe": "1h",
    "min_trend_strength": 0.5,     # EMA gap / ATR ratio
    "min_confidence": 0.5,
}


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    h, l, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([(h - l), (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


class TrendContinuationStrategy(BaseStrategy):
    name = StrategyName.TREND_CONTINUATION

    def _get_htf_bias(
        self, htf_df: pd.DataFrame, ema_fast_p: int, ema_slow_p: int, min_strength: float
    ) -> Optional[SignalDirection]:
        """Determine directional bias from higher timeframe EMA alignment."""
        if len(htf_df) < ema_slow_p + 5:
            return None

        ema_f = _ema(htf_df["close"], ema_fast_p).iloc[-1]
        ema_s = _ema(htf_df["close"], ema_slow_p).iloc[-1]
        htf_atr = _atr(htf_df)
        if htf_atr <= 0:
            return None

        gap_ratio = abs(ema_f - ema_s) / htf_atr
        if gap_ratio < min_strength:
            return None  # No clear trend

        price = htf_df["close"].iloc[-1]
        if ema_f > ema_s and price > ema_f:
            return SignalDirection.LONG
        elif ema_f < ema_s and price < ema_f:
            return SignalDirection.SHORT
        return None

    def _detect_pullback_entry(
        self,
        ltf_df: pd.DataFrame,
        bias: SignalDirection,
        pullback_ema_p: int,
        atr: float,
        pullback_tolerance: float,
    ) -> Optional[dict]:
        """Detect a valid pullback entry on the lower timeframe."""
        if len(ltf_df) < pullback_ema_p + 5:
            return None

        ema = _ema(ltf_df["close"], pullback_ema_p)
        current_ema = float(ema.iloc[-1])
        current_price = float(ltf_df["close"].iloc[-1])
        prev_price = float(ltf_df["close"].iloc[-2])
        tolerance = atr * pullback_tolerance

        if bias == SignalDirection.LONG:
            # Price has pulled back to EMA and is now reclaiming upward
            near_ema = abs(current_price - current_ema) < tolerance
            reclaiming = current_price > current_ema and prev_price <= current_ema
            bouncing = current_price > prev_price and current_price > current_ema

            if reclaiming or (near_ema and bouncing):
                # Check for higher low structure
                lows = ltf_df["low"].tail(10).values
                higher_low = len(lows) >= 3 and lows[-1] > lows[-3]
                return {
                    "pullback_ema": current_ema,
                    "structure_confirmed": higher_low,
                    "pullback_type": "ema_reclaim",
                }

        elif bias == SignalDirection.SHORT:
            near_ema = abs(current_price - current_ema) < tolerance
            reclaiming = current_price < current_ema and prev_price >= current_ema
            bouncing = current_price < prev_price and current_price < current_ema

            if reclaiming or (near_ema and bouncing):
                highs = ltf_df["high"].tail(10).values
                lower_high = len(highs) >= 3 and highs[-1] < highs[-3]
                return {
                    "pullback_ema": current_ema,
                    "structure_confirmed": lower_high,
                    "pullback_type": "ema_reclaim",
                }

        return None

    def generate_signals(self, ctx: StrategyContext) -> list[StrategySignal]:
        htf_tf = Timeframe(self._get_param("htf_timeframe", "4h"))
        sig_tf = Timeframe(self._get_param("signal_timeframe", "1h"))

        if htf_tf not in ctx.candles or sig_tf not in ctx.candles:
            return []
        if len(ctx.candles[htf_tf]) < 60 or len(ctx.candles[sig_tf]) < 30:
            return []

        htf_df = ctx.candles[htf_tf]
        ltf_df = ctx.candles[sig_tf]

        bias = self._get_htf_bias(
            htf_df,
            self._get_param("htf_ema_fast", 21),
            self._get_param("htf_ema_slow", 50),
            self._get_param("min_trend_strength", 0.5),
        )
        if bias is None:
            return []

        atr = _atr(ltf_df)
        if atr <= 0:
            return []

        pullback = self._detect_pullback_entry(
            ltf_df,
            bias,
            self._get_param("ltf_ema_pullback", 21),
            atr,
            self._get_param("pullback_atr_tolerance", 1.0),
        )
        if pullback is None:
            return []

        current_price = float(ltf_df["close"].iloc[-1])
        atr_sl_mult = self._get_param("atr_sl_multiplier", 1.5)
        rr_target = self._get_param("rr_target", 2.5)

        if bias == SignalDirection.LONG:
            stop_loss = current_price - atr * atr_sl_mult
            take_profit = current_price + atr * atr_sl_mult * rr_target
        else:
            stop_loss = current_price + atr * atr_sl_mult
            take_profit = current_price - atr * atr_sl_mult * rr_target

        # Confidence scoring
        confidence = 0.55
        if pullback["structure_confirmed"]:
            confidence += 0.15
        if ctx.volatility_regime == VolatilityRegime.NORMAL:
            confidence += 0.1
        elif ctx.volatility_regime == VolatilityRegime.EXTREME:
            confidence -= 0.2
        confidence = max(0.2, min(0.9, confidence))

        signal = StrategySignal(
            strategy_name=self.name,
            symbol=ctx.symbol,
            timeframe=sig_tf,
            direction=bias,
            entry=round(current_price, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            confidence=round(confidence, 3),
            rationale={
                "htf_bias": bias.value,
                "pullback_type": pullback["pullback_type"],
                "pullback_ema": round(pullback["pullback_ema"], 2),
                "structure_confirmed": pullback["structure_confirmed"],
                "atr": round(atr, 4),
                "htf_timeframe": htf_tf.value,
            },
            parameter_set_id=self.parameter_set_id,
        )
        return [signal]
