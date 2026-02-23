"""Module D — Alert record API endpoints."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import AlertRecord
from app.schemas.alerts import AlertRecordResponse, AlertStatusUpdate
from app.alerts.engine import AlertEngine

router = APIRouter()


@router.get("/", response_model=List[AlertRecordResponse])
async def get_alerts(
    status: Optional[str] = Query(None, description="Filter by status: active, acknowledged, resolved"),
    priority: Optional[str] = Query(None, description="Filter by priority: critical, warning, info"),
    employee_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get alert records with optional filters."""
    query = select(AlertRecord).order_by(AlertRecord.fired_at.desc())

    conditions = []
    if status:
        conditions.append(AlertRecord.status == status)
    if priority:
        conditions.append(AlertRecord.priority == priority)
    if employee_id:
        conditions.append(AlertRecord.employee_id == employee_id)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.limit(limit)
    result = await db.execute(query)
    alerts = result.scalars().all()

    return [AlertRecordResponse.model_validate(a) for a in alerts]


@router.get("/summary", response_model=dict)
async def get_alert_summary(db: AsyncSession = Depends(get_db)):
    """Get a summary count of alerts by status and priority."""
    result = await db.execute(select(AlertRecord))
    all_alerts = result.scalars().all()

    summary = {
        "total": len(all_alerts),
        "by_status": {"active": 0, "acknowledged": 0, "resolved": 0},
        "by_priority": {"critical": 0, "warning": 0, "info": 0},
    }
    for a in all_alerts:
        if a.status in summary["by_status"]:
            summary["by_status"][a.status] += 1
        if a.priority in summary["by_priority"]:
            summary["by_priority"][a.priority] += 1

    return summary


@router.patch("/{alert_id}", response_model=AlertRecordResponse)
async def update_alert_status(
    alert_id: str,
    body: AlertStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an alert's status (acknowledge or resolve)."""
    result = await db.execute(
        select(AlertRecord).where(AlertRecord.alert_id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    now = datetime.now(timezone.utc)
    if body.status == "acknowledged":
        alert.status = "acknowledged"
        alert.acknowledged_at = now
    elif body.status == "resolved":
        alert.status = "resolved"
        alert.resolved_at = now
    else:
        raise HTTPException(
            status_code=400,
            detail="Status must be 'acknowledged' or 'resolved'",
        )

    await db.commit()
    return AlertRecordResponse.model_validate(alert)


@router.post("/evaluate", response_model=dict)
async def trigger_alert_evaluation(db: AsyncSession = Depends(get_db)):
    """Manually trigger alert rule evaluation for all employees."""
    engine = AlertEngine(session=db)
    await engine.evaluate_all_rules()
    return {"status": "ok", "message": "Alert evaluation completed"}
