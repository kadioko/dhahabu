"""
Bootstrap script: seed the database with default live parameter sets
for all 4 strategies so the trading brain can run on first deploy.

Usage: python scripts/init_live_params.py
"""

from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from backend.core.config import settings
from backend.db.base import AsyncSessionLocal
from backend.db.models import StrategyParameters
from backend.strategies.liquidity_sweeps.strategy import DEFAULT_PARAMS as LS
from backend.strategies.trend_continuation.strategy import DEFAULT_PARAMS as TC
from backend.strategies.breakout_expansion.strategy import DEFAULT_PARAMS as BE
from backend.strategies.ema_momentum.strategy import DEFAULT_PARAMS as EM
from backend.core.constants import StrategyName


DEFAULTS = {
    StrategyName.LIQUIDITY_SWEEPS: LS,
    StrategyName.TREND_CONTINUATION: TC,
    StrategyName.BREAKOUT_EXPANSION: BE,
    StrategyName.EMA_MOMENTUM: EM,
}


async def seed():
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        for name, params in DEFAULTS.items():
            existing = await db.execute(
                select(StrategyParameters).where(
                    StrategyParameters.strategy_name == name.value,
                    StrategyParameters.is_live == True,
                )
            )
            if existing.scalar_one_or_none():
                print(f"[SKIP] {name.value} already has a live parameter set")
                continue

            sp = StrategyParameters(
                strategy_name=name.value,
                parameter_json=dict(params),
                source_window="default",
                score=0.5,
                status="live",
                is_live=True,
                overfit_flag=False,
                suppressed_flag=False,
                promoted_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(sp)
            print(f"[SEED] {name.value} — default parameters seeded as live")

        await db.commit()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())
