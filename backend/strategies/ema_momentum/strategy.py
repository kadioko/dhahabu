"""
EMA Momentum Strategy.

Logic:
  1. Multi-EMA alignment: short EMA > medium EMA > long EMA (bullish)
     or short EMA < medium EMA < long EMA (bearish)
  2. EMA slope confirmation: fast EMA must have a meaningful slope
  3. Candle body strength: last candle body >= X% of ATR (avoid weak wicks)
  4. Not overextended: price within N * ATR of the fast EMA
  5. Enter on the current close with ATR-based SL
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backend.core.constants import SignalDirection, StrategyName, Timeframe, VolatilityRegime
from backend.strategies.base import BaseStrategy, StrategyContext, StrategySignal

DEFAULT_PARAMS = {
    "ema_fast": 9,
    "ema_medium": 21,
    "ema_slow": 50,
    "slope_min_atr_ratio": 0.15,        # fast EMA slope vs ATR
    "body_min_atr_ratio": 0.25,         # candle body size vs ATR
    "max_extension_atr": 2.5,           # max price distance from fast EMA
    "atr_sl_multiplier": 1.5,
    "rr_target": 2.0,
    "signal_timeframe": "15min",
    "confirmation_timeframe": "1h",     # must agree
    "min_confidence": 0.45,
}


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    h, l, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([(h - l), (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


class EMAMomentumStrategy(BaseStrategy):
    name = StrategyName.EMA_MOMENTUM

    def _ema_alignment(
        self,
        df: pd.DataFrame,
        fast_p: int,
        med_p: int,
        slow_p: int,
    ) -> Optional[SignalDirection]:
        """Return direction if all 3 EMAs are aligned, else None."""
        if len(df) < slow_p + 5:
            return None
        fast = _ema(df["close"], fast_p).iloc[-1]
        med = _ema(df["close"], med_p).iloc[-1]
        slow = _ema(df["close"], slow_p).iloc[-1]
        if fast > med > slow:
            return SignalDirection.LONG
        elif fast < med < slow:
            return SignalDirection.SHORT
        return None

    def _ema_slope_ok(
        self,
        df: pd.DataFrame,
        fast_p: int,
        atr: float,
        min_slope_ratio: float,
    ) -> bool:
        fast_series = _ema(df["close"], fast_p)
        slope = float(fast_series.iloc[-1] - fast_series.iloc[-3])
        return abs(slope) >= atr * min_slope_ratio

    def _body_strength_ok(
        self, df: pd.DataFrame, atr: float, min_body_ratio: float
    ) -> bool:
        last = df.iloc[-1]
        body = abs(float(last["close"]) - float(last["open"]))
        return body >= atr * min_body_ratio

    def _not_overextended(
        self,
        df: pd.DataFrame,
        fast_p: int,
        atr: float,
        max_ext_atr: float,
    ) -> bool:
        fast_ema = float(_ema(df["close"], fast_p).iloc[-1])
        price = float(df["close"].iloc[-1])
        return abs(price - fast_ema) <= atr * max_ext_atr

    def generate_signals(self, ctx: StrategyContext) -> list[StrategySignal]:
        sig_tf = Timeframe(self._get_param("signal_timeframe", "15min"))
        conf_tf_str = self._get_param("confirmation_timeframe", "1h")

        if sig_tf not in ctx.candles or len(ctx.candles[sig_tf]) < 60:
            return []

        df = ctx.candles[sig_tf]
        fast_p = self._get_param("ema_fast", 9)
        med_p = self._get_param("ema_medium", 21)
        slow_p = self._get_param("ema_slow", 50)
        slope_min = self._get_param("slope_min_atr_ratio", 0.15)
        body_min = self._get_param("body_min_atr_ratio", 0.25)
        max_ext = self._get_param("max_extension_atr", 2.5)
        atr_sl_mult = self._get_param("atr_sl_multiplier", 1.5)
        rr = self._get_param("rr_target", 2.0)

        atr = _atr(df)
        if atr <= 0:
            return []

        direction = self._ema_alignment(df, fast_p, med_p, slow_p)
        if direction is None:
            return []

        if not self._ema_slope_ok(df, fast_p, atr, slope_min):
            return []
        if not self._body_strength_ok(df, atr, body_min):
            return []
        if not self._not_overextended(df, fast_p, atr, max_ext):
            return []

        # Optional confirmation timeframe
        conf_tf = Timeframe(conf_tf_str) if conf_tf_str else None
        if conf_tf and conf_tf in ctx.candles and len(ctx.candles[conf_tf]) >= slow_p + 5:
            conf_dir = self._ema_alignment(ctx.candles[conf_tf], fast_p, med_p, slow_p)
            if conf_dir is not None and conf_dir != direction:
                return []  # HTF disagrees

        current_price = float(df["close"].iloc[-1])
        if direction == SignalDirection.LONG:
            stop_loss = current_price - atr * atr_sl_mult
            take_profit = current_price + atr * atr_sl_mult * rr
        else:
            stop_loss = current_price + atr * atr_sl_mult
            take_profit = current_price - atr * atr_sl_mult * rr

        # Confidence: more aligned = higher confidence
        fast_ema_v = float(_ema(df["close"], fast_p).iloc[-1])
        med_ema_v = float(_ema(df["close"], med_p).iloc[-1])
        slow_ema_v = float(_ema(df["close"], slow_p).iloc[-1])
        ema_spread = abs(fast_ema_v - slow_ema_v) / atr
        confidence = 0.45 + min(ema_spread * 0.05, 0.3)
        if conf_tf and conf_tf in ctx.candles:
            conf_dir = self._ema_alignment(ctx.candles[conf_tf], fast_p, med_p, slow_p)
            if conf_dir == direction:
                confidence += 0.10
        if ctx.volatility_regime == VolatilityRegime.EXTREME:
            confidence -= 0.15
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
                "ema_fast": round(fast_ema_v, 2),
                "ema_medium": round(med_ema_v, 2),
                "ema_slow": round(slow_ema_v, 2),
                "ema_spread_atr": round(ema_spread, 3),
                "atr": round(atr, 4),
                "regime": ctx.volatility_regime.value,
            },
            parameter_set_id=self.parameter_set_id,
        )]
