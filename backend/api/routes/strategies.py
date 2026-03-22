"""Strategy and parameter set endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.common import StrategyParametersSchema
from backend.db.base import get_db
from backend.db.models import StrategyParameters

router = APIRouter()


@router.get("", response_model=List[StrategyParametersSchema])
async def list_strategies(
    strategy_name: Optional[str] = Query(default=None),
    is_live: Optional[bool] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """List strategy parameter sets."""
    q = select(StrategyParameters)
    if strategy_name:
        q = q.where(StrategyParameters.strategy_name == strategy_name)
    if is_live is not None:
        q = q.where(StrategyParameters.is_live == is_live)
    q = q.order_by(StrategyParameters.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/rankings")
async def get_strategy_rankings(db: AsyncSession = Depends(get_db)):
    """
    Return live strategy parameter sets with their scores,
    ranked from highest to lowest performing.
    """
    result = await db.execute(
        select(StrategyParameters)
        .where(StrategyParameters.is_live == True)
        .order_by(StrategyParameters.score.desc().nullslast())
    )
    live_params = result.scalars().all()

    rankings = []
    for rank, sp in enumerate(live_params, start=1):
        rankings.append({
            "rank": rank,
            "strategy_name": sp.strategy_name,
            "parameter_set_id": sp.id,
            "score": sp.score,
            "overfit_flag": sp.overfit_flag,
            "suppressed_flag": sp.suppressed_flag,
            "promoted_at": sp.promoted_at.isoformat() if sp.promoted_at else None,
            "status": sp.status,
        })

    return {"rankings": rankings, "total": len(rankings)}
