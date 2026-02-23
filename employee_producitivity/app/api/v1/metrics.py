from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.metric_snapshot import MetricSnapshot
from app.schemas.metrics import MetricSnapshotResponse
from app.metrics.engine import MetricEngine

router = APIRouter()


@router.get("/", response_model=List[MetricSnapshotResponse])
async def get_metrics(
    employee_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    metric_name: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve computed metric snapshots with optional filters."""
    query = select(MetricSnapshot).order_by(MetricSnapshot.computed_at.desc())

    conditions = []
    if employee_id:
        conditions.append(MetricSnapshot.employee_id == employee_id)
    if category:
        conditions.append(MetricSnapshot.metric_category == category)
    if metric_name:
        conditions.append(MetricSnapshot.metric_name == metric_name)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.limit(limit)
    result = await db.execute(query)
    snapshots = result.scalars().all()

    return [
        MetricSnapshotResponse(
            employee_id=s.employee_id,
            metric_name=s.metric_name,
            category=s.metric_category,
            value=s.value,
            unit=s.unit,
            window_start=s.window_start,
            window_end=s.window_end,
            computed_at=s.computed_at,
            details=s.details,
        )
        for s in snapshots
    ]


@router.post("/compute", response_model=dict)
async def trigger_metric_computation(db: AsyncSession = Depends(get_db)):
    """Manually trigger metric computation for all employees."""
    engine = MetricEngine(session=db)
    await engine.compute_all()
    return {"status": "ok", "message": "Metric computation completed"}
