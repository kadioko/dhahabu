"""Validation engine endpoints — backtests, walk-forward, Monte Carlo, overfit."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.common import (
    BacktestRunSchema,
    MonteCarloRunSchema,
    WalkForwardRunSchema,
)
from backend.db.base import get_db
from backend.db.models import (
    BacktestRun,
    MonteCarloRun,
    OptimizationRun,
    StrategyParameters,
    WalkForwardRun,
)

router = APIRouter()


@router.get("/backtests", response_model=List[BacktestRunSchema])
async def get_backtest_runs(
    strategy_name: Optional[str] = Query(default=None),
    days: int = Query(default=7),
    limit: int = Query(default=50),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = select(BacktestRun).where(BacktestRun.created_at >= cutoff)
    if strategy_name:
        q = q.where(BacktestRun.strategy_name == strategy_name)
    result = await db.execute(q.order_by(BacktestRun.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/walk-forward", response_model=List[WalkForwardRunSchema])
async def get_walk_forward_runs(
    strategy_name: Optional[str] = Query(default=None),
    overfit_only: bool = Query(default=False),
    days: int = Query(default=7),
    limit: int = Query(default=50),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = select(WalkForwardRun).where(WalkForwardRun.created_at >= cutoff)
    if strategy_name:
        q = q.where(WalkForwardRun.strategy_name == strategy_name)
    if overfit_only:
        q = q.where(WalkForwardRun.overfit_flag == True)
    result = await db.execute(q.order_by(WalkForwardRun.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/monte-carlo", response_model=List[MonteCarloRunSchema])
async def get_monte_carlo_runs(
    strategy_name: Optional[str] = Query(default=None),
    days: int = Query(default=7),
    limit: int = Query(default=50),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = select(MonteCarloRun).where(MonteCarloRun.created_at >= cutoff)
    if strategy_name:
        q = q.where(MonteCarloRun.strategy_name == strategy_name)
    result = await db.execute(q.order_by(MonteCarloRun.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/overfit-flags")
async def get_overfit_flags(db: AsyncSession = Depends(get_db)):
    """Return all parameter sets currently flagged as overfit."""
    result = await db.execute(
        select(StrategyParameters)
        .where(StrategyParameters.overfit_flag == True)
        .order_by(StrategyParameters.updated_at.desc())
    )
    overfit = result.scalars().all()
    return {
        "overfit_sets": [
            {
                "id": sp.id,
                "strategy_name": sp.strategy_name,
                "score": sp.score,
                "suppressed_flag": sp.suppressed_flag,
                "status": sp.status,
            }
            for sp in overfit
        ]
    }


@router.get("/parameter-search")
async def get_parameter_search_results(
    strategy_name: Optional[str] = Query(default=None),
    days: int = Query(default=7),
    limit: int = Query(default=20),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = select(OptimizationRun).where(OptimizationRun.created_at >= cutoff)
    if strategy_name:
        q = q.where(OptimizationRun.strategy_name == strategy_name)
    result = await db.execute(q.order_by(OptimizationRun.created_at.desc()).limit(limit))
    runs = result.scalars().all()
    return {
        "runs": [
            {
                "id": r.id,
                "strategy_name": r.strategy_name,
                "combos_tested": r.combos_tested,
                "winner_parameter_set_id": r.winner_parameter_set_id,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in runs
        ]
    }


@router.get("/promotions")
async def get_promotion_history(
    days: int = Query(default=30),
    db: AsyncSession = Depends(get_db),
):
    """Return parameter sets recently promoted to live or discarded."""
    from datetime import date, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(StrategyParameters)
        .where(
            StrategyParameters.promoted_at >= cutoff,
        )
        .order_by(StrategyParameters.promoted_at.desc())
        .limit(50)
    )
    promoted = result.scalars().all()

    discarded_result = await db.execute(
        select(StrategyParameters)
        .where(StrategyParameters.discarded_at >= cutoff)
        .order_by(StrategyParameters.discarded_at.desc())
        .limit(50)
    )
    discarded = discarded_result.scalars().all()

    return {
        "promoted": [
            {
                "id": sp.id,
                "strategy_name": sp.strategy_name,
                "score": sp.score,
                "promoted_at": sp.promoted_at.isoformat() if sp.promoted_at else None,
                "status": "promote_live",
            }
            for sp in promoted
        ],
        "discarded": [
            {
                "id": sp.id,
                "strategy_name": sp.strategy_name,
                "score": sp.score,
                "discarded_at": sp.discarded_at.isoformat() if sp.discarded_at else None,
                "discard_reason": sp.discard_reason,
                "status": "throw_away",
            }
            for sp in discarded
        ],
    }
