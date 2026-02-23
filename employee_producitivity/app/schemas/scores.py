"""Module C — Pydantic schemas for scoring API responses."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class EmployeeScoreResponse(BaseModel):
    employee_id: str
    delivery_score: float
    quality_score: float
    team_exp_score: float
    business_value_score: float
    overall_score: float
    weights: Optional[Dict[str, float]] = None
    details: Optional[Dict[str, Any]] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    computed_at: datetime

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    employee_id: str
    overall_score: float
    delivery_score: float
    quality_score: float
    team_exp_score: float
    business_value_score: float
    computed_at: datetime

    model_config = {"from_attributes": True}
