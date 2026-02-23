"""Module C — Score models.

Stores computed sub-scores and overall scores per employee.
"""

from sqlalchemy import Column, String, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, utcnow, new_uuid


class EmployeeScore(Base):
    __tablename__ = "employee_scores"

    score_id = Column(String, primary_key=True, default=new_uuid)
    employee_id = Column(String, nullable=False, index=True)

    # Sub-scores (0-100)
    delivery_score = Column(Float, nullable=False, default=0.0)
    quality_score = Column(Float, nullable=False, default=0.0)
    team_exp_score = Column(Float, nullable=False, default=0.0)
    business_value_score = Column(Float, nullable=False, default=0.0)

    # Overall weighted score (0-100)
    overall_score = Column(Float, nullable=False, default=0.0)

    # Weights used (stored for auditability)
    weights = Column(JSONB, nullable=True)

    # Breakdown details for drill-down
    details = Column(JSONB, nullable=True)

    # Time context
    window_start = Column(DateTime(timezone=True))
    window_end = Column(DateTime(timezone=True))
    computed_at = Column(DateTime(timezone=True), primary_key=True, default=utcnow)

    __table_args__ = (
        Index("ix_score_emp_ts", "employee_id", "computed_at"),
    )
