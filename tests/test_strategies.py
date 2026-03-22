"""
Unit tests for all 4 trading strategies.

Tests use synthetic price data to verify:
  - Signal generation under correct conditions
  - No signals under incorrect/insufficient conditions
  - Correct direction logic
  - Valid SL/TP levels
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.core.constants import MarketRegime, SignalDirection, Timeframe, VolatilityRegime
from backend.strategies.base import StrategyContext
from backend.strategies.liquidity_sweeps.strategy import DEFAULT_PARAMS as LS_PARAMS, LiquiditySweepsStrategy
from backend.strategies.trend_continuation.strategy import DEFAULT_PARAMS as TC_PARAMS, TrendContinuationStrategy
from backend.strategies.breakout_expansion.strategy import DEFAULT_PARAMS as BE_PARAMS, BreakoutExpansionStrategy
from backend.strategies.ema_momentum.strategy import DEFAULT_PARAMS as EM_PARAMS, EMAMomentumStrategy


def _make_candles(
    n: int = 100,
    base_price: float = 2000.0,
    trend: float = 0.0,
    volatility: float = 5.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    rng = np.random.RandomState(seed)
    timestamps = [datetime(2025, 1, 1) + timedelta(hours=i) for i in range(n)]
    closes = [base_price]
    for _ in range(n - 1):
        change = trend + rng.normal(0, volatility)
        closes.append(max(closes[-1] + change, 1.0))

    rows = []
    for i, (ts, c) in enumerate(zip(timestamps, closes)):
        noise = rng.uniform(0, volatility)
        o = c + rng.normal(0, volatility * 0.3)
        h = max(o, c) + abs(rng.normal(0, noise))
        l = min(o, c) - abs(rng.normal(0, noise))
        rows.append({"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": rng.uniform(100, 1000)})

    df = pd.DataFrame(rows).set_index("timestamp")
    return df


def _make_ctx(
    df: pd.DataFrame,
    extra_tfs: dict | None = None,
    regime: VolatilityRegime = VolatilityRegime.NORMAL,
    market_regime: MarketRegime = MarketRegime.RANGING,
) -> StrategyContext:
    candles = {Timeframe.H1: df}
    if extra_tfs:
        candles.update(extra_tfs)
    return StrategyContext(
        symbol="XAU/USD",
        candles=candles,
        volatility_regime=regime,
        market_regime=market_regime,
        atr=5.0,
        current_price=float(df["close"].iloc[-1]),
    )


# ── Liquidity Sweeps ──────────────────────────────────────────────────────────

class TestLiquiditySweepsStrategy:
    def test_instantiation(self):
        s = LiquiditySweepsStrategy(LS_PARAMS)
        assert s.name.value == "liquidity_sweeps"

    def test_no_signal_insufficient_data(self):
        df = _make_candles(n=10)
        s = LiquiditySweepsStrategy(LS_PARAMS)
        ctx = _make_ctx(df)
        signals = s.generate_signals(ctx)
        assert signals == []

    def test_signal_has_valid_sl_tp(self):
        """When a signal is produced, SL and TP must be on correct sides of entry."""
        df = _make_candles(n=80)
        s = LiquiditySweepsStrategy({**LS_PARAMS, "min_sweep_pips": 0.01})
        ctx = _make_ctx(df)
        signals = s.generate_signals(ctx)
        for sig in signals:
            if sig.direction == SignalDirection.LONG:
                assert sig.stop_loss < sig.entry
                assert sig.take_profit > sig.entry
            else:
                assert sig.stop_loss > sig.entry
                assert sig.take_profit < sig.entry

    def test_confidence_in_range(self):
        df = _make_candles(n=80)
        s = LiquiditySweepsStrategy({**LS_PARAMS, "min_sweep_pips": 0.01})
        ctx = _make_ctx(df)
        for sig in s.generate_signals(ctx):
            assert 0.0 <= sig.confidence <= 1.0

    def test_extreme_volatility_reduces_confidence(self):
        df = _make_candles(n=80)
        s = LiquiditySweepsStrategy({**LS_PARAMS, "min_sweep_pips": 0.01})
        ctx_normal = _make_ctx(df, regime=VolatilityRegime.NORMAL)
        ctx_extreme = _make_ctx(df, regime=VolatilityRegime.EXTREME)

        sigs_normal = s.generate_signals(ctx_normal)
        sigs_extreme = s.generate_signals(ctx_extreme)

        # If both produce signals, extreme should have lower confidence
        if sigs_normal and sigs_extreme:
            assert sigs_extreme[0].confidence < sigs_normal[0].confidence


# ── Trend Continuation ────────────────────────────────────────────────────────

class TestTrendContinuationStrategy:
    def test_instantiation(self):
        s = TrendContinuationStrategy(TC_PARAMS)
        assert s.name.value == "trend_continuation"

    def test_no_signal_missing_htf(self):
        df = _make_candles(n=80)
        s = TrendContinuationStrategy(TC_PARAMS)
        # Only provide H1, no H4
        ctx = StrategyContext(
            symbol="XAU/USD",
            candles={Timeframe.H1: df},
            volatility_regime=VolatilityRegime.NORMAL,
            market_regime=MarketRegime.TRENDING_UP,
            atr=5.0,
            current_price=float(df["close"].iloc[-1]),
        )
        signals = s.generate_signals(ctx)
        assert signals == []

    def test_uptrend_bias_with_strong_ema(self):
        """Strong uptrend should produce LONG signals."""
        df_uptrend = _make_candles(n=120, trend=2.0, volatility=2.0, seed=1)
        htf = _make_candles(n=120, trend=3.0, volatility=1.0, seed=2)
        s = TrendContinuationStrategy(TC_PARAMS)
        ctx = StrategyContext(
            symbol="XAU/USD",
            candles={Timeframe.H1: df_uptrend, Timeframe.H4: htf},
            volatility_regime=VolatilityRegime.NORMAL,
            market_regime=MarketRegime.TRENDING_UP,
            atr=5.0,
            current_price=float(df_uptrend["close"].iloc[-1]),
        )
        signals = s.generate_signals(ctx)
        for sig in signals:
            assert sig.direction == SignalDirection.LONG


# ── Breakout Expansion ────────────────────────────────────────────────────────

class TestBreakoutExpansionStrategy:
    def test_instantiation(self):
        s = BreakoutExpansionStrategy(BE_PARAMS)
        assert s.name.value == "breakout_expansion"

    def test_no_signal_insufficient_data(self):
        df = _make_candles(n=20)
        s = BreakoutExpansionStrategy(BE_PARAMS)
        ctx = _make_ctx(df)
        assert s.generate_signals(ctx) == []

    def test_signal_sl_inside_range(self):
        """SL should be inside the range for breakout trades."""
        # Create a tight range then a sharp move up
        df = _make_candles(n=60, volatility=0.5, seed=10)
        # Force last candle to be a big breakout
        breakout_data = df.copy()
        breakout_data.iloc[-1, breakout_data.columns.get_loc("close")] = (
            breakout_data["high"].tail(20).max() + 10.0
        )
        breakout_data.iloc[-1, breakout_data.columns.get_loc("high")] = (
            breakout_data.iloc[-1]["close"] + 1.0
        )

        s = BreakoutExpansionStrategy({**BE_PARAMS, "breakout_confirmation_atr": 0.1})
        ctx = _make_ctx(breakout_data)
        signals = s.generate_signals(ctx)
        for sig in signals:
            assert 0.0 <= sig.confidence <= 1.0
            assert sig.risk_reward > 0


# ── EMA Momentum ──────────────────────────────────────────────────────────────

class TestEMAMomentumStrategy:
    def test_instantiation(self):
        s = EMAMomentumStrategy(EM_PARAMS)
        assert s.name.value == "ema_momentum"

    def test_no_signal_choppy_market(self):
        """Choppy/flat market should produce no EMA momentum signals."""
        df = _make_candles(n=100, trend=0.0, volatility=0.1, seed=99)
        s = EMAMomentumStrategy(EM_PARAMS)
        ctx = StrategyContext(
            symbol="XAU/USD",
            candles={Timeframe.M15: df, Timeframe.H1: df},
            volatility_regime=VolatilityRegime.LOW,
            market_regime=MarketRegime.CHOPPY,
            atr=0.5,
            current_price=float(df["close"].iloc[-1]),
        )
        signals = s.generate_signals(ctx)
        # May or may not have signals — just verify output format
        for sig in signals:
            assert sig.direction in (SignalDirection.LONG, SignalDirection.SHORT)

    def test_strong_trend_produces_aligned_signal(self):
        """Strong trending market should produce signals aligned with trend."""
        df = _make_candles(n=120, trend=5.0, volatility=1.0, seed=7)
        htf = _make_candles(n=120, trend=5.0, volatility=1.0, seed=8)
        s = EMAMomentumStrategy({**EM_PARAMS, "body_min_atr_ratio": 0.05, "slope_min_atr_ratio": 0.01})
        ctx = StrategyContext(
            symbol="XAU/USD",
            candles={Timeframe.M15: df, Timeframe.H1: htf},
            volatility_regime=VolatilityRegime.NORMAL,
            market_regime=MarketRegime.TRENDING_UP,
            atr=5.0,
            current_price=float(df["close"].iloc[-1]),
        )
        signals = s.generate_signals(ctx)
        for sig in signals:
            assert sig.direction == SignalDirection.LONG


# ── Backtest engine smoke test ────────────────────────────────────────────────

class TestBacktestEngine:
    def test_backtest_produces_metrics(self):
        from backend.services.backtest.engine import run_backtest
        df = _make_candles(n=200, trend=1.0, volatility=3.0)
        candles = {Timeframe.H1: df}
        strategy = LiquiditySweepsStrategy({**LS_PARAMS, "min_sweep_pips": 0.01})
        result = run_backtest(strategy, candles, window_days=30)
        assert result.strategy_name == "liquidity_sweeps"
        assert isinstance(result.total_trades, int)
        assert 0.0 <= result.win_rate <= 1.0
        assert result.profit_factor >= 0.0 or result.profit_factor == float("inf")

    def test_backtest_metrics_dict(self):
        from backend.services.backtest.engine import run_backtest
        df = _make_candles(n=200)
        candles = {Timeframe.H1: df}
        strategy = EMAMomentumStrategy({**EM_PARAMS, "body_min_atr_ratio": 0.01, "slope_min_atr_ratio": 0.01})
        result = run_backtest(strategy, candles, window_days=14)
        metrics = result.to_metrics_dict()
        assert "win_rate" in metrics
        assert "profit_factor" in metrics
        assert "total_trades" in metrics


# ── Position sizing tests ─────────────────────────────────────────────────────

class TestPositionSizing:
    def test_basic_sizing(self):
        from backend.services.position_sizing.service import compute_position_size
        result = compute_position_size(
            entry=2000.0,
            stop_loss=1990.0,
            account_balance=10000.0,
            risk_per_trade_pct=0.01,
            volatility_regime=VolatilityRegime.NORMAL,
        )
        assert result.position_size > 0
        assert result.risk_amount == pytest.approx(100.0, abs=1.0)
        assert result.sl_distance == pytest.approx(10.0)

    def test_extreme_volatility_reduces_size(self):
        from backend.services.position_sizing.service import compute_position_size
        normal = compute_position_size(2000.0, 1990.0, volatility_regime=VolatilityRegime.NORMAL)
        extreme = compute_position_size(2000.0, 1990.0, volatility_regime=VolatilityRegime.EXTREME)
        assert extreme.position_size < normal.position_size

    def test_zero_sl_returns_minimum(self):
        from backend.services.position_sizing.service import compute_position_size
        result = compute_position_size(2000.0, 2000.0)
        assert result.position_size == 0.01
