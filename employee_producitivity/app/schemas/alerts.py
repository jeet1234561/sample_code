"""Module D — Pydantic schemas for alerts and rules API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# --- Alert Rule schemas ---

class AlertRuleCreate(BaseModel):
    metric_name: str
    operator: str            # >, <, >=, <=, ==
    threshold: float
    threshold_unit: Optional[str] = None
    time_window: Optional[str] = None
    priority: str            # critical, warning, info
    targets: str             # "Employee", "Team Lead", etc.
    description: Optional[str] = None
    is_active: bool = True


class AlertRuleUpdate(BaseModel):
    metric_name: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[float] = None
    threshold_unit: Optional[str] = None
    time_window: Optional[str] = None
    priority: Optional[str] = None
    targets: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class AlertRuleResponse(BaseModel):
    rule_id: str
    metric_name: str
    operator: str
    threshold: float
    threshold_unit: Optional[str] = None
    time_window: Optional[str] = None
    priority: str
    targets: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Alert Record schemas ---

class AlertRecordResponse(BaseModel):
    alert_id: str
    rule_id: str
    metric_name: str
    metric_value: float
    threshold: float
    operator: str
    employee_id: Optional[str] = None
    team: Optional[str] = None
    priority: str
    status: str
    targets: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    fired_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertStatusUpdate(BaseModel):
    status: str  # "acknowledged" or "resolved"
