"""
Self-Healing Engine.

Implements the full validation and optimization cycle from the architecture diagram:

  BACKTEST LOOP (every 4h):
    Re-Backtest → Walk-Forward → Overfit? → Continue / Flag Overfitted

  OPTIMIZE LOOP (every 4-6h):
    Parameter Search → Monte Carlo → Random wins? → Promote Live / Throw Away

This engine is the heart of the platform's robustness guarantees.
Every decision it makes is persisted to the database and visible on the dashboard.
"""

from __future__ import annotations

import asyncio
import itertools
import random
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from backend.core.config import settings
from backend.core.constants import StrategyName, Timeframe
from backend.core.logging import get_logger
from backend.db.base import get_db_session
from backend.db.models import (
    BacktestRun,
    MonteCarloRun,
    OptimizationRun,
    StrategyParameters,
    WalkForwardRun,
)

logger = get_logger(__name__)

LIVE_TIMEFRAMES = [Timeframe.M15, Timeframe.H1, Timeframe.H4, Timeframe.D1]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_candles_for_window(
    symbol: str, window_days: int
) -> dict[Timeframe, "pd.DataFrame"]:
    """Load candle data from DB for the last N days."""
    import pandas as pd
    from backend.services.market_data.service import get_latest_candles_df

    # For backtest, fetch generous window
    limits = {
        Timeframe.M15: window_days * 96 + 200,   # 96 M15 bars/day
        Timeframe.H1: window_days * 24 + 50,
        Timeframe.H4: window_days * 6 + 20,
        Timeframe.D1: window_days + 10,
    }
    candles = {}
    for tf in LIVE_TIMEFRAMES:
        df = await get_latest_candles_df(symbol, tf, limit=limits[tf])
        if not df.empty:
            candles[tf] = df
    return candles


def _get_strategy_instance(name: StrategyName, params: dict):
    """Instantiate a strategy from the registry."""
    from backend.services.risk_guardian.brain import _get_strategy_instance as _get
    return _get(name, params)


def _get_param_grid(strategy_name: StrategyName, n_combos: int) -> list[dict]:
    """
    Generate a random sample of parameter combinations for a strategy.

    Returns up to n_combos combinations by sampling a Cartesian product.
    """
    grids = {
        StrategyName.LIQUIDITY_SWEEPS: {
            "swing_lookback": [5, 8, 10, 12, 15],
            "atr_sl_multiplier": [1.0, 1.5, 2.0],
            "atr_tp_multiplier": [2.0, 2.5, 3.0, 3.5],
            "min_sweep_pips": [0.3, 0.5, 0.8],
            "require_close_inside": [True, False],
            "primary_timeframe": ["1h"],
        },
        StrategyName.TREND_CONTINUATION: {
            "htf_ema_fast": [21, 34],
            "htf_ema_slow": [50, 89, 100],
            "ltf_ema_pullback": [13, 21, 34],
            "pullback_atr_tolerance": [0.5, 1.0, 1.5],
            "atr_sl_multiplier": [1.0, 1.5, 2.0],
            "rr_target": [2.0, 2.5, 3.0],
            "htf_timeframe": ["4h"],
            "signal_timeframe": ["1h"],
        },
        StrategyName.BREAKOUT_EXPANSION: {
            "compression_lookback": [15, 20, 25],
            "compression_atr_ratio": [0.6, 0.7, 0.8],
            "breakout_confirmation_atr": [0.2, 0.3, 0.5],
            "range_lookback": [10, 15, 20],
            "atr_sl_multiplier": [1.0, 1.2, 1.5],
            "rr_target": [1.5, 2.0, 2.5],
        },
        StrategyName.EMA_MOMENTUM: {
            "ema_fast": [9, 13],
            "ema_medium": [21, 34],
            "ema_slow": [50, 89],
            "slope_min_atr_ratio": [0.10, 0.15, 0.20],
            "body_min_atr_ratio": [0.20, 0.25, 0.30],
            "atr_sl_multiplier": [1.0, 1.5, 2.0],
            "rr_target": [1.5, 2.0, 2.5],
        },
    }
    grid = grids.get(strategy_name, {})
    if not grid:
        return [{}]

    keys = list(grid.keys())
    values = [grid[k] for k in keys]
    all_combos = list(itertools.product(*values))
    random.shuffle(all_combos)
    sampled = all_combos[:n_combos]
    return [dict(zip(keys, combo)) for combo in sampled]


def _score_backtest_result(result) -> float:
    """
    Composite score for a backtest result.
    Weights: profit_factor (0.35), win_rate (0.25), expectancy (0.20), sharpe (0.20)
    """
    if result.total_trades < 5:
        return 0.0
    pf = min(result.profit_factor, 5.0)
    wr = result.win_rate
    exp = max(min(result.expectancy, 100), -100) / 100
    sharpe = max(min(result.sharpe_score, 5.0), -5.0) / 5.0
    dd_penalty = max(0.0, 1.0 - result.max_drawdown / 500.0)

    score = (pf / 5.0) * 0.35 + wr * 0.25 + (exp + 1) / 2 * 0.20 + (sharpe + 1) / 2 * 0.20
    return round(score * dd_penalty, 4)


# ── A. Backtest + Walk-Forward Loop ──────────────────────────────────────────

async def run_backtest_validation_cycle() -> None:
    """
    Every 4 hours:
      1. For each strategy, load live parameter set
      2. Run backtests across rolling windows (7d, 14d, 30d, 60d)
      3. Run walk-forward validation (80/20 split)
      4. Detect overfit
      5. Flag or Continue
    """
    logger.info("self_healing.backtest_cycle.start")
    symbol = settings.market_data_symbol

    for strategy_name in StrategyName:
        try:
            await _validate_strategy(strategy_name, symbol)
        except Exception as exc:
            logger.error(
                "self_healing.validate.failed",
                strategy=strategy_name.value,
                error=str(exc),
            )

    logger.info("self_healing.backtest_cycle.done")


async def _validate_strategy(strategy_name: StrategyName, symbol: str) -> None:
    """Run the full backtest + walk-forward pipeline for one strategy."""
    async with get_db_session() as db:
        from sqlalchemy import select

        # Get live parameter set
        param_res = await db.execute(
            select(StrategyParameters).where(
                StrategyParameters.strategy_name == strategy_name.value,
                StrategyParameters.is_live == True,
            )
        )
        param_set = param_res.scalar_one_or_none()

    if not param_set:
        logger.info("self_healing.no_live_params", strategy=strategy_name.value)
        return

    strategy = _get_strategy_instance(strategy_name, param_set.parameter_json)

    for window_days in settings.rolling_windows_days:
        candles = await _load_candles_for_window(symbol, window_days)
        if not candles:
            continue

        from backend.services.backtest.engine import run_backtest
        bt_result = run_backtest(strategy, candles, window_days, param_set.id)

        async with get_db_session() as db:
            bt_record = BacktestRun(
                strategy_name=strategy_name.value,
                parameter_set_id=param_set.id,
                window_days=window_days,
                start_at=bt_result.start_at,
                end_at=bt_result.end_at,
                total_trades=bt_result.total_trades,
                win_rate=bt_result.win_rate,
                profit_factor=bt_result.profit_factor if bt_result.profit_factor != float("inf") else 999.0,
                sharpe_score=bt_result.sharpe_score,
                expectancy=bt_result.expectancy,
                max_drawdown=bt_result.max_drawdown,
                metrics_json=bt_result.to_metrics_dict(),
                created_at=datetime.utcnow(),
            )
            db.add(bt_record)

        # Run walk-forward on the 30d window for overfit detection
        if window_days == 30:
            await _run_walk_forward(strategy_name, strategy, param_set, candles, symbol)


async def _run_walk_forward(
    strategy_name: StrategyName,
    strategy,
    param_set: StrategyParameters,
    candles: dict,
    symbol: str,
) -> None:
    """
    Walk-forward validation: 80% train, 20% test.

    Detects OOS collapse and flags overfit if thresholds are breached.
    """
    train_ratio = settings.walk_forward_train_ratio
    test_ratio = settings.walk_forward_test_ratio

    from backend.services.backtest.engine import run_backtest

    # Split primary TF candles
    primary_tf = Timeframe.H1
    if primary_tf not in candles:
        return

    primary_df = candles[primary_tf]
    split_idx = int(len(primary_df) * train_ratio)

    train_candles = {tf: df.iloc[:split_idx] for tf, df in candles.items()}
    test_candles = {tf: df.iloc[split_idx:] for tf, df in candles.items()}

    if len(list(train_candles.values())[0]) < 30:
        return
    if len(list(test_candles.values())[0]) < 10:
        return

    train_result = run_backtest(strategy, train_candles, 24, param_set.id)
    test_result = run_backtest(strategy, test_candles, 6, param_set.id)

    # Overfit detection
    overfit = False
    collapse_details = {}

    pf_ratio = (
        test_result.profit_factor / train_result.profit_factor
        if train_result.profit_factor > 0 and train_result.profit_factor != float("inf")
        else 1.0
    )
    exp_ratio = (
        test_result.expectancy / train_result.expectancy
        if abs(train_result.expectancy) > 0.001
        else 1.0
    )
    wr_ratio = (
        test_result.win_rate / train_result.win_rate
        if train_result.win_rate > 0
        else 1.0
    )
    dd_ratio = (
        test_result.max_drawdown / train_result.max_drawdown
        if train_result.max_drawdown > 0
        else 1.0
    )

    if pf_ratio < settings.oos_profit_factor_threshold:
        overfit = True
        collapse_details["pf_ratio"] = pf_ratio
    if exp_ratio < settings.oos_expectancy_threshold:
        overfit = True
        collapse_details["expectancy_ratio"] = exp_ratio
    if wr_ratio < settings.oos_win_rate_collapse_threshold:
        overfit = True
        collapse_details["win_rate_ratio"] = wr_ratio
    if dd_ratio > settings.oos_drawdown_expansion_threshold:
        overfit = True
        collapse_details["drawdown_ratio"] = dd_ratio

    oos_degradation_score = 1.0 - min(pf_ratio, 1.0) * 0.5 - min(wr_ratio, 1.0) * 0.5

    async with get_db_session() as db:
        wf_record = WalkForwardRun(
            strategy_name=strategy_name.value,
            parameter_set_id=param_set.id,
            train_ratio=train_ratio,
            test_ratio=test_ratio,
            train_metrics_json=train_result.to_metrics_dict(),
            test_metrics_json=test_result.to_metrics_dict(),
            oos_degradation_score=oos_degradation_score,
            overfit_flag=overfit,
            oos_collapse_details=collapse_details if collapse_details else None,
            created_at=datetime.utcnow(),
        )
        db.add(wf_record)

        # Update parameter set if overfit detected
        if overfit:
            from sqlalchemy import select, update
            await db.execute(
                update(StrategyParameters)
                .where(StrategyParameters.id == param_set.id)
                .values(overfit_flag=True, suppressed_flag=True)
            )
            logger.warning(
                "self_healing.overfit_detected",
                strategy=strategy_name.value,
                collapse_details=collapse_details,
            )
            # Telegram notification
            try:
                from backend.telegram.service import send_system_alert
                asyncio.create_task(
                    send_system_alert(
                        f"⚠️ OVERFIT FLAGGED: {strategy_name.value}\n"
                        f"OOS collapse: {collapse_details}"
                    )
                )
            except Exception:
                pass
        else:
            # Clear overfit flag if previously set
            await db.execute(
                update(StrategyParameters)
                .where(StrategyParameters.id == param_set.id)
                .values(overfit_flag=False, suppressed_flag=False)
            )
            logger.info(
                "self_healing.walk_forward.pass",
                strategy=strategy_name.value,
                oos_degradation=round(oos_degradation_score, 3),
            )


# ── B. Optimization Loop ──────────────────────────────────────────────────────

async def run_optimization_cycle() -> None:
    """
    Every 4-6 hours:
      1. Parameter search for each strategy
      2. Monte Carlo on best candidate
      3. Random wins? → Promote Live / Throw Away
    """
    logger.info("self_healing.optimization_cycle.start")
    symbol = settings.market_data_symbol

    for strategy_name in StrategyName:
        try:
            await _optimize_strategy(strategy_name, symbol)
        except Exception as exc:
            logger.error(
                "self_healing.optimize.failed",
                strategy=strategy_name.value,
                error=str(exc),
            )

    logger.info("self_healing.optimization_cycle.done")


async def _optimize_strategy(strategy_name: StrategyName, symbol: str) -> None:
    """Full optimization cycle for one strategy."""
    # Use 30-day window for optimization
    candles = await _load_candles_for_window(symbol, 30)
    if not candles:
        logger.warning("self_healing.optimize.no_candles", strategy=strategy_name.value)
        return

    n_combos = settings.param_search_combinations
    param_grid = _get_param_grid(strategy_name, n_combos)

    from backend.services.backtest.engine import run_backtest

    # Create optimization run record
    async with get_db_session() as db:
        opt_run = OptimizationRun(
            strategy_name=strategy_name.value,
            combos_tested=0,
            status="running",
            created_at=datetime.utcnow(),
        )
        db.add(opt_run)
        await db.flush()
        opt_run_id = opt_run.id

    all_results = []
    best_score = -1.0
    best_params = None
    best_bt_result = None

    for i, params in enumerate(param_grid):
        try:
            strategy = _get_strategy_instance(strategy_name, params)
            bt = run_backtest(strategy, candles, 30, parameter_set_id=None)
            score = _score_backtest_result(bt)
            all_results.append({"params": params, "score": score, "metrics": bt.to_metrics_dict()})

            if score > best_score:
                best_score = score
                best_params = params
                best_bt_result = bt

        except Exception as exc:
            logger.debug("self_healing.optimize.combo_failed", combo=i, error=str(exc))

    if best_params is None or best_bt_result is None:
        async with get_db_session() as db:
            from sqlalchemy import update
            await db.execute(
                update(OptimizationRun)
                .where(OptimizationRun.id == opt_run_id)
                .values(status="failed", completed_at=datetime.utcnow())
            )
        return

    # Create candidate parameter set
    async with get_db_session() as db:
        candidate = StrategyParameters(
            strategy_name=strategy_name.value,
            parameter_json=best_params,
            source_window="30d",
            score=best_score,
            status="candidate",
            is_live=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(candidate)
        await db.flush()
        candidate_id = candidate.id

        # Persist optimization run result
        from sqlalchemy import update
        await db.execute(
            update(OptimizationRun)
            .where(OptimizationRun.id == opt_run_id)
            .values(
                combos_tested=len(param_grid),
                winner_parameter_set_id=candidate_id,
                status="pending_monte_carlo",
                metrics_json=best_bt_result.to_metrics_dict(),
                all_results_json={"top_10": sorted(all_results, key=lambda x: x["score"], reverse=True)[:10]},
            )
        )

    # Run Monte Carlo validation
    mc_result = _run_monte_carlo(
        best_bt_result,
        strategy_name.value,
        candidate_id,
        settings.monte_carlo_simulations,
    )

    async with get_db_session() as db:
        from sqlalchemy import select, update

        mc_record = MonteCarloRun(
            strategy_name=strategy_name.value,
            parameter_set_id=candidate_id,
            source_backtest_run_id=_get_or_create_bt_run_id(best_bt_result, candidate_id),
            simulation_count=mc_result["simulation_count"],
            robustness_score=mc_result["robustness_score"],
            random_beats_original=mc_result["random_beats_original"],
            pass_flag=mc_result["pass_flag"],
            distribution_json=mc_result["distribution"],
            created_at=datetime.utcnow(),
        )
        db.add(mc_record)

        now = datetime.utcnow()
        if mc_result["pass_flag"]:
            # Promote to live — demote previous live set
            await db.execute(
                update(StrategyParameters)
                .where(
                    StrategyParameters.strategy_name == strategy_name.value,
                    StrategyParameters.is_live == True,
                )
                .values(is_live=False, status="superseded")
            )
            await db.execute(
                update(StrategyParameters)
                .where(StrategyParameters.id == candidate_id)
                .values(is_live=True, status="live", promoted_at=now, updated_at=now)
            )
            await db.execute(
                update(OptimizationRun)
                .where(OptimizationRun.id == opt_run_id)
                .values(status="promote_live", completed_at=now)
            )
            logger.info(
                "self_healing.promote_live",
                strategy=strategy_name.value,
                score=best_score,
                robustness=mc_result["robustness_score"],
            )
            try:
                from backend.telegram.service import send_system_alert
                asyncio.create_task(
                    send_system_alert(
                        f"✅ PROMOTE LIVE: {strategy_name.value}\n"
                        f"Score: {best_score:.3f} | Robustness: {mc_result['robustness_score']:.3f}"
                    )
                )
            except Exception:
                pass
        else:
            # Discard
            await db.execute(
                update(StrategyParameters)
                .where(StrategyParameters.id == candidate_id)
                .values(
                    status="discarded",
                    discarded_at=now,
                    discard_reason=f"monte_carlo_failed:robustness={mc_result['robustness_score']:.3f}",
                    updated_at=now,
                )
            )
            await db.execute(
                update(OptimizationRun)
                .where(OptimizationRun.id == opt_run_id)
                .values(status="throw_away", completed_at=now)
            )
            logger.info(
                "self_healing.throw_away",
                strategy=strategy_name.value,
                robustness=mc_result["robustness_score"],
                random_beats=mc_result["random_beats_original"],
            )


def _run_monte_carlo(
    bt_result,
    strategy_name: str,
    candidate_id: str,
    n_simulations: int,
) -> dict:
    """
    Monte Carlo robustness test.

    Shuffles trade PnL sequences N times and measures how often
    randomized sequences outperform the original (edge dilution test).

    A robust strategy's edge should not disappear when trade order is shuffled.
    """
    if not bt_result.trades:
        return {
            "simulation_count": 0,
            "robustness_score": 0.0,
            "random_beats_original": 1.0,
            "pass_flag": False,
            "distribution": {},
        }

    closed = [t for t in bt_result.trades if t.exit_bar is not None]
    if len(closed) < 5:
        return {
            "simulation_count": 0,
            "robustness_score": 0.0,
            "random_beats_original": 1.0,
            "pass_flag": False,
            "distribution": {},
        }

    original_pnls = [t.pnl for t in closed]
    original_total = sum(original_pnls)
    original_pf = (
        sum(p for p in original_pnls if p > 0) /
        abs(sum(p for p in original_pnls if p < 0))
        if any(p < 0 for p in original_pnls) else 999.0
    )

    sim_totals = []
    sim_pfs = []
    beats = 0

    for _ in range(n_simulations):
        shuffled = original_pnls.copy()
        random.shuffle(shuffled)
        # Also add small perturbations to simulate execution variance
        perturbed = [p * (1 + random.gauss(0, 0.05)) for p in shuffled]
        sim_total = sum(perturbed)
        sim_pf = (
            sum(p for p in perturbed if p > 0) /
            abs(sum(p for p in perturbed if p < 0))
            if any(p < 0 for p in perturbed) else 999.0
        )
        sim_totals.append(sim_total)
        sim_pfs.append(sim_pf)
        if sim_total > original_total:
            beats += 1

    random_beats_ratio = beats / n_simulations

    # Robustness score: fraction of simulations where strategy beats zero PnL
    # (basic positive expectancy check under perturbation)
    positive_sim_ratio = sum(1 for t in sim_totals if t > 0) / n_simulations

    # Sharpe of simulation distribution vs original
    sim_mean = np.mean(sim_totals)
    sim_std = np.std(sim_totals)
    z_score = (original_total - sim_mean) / sim_std if sim_std > 0 else 0.0
    robustness_score = float(np.clip(positive_sim_ratio, 0.0, 1.0))

    # Pass: random beats original < threshold AND robustness > threshold
    pass_flag = (
        random_beats_ratio < (1 - settings.monte_carlo_robustness_threshold) and
        robustness_score > settings.monte_carlo_robustness_threshold
    )

    return {
        "simulation_count": n_simulations,
        "robustness_score": round(robustness_score, 4),
        "random_beats_original": round(random_beats_ratio, 4),
        "pass_flag": pass_flag,
        "distribution": {
            "sim_mean_pnl": round(sim_mean, 2),
            "sim_std_pnl": round(sim_std, 2),
            "original_total_pnl": round(original_total, 2),
            "z_score": round(z_score, 3),
            "positive_sim_ratio": round(positive_sim_ratio, 4),
        },
    }


def _get_or_create_bt_run_id(bt_result, candidate_id: str) -> str:
    """
    Placeholder — returns a dummy ID since we don't persist backtest
    runs synchronously in the optimization loop.
    In production, refactor to persist BT runs during the search phase.
    """
    return candidate_id  # Use candidate_id as surrogate for now
