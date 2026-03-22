"""
Tests for the self-healing engine components.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from backend.services.self_healing.engine import _run_monte_carlo, _score_backtest_result, _get_param_grid
from backend.core.constants import StrategyName


class TestMonteCarlo:
    def _make_bt_result(self, pnls: list[float]):
        """Create a minimal BacktestResult with given PnL list."""
        from backend.services.backtest.engine import BacktestResult, BacktestTrade
        result = BacktestResult(
            strategy_name="test",
            parameter_set_id=None,
            window_days=30,
            start_at=__import__('datetime').datetime.utcnow(),
            end_at=__import__('datetime').datetime.utcnow(),
        )
        for i, pnl in enumerate(pnls):
            t = BacktestTrade(
                direction="long" if pnl > 0 else "short",
                entry=2000.0,
                stop_loss=1990.0 if pnl > 0 else 2010.0,
                take_profit=2030.0 if pnl > 0 else 1970.0,
                entry_bar=i,
                exit_bar=i + 1,
                exit_price=2000.0 + pnl / (100 * 0.01),
                pnl=pnl,
                closed_reason="tp_hit" if pnl > 0 else "sl_hit",
            )
            result.trades.append(t)
        result.compute_metrics()
        return result

    def test_monte_carlo_passes_strong_edge(self):
        """A system with strong positive expectancy should pass MC."""
        # Highly profitable system: 70% win rate, 2:1 R:R
        pnls = [20.0] * 70 + [-10.0] * 30
        random.shuffle(pnls)
        bt = self._make_bt_result(pnls)
        result = _run_monte_carlo(bt, "test", "test-id", 200)
        assert result["robustness_score"] > 0.5

    def test_monte_carlo_fails_random_system(self):
        """A near-random system should have poor robustness."""
        # 50% win rate, 1:1 R:R — no real edge
        pnls = [10.0] * 50 + [-10.0] * 50
        random.shuffle(pnls)
        bt = self._make_bt_result(pnls)
        result = _run_monte_carlo(bt, "test", "test-id", 200)
        # Should not have great robustness
        assert result["robustness_score"] <= 0.8  # borderline system

    def test_monte_carlo_empty_trades(self):
        """Empty trade list should return fail."""
        from backend.services.backtest.engine import BacktestResult
        bt = BacktestResult("test", None, 30, __import__('datetime').datetime.utcnow(), __import__('datetime').datetime.utcnow())
        result = _run_monte_carlo(bt, "test", "test-id", 100)
        assert result["pass_flag"] == False
        assert result["robustness_score"] == 0.0

    def test_distribution_keys_present(self):
        pnls = [15.0] * 60 + [-10.0] * 40
        bt = self._make_bt_result(pnls)
        result = _run_monte_carlo(bt, "test", "test-id", 100)
        assert "sim_mean_pnl" in result["distribution"]
        assert "z_score" in result["distribution"]
        assert "robustness_score" in result


class TestParamGrid:
    def test_generates_correct_count(self):
        grid = _get_param_grid(StrategyName.EMA_MOMENTUM, 20)
        assert len(grid) <= 20

    def test_grid_has_required_keys(self):
        grid = _get_param_grid(StrategyName.LIQUIDITY_SWEEPS, 5)
        for combo in grid:
            assert "atr_sl_multiplier" in combo
            assert "swing_lookback" in combo

    def test_all_strategies_have_grids(self):
        for sn in StrategyName:
            grid = _get_param_grid(sn, 5)
            assert len(grid) > 0


class TestBacktestScoring:
    def _make_result(self, wr, pf, sharpe, expectancy, dd, trades):
        from types import SimpleNamespace
        return SimpleNamespace(
            total_trades=trades,
            win_rate=wr,
            profit_factor=pf,
            sharpe_score=sharpe,
            expectancy=expectancy,
            max_drawdown=dd,
        )

    def test_strong_result_scores_high(self):
        r = self._make_result(0.65, 2.5, 1.5, 15.0, 50.0, 50)
        score = _score_backtest_result(r)
        assert score > 0.6

    def test_weak_result_scores_low(self):
        r = self._make_result(0.40, 0.8, -0.5, -5.0, 200.0, 20)
        score = _score_backtest_result(r)
        assert score < 0.4

    def test_insufficient_trades_scores_zero(self):
        r = self._make_result(0.80, 3.0, 2.0, 20.0, 10.0, 3)
        score = _score_backtest_result(r)
        assert score == 0.0
