"""System state and health endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.common import SystemStateSchema
from backend.db.base import get_db
from backend.db.models import SystemState

router = APIRouter()


@router.get("/state", response_model=List[SystemStateSchema])
async def get_system_state(db: AsyncSession = Depends(get_db)):
    """Return current state of all tracked system components."""
    result = await db.execute(
        select(SystemState).order_by(SystemState.component_name)
    )
    return result.scalars().all()


@router.get("/state/{component_name}", response_model=SystemStateSchema)
async def get_component_state(component_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SystemState).where(SystemState.component_name == component_name)
    )
    state = result.scalar_one_or_none()
    if not state:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Component {component_name!r} not found")
    return state
