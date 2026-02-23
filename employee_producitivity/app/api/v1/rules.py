"""Module D1 — Alert Rules CRUD API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import AlertRule
from app.models.base import new_uuid
from app.schemas.alerts import AlertRuleCreate, AlertRuleUpdate, AlertRuleResponse

router = APIRouter()


@router.get("/", response_model=List[AlertRuleResponse])
async def list_rules(db: AsyncSession = Depends(get_db)):
    """List all alert rules."""
    result = await db.execute(
        select(AlertRule).order_by(AlertRule.created_at.desc())
    )
    rules = result.scalars().all()
    return [AlertRuleResponse.model_validate(r) for r in rules]


@router.post("/", response_model=AlertRuleResponse, status_code=201)
async def create_rule(body: AlertRuleCreate, db: AsyncSession = Depends(get_db)):
    """Create a new alert rule."""
    rule = AlertRule(
        rule_id=new_uuid(),
        metric_name=body.metric_name,
        operator=body.operator,
        threshold=body.threshold,
        threshold_unit=body.threshold_unit,
        time_window=body.time_window,
        priority=body.priority,
        targets=body.targets,
        description=body.description,
        is_active=body.is_active,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return AlertRuleResponse.model_validate(rule)


@router.get("/{rule_id}", response_model=AlertRuleResponse)
async def get_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single alert rule by ID."""
    result = await db.execute(
        select(AlertRule).where(AlertRule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return AlertRuleResponse.model_validate(rule)


@router.patch("/{rule_id}", response_model=AlertRuleResponse)
async def update_rule(
    rule_id: str, body: AlertRuleUpdate, db: AsyncSession = Depends(get_db)
):
    """Update an existing alert rule (partial update)."""
    result = await db.execute(
        select(AlertRule).where(AlertRule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)
    return AlertRuleResponse.model_validate(rule)


@router.delete("/{rule_id}", response_model=dict)
async def delete_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    """Delete an alert rule."""
    result = await db.execute(
        select(AlertRule).where(AlertRule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    await db.delete(rule)
    await db.commit()
    return {"status": "ok", "message": f"Rule {rule_id} deleted"}
