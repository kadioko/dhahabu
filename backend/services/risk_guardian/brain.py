"""
Trading Brain — Central 30-minute decision pipeline.

This is the orchestration core that:
  1. Fetches current candle data for all timeframes
  2. Computes volatility and market regime
  3. Runs all 4 strategies
  4. Scores and ranks signals using performance history + context fit
  5. Applies risk checks (daily cap, shutdown, exposure, dedup)
  6. Adjusts position sizing
  7. Approves/suppresses signals
  8. Persists all decisions to the database
  9. Sends approved signals to Telegram

Every decision is auditable. Nothing is discarded silently.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from backend.core.config import settings
from backend.core.constants import (
    ApprovalStatus,
    LIVE_TIMEFRAMES,
    MarketRegime,
    StrategyName,
    Timeframe,
    VolatilityRegime,
)
from backend.core.logging import get_logger
from backend.db.base import get_db_session
from backend.db.models import Signal, StrategyParameters, Trade
from backend.services.market_data.service import get_latest_candles_df
from backend.services.position_sizing.service import compute_position_size
from backend.services.risk_guardian.service import _build_risk_state, record_risk_event
from backend.services.volatility_regime.service import compute_volatility_state
from backend.strategies.base import StrategyContext, StrategySignal
from backend.core.constants import RiskEventType, RiskSeverity

logger = get_logger(__name__)


# ── Strategy registry ─────────────────────────────────────────────────────────

def _get_strategy_instance(name: StrategyName, params: dict):
    if name == StrategyName.LIQUIDITY_SWEEPS:
        from backend.strategies.liquidity_sweeps.strategy import LiquiditySweepsStrategy
        return LiquiditySweepsStrategy(params)
    elif name == StrategyName.TREND_CONTINUATION:
        from backend.strategies.trend_continuation.strategy import TrendContinuationStrategy
        return TrendContinuationStrategy(params)
    elif name == StrategyName.BREAKOUT_EXPANSION:
        from backend.strategies.breakout_expansion.strategy import BreakoutExpansionStrategy
        return BreakoutExpansionStrategy(params)
    elif name == StrategyName.EMA_MOMENTUM:
        from backend.strategies.ema_momentum.strategy import EMAMomentumStrategy
        return EMAMomentumStrategy(params)
    raise ValueError(f"Unknown strategy: {name}")


# ── Signal scoring ────────────────────────────────────────────────────────────

async def _score_signal(
    signal: StrategySignal,
    param_set: Optional[StrategyParameters],
    vol_state,
    db,
) -> float:
    """
    Produce a composite brain_score for a signal.

    Inputs:
      - Signal confidence (0-1)
      - Strategy's recent live win rate
      - Strategy's recent profit factor
      - Walk-forward OOS degradation (penalize poor WF results)
      - Monte Carlo robustness
      - Regime fit (bonus if signal aligns with current regime)
      - Overfit flag (hard penalty)
    """
    score = signal.confidence * 40  # base: up to 40 points

    if param_set:
        # Historical performance contribution (up to 30 points)
        score_from_db = param_set.score or 0.5
        score += score_from_db * 30

        # Overfit penalty
        if param_set.overfit_flag:
            score *= 0.4
        if param_set.suppressed_flag:
            score *= 0.2

    # Regime fit bonus (up to 15 points)
    regime_bonus = _compute_regime_fit(signal, vol_state)
    score += regime_bonus * 15

    # Risk-reward quality (up to 15 points)
    rr = signal.risk_reward
    if rr >= 3.0:
        score += 15
    elif rr >= 2.0:
        score += 10
    elif rr >= 1.5:
        score += 5

    return round(score, 2)


def _compute_regime_fit(signal: StrategySignal, vol_state) -> float:
    """Return 0-1 regime fit score for the signal."""
    regime = vol_state.market_regime
    direction = signal.direction.value

    fit_map = {
        (StrategyName.LIQUIDITY_SWEEPS, MarketRegime.RANGING): 0.9,
        (StrategyName.LIQUIDITY_SWEEPS, MarketRegime.CHOPPY): 0.8,
        (StrategyName.TREND_CONTINUATION, MarketRegime.TRENDING_UP): 0.9,
        (StrategyName.TREND_CONTINUATION, MarketRegime.TRENDING_DOWN): 0.9,
        (StrategyName.BREAKOUT_EXPANSION, MarketRegime.BREAKOUT): 0.95,
        (StrategyName.BREAKOUT_EXPANSION, MarketRegime.RANGING): 0.7,
        (StrategyName.EMA_MOMENTUM, MarketRegime.TRENDING_UP): 0.85,
        (StrategyName.EMA_MOMENTUM, MarketRegime.TRENDING_DOWN): 0.85,
    }
    return fit_map.get((signal.strategy_name, regime), 0.5)


# ── Exposure deduplication ────────────────────────────────────────────────────

async def _check_duplicate_direction(
    signal: StrategySignal, db
) -> bool:
    """
    Returns True if there is already an open trade in the same direction.
    Used to block overexposure to a single directional bet.
    """
    from sqlalchemy import select, and_
    open_trades = await db.execute(
        select(Trade).where(Trade.status.in_(["pending", "triggered", "open"]))
    )
    trades = open_trades.scalars().all()

    from backend.db.models import Signal as SignalModel
    for trade in trades:
        sig_res = await db.execute(
            select(SignalModel).where(SignalModel.id == trade.signal_id)
        )
        existing_sig = sig_res.scalar_one_or_none()
        if existing_sig and existing_sig.direction == signal.direction.value:
            if existing_sig.symbol == signal.symbol:
                return True
    return False


# ── Main brain pipeline ───────────────────────────────────────────────────────

async def run_trading_brain() -> None:
    """
    30-minute central decision pipeline.

    All outcomes are persisted to the database for full auditability.
    """
    logger.info("brain.run.start")
    symbol = settings.market_data_symbol

    async with get_db_session() as db:
        # ── Step 1: Risk pre-check ────────────────────────────────────────────
        risk_state = await _build_risk_state(db)
        if not risk_state.can_trade:
            logger.info("brain.blocked", reason=risk_state.block_reason)
            return

        # ── Step 2: Load candle data ──────────────────────────────────────────
        candles = {}
        for tf in LIVE_TIMEFRAMES:
            df = await get_latest_candles_df(symbol, tf, limit=200)
            if not df.empty:
                candles[tf] = df

        if not candles:
            logger.warning("brain.no_candle_data", symbol=symbol)
            return

        # ── Step 3: Compute volatility/regime state ───────────────────────────
        primary_tf = Timeframe.H1
        primary_df = candles.get(primary_tf)
        if primary_df is None or len(primary_df) < 30:
            logger.warning("brain.insufficient_h1_data")
            return

        vol_state = compute_volatility_state(primary_df, symbol)
        ctx = StrategyContext(
            symbol=symbol,
            candles=candles,
            volatility_regime=vol_state.regime,
            market_regime=vol_state.market_regime,
            atr=vol_state.atr,
            current_price=float(primary_df["close"].iloc[-1]),
        )

        # ── Step 4: Run all strategies ────────────────────────────────────────
        from sqlalchemy import select

        all_signals: list[tuple[StrategySignal, Optional[StrategyParameters]]] = []

        for strategy_name in StrategyName:
            # Load live parameter set
            param_res = await db.execute(
                select(StrategyParameters).where(
                    StrategyParameters.strategy_name == strategy_name.value,
                    StrategyParameters.is_live == True,
                    StrategyParameters.suppressed_flag == False,
                )
            )
            param_set = param_res.scalar_one_or_none()

            if param_set:
                params = param_set.parameter_json
                param_set_id = param_set.id
            else:
                # Use default params if no live set exists
                params = _get_default_params(strategy_name)
                param_set_id = None

            try:
                strategy = _get_strategy_instance(strategy_name, params)
                strategy.parameter_set_id = param_set_id
                signals = strategy.generate_signals(ctx)
                for sig in signals:
                    all_signals.append((sig, param_set))
            except Exception as exc:
                logger.error(
                    "brain.strategy.error",
                    strategy=strategy_name.value,
                    error=str(exc),
                )

        logger.info("brain.signals.generated", count=len(all_signals))

        # ── Step 5: Score signals ─────────────────────────────────────────────
        scored: list[tuple[StrategySignal, Optional[StrategyParameters], float]] = []
        for sig, ps in all_signals:
            score = await _score_signal(sig, ps, vol_state, db)
            scored.append((sig, ps, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[2], reverse=True)

        # ── Step 6: Apply risk filters and persist ────────────────────────────
        approved_count = 0

        for sig, ps, brain_score in scored:
            approval = ApprovalStatus.APPROVED
            suppression_reason = None

            # Check overfit suppression
            if ps and ps.overfit_flag:
                approval = ApprovalStatus.SUPPRESSED
                suppression_reason = "parameter_set_overfitted"

            # Check RR threshold
            elif sig.risk_reward < 1.5:
                approval = ApprovalStatus.SUPPRESSED
                suppression_reason = f"risk_reward_too_low:{sig.risk_reward:.2f}"

            # Check confidence
            elif sig.confidence < 0.40:
                approval = ApprovalStatus.SUPPRESSED
                suppression_reason = f"low_confidence:{sig.confidence:.2f}"

            # Check max simultaneous trades
            elif risk_state.open_trade_count + approved_count >= settings.max_simultaneous_trades:
                approval = ApprovalStatus.SUPPRESSED
                suppression_reason = "max_simultaneous_trades"

            # Check duplicate direction
            elif await _check_duplicate_direction(sig, db):
                approval = ApprovalStatus.SUPPRESSED
                suppression_reason = "duplicate_directional_exposure"

            # Position sizing
            if approval == ApprovalStatus.APPROVED:
                sizing = compute_position_size(
                    entry=sig.entry,
                    stop_loss=sig.stop_loss,
                    volatility_regime=vol_state.regime,
                    current_exposure_pct=risk_state.estimated_open_exposure_pct,
                    strategy_risk_multiplier=ps.parameter_json.get("risk_multiplier", 1.0) if ps else 1.0,
                )
                if sizing.position_size <= 0:
                    approval = ApprovalStatus.SUPPRESSED
                    suppression_reason = "zero_position_size"

            # Persist signal
            signal_record = Signal(
                strategy_name=sig.strategy_name.value,
                parameter_set_id=sig.parameter_set_id,
                symbol=sig.symbol,
                timeframe=sig.timeframe.value,
                direction=sig.direction.value,
                entry=sig.entry,
                stop_loss=sig.stop_loss,
                take_profit=sig.take_profit,
                confidence=sig.confidence,
                rationale_json=sig.rationale,
                brain_score=brain_score,
                approval_status=approval.value,
                suppression_reason=suppression_reason,
                risk_metadata_json={
                    "vol_regime": vol_state.regime.value,
                    "market_regime": vol_state.market_regime.value,
                    "atr": vol_state.atr,
                    "risk_reward": sig.risk_reward,
                },
                created_at=datetime.utcnow(),
            )
            db.add(signal_record)

            if approval == ApprovalStatus.APPROVED:
                approved_count += 1
                logger.info(
                    "brain.signal.approved",
                    strategy=sig.strategy_name.value,
                    direction=sig.direction.value,
                    confidence=sig.confidence,
                    score=brain_score,
                )

                # Create pending trade record
                await db.flush()
                trade = Trade(
                    signal_id=signal_record.id,
                    status="pending",
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    position_size=sizing.position_size if approval == ApprovalStatus.APPROVED else 0.01,
                    consecutive_loss_seq_snapshot=risk_state.consecutive_sl_hits,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(trade)
            else:
                logger.info(
                    "brain.signal.suppressed",
                    strategy=sig.strategy_name.value,
                    reason=suppression_reason,
                    score=brain_score,
                )

        # Commit signals and trades
        await db.flush()

        # ── Step 7: Send approved signals to Telegram ─────────────────────────
        if approved_count > 0:
            try:
                from backend.telegram.service import send_signal_batch
                # Re-fetch approved signals to get IDs
                from sqlalchemy import and_
                new_signals_res = await db.execute(
                    select(Signal)
                    .where(
                        Signal.approval_status == "approved",
                        Signal.created_at >= datetime.utcnow().replace(second=0, microsecond=0),
                    )
                    .order_by(Signal.created_at.desc())
                    .limit(approved_count)
                )
                new_signals = new_signals_res.scalars().all()
                asyncio.create_task(send_signal_batch(new_signals))
            except Exception as exc:
                logger.error("brain.telegram.failed", error=str(exc))

    logger.info(
        "brain.run.complete",
        total_signals=len(all_signals),
        approved=approved_count,
    )


def _get_default_params(strategy_name: StrategyName) -> dict:
    """Return default parameters for a strategy (used before first optimization)."""
    from backend.strategies.liquidity_sweeps.strategy import DEFAULT_PARAMS as LS_PARAMS
    from backend.strategies.trend_continuation.strategy import DEFAULT_PARAMS as TC_PARAMS
    from backend.strategies.breakout_expansion.strategy import DEFAULT_PARAMS as BE_PARAMS
    from backend.strategies.ema_momentum.strategy import DEFAULT_PARAMS as EM_PARAMS

    defaults = {
        StrategyName.LIQUIDITY_SWEEPS: LS_PARAMS,
        StrategyName.TREND_CONTINUATION: TC_PARAMS,
        StrategyName.BREAKOUT_EXPANSION: BE_PARAMS,
        StrategyName.EMA_MOMENTUM: EM_PARAMS,
    }
    return dict(defaults.get(strategy_name, {}))
