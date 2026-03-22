"""Health and liveness endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.base import get_db

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Liveness probe — returns 200 when the service is up and DB is reachable."""
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "db": "ok" if db_ok else "error",
        "service": "dhahabu",
    }


@router.get("/ready")
async def readiness_check():
    """Readiness probe — used by Railway / load balancers."""
    return {"ready": True, "timestamp": datetime.utcnow().isoformat()}
