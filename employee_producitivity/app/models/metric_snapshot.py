from sqlalchemy import Column, String, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, utcnow, new_uuid


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    snapshot_id = Column(String, primary_key=True, default=new_uuid)
    employee_id = Column(String, nullable=False, index=True)
    metric_name = Column(String(50), nullable=False)  # lead_time, deploy_freq, cfr, etc.
    metric_category = Column(String(20), nullable=False)  # delivery, quality, team_exp, business
    value = Column(Float, nullable=False)
    unit = Column(String(20))  # hours, percentage, count, dollars
    window_start = Column(DateTime(timezone=True))
    window_end = Column(DateTime(timezone=True))
    computed_at = Column(DateTime(timezone=True), primary_key=True, default=utcnow)
    details = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_metric_emp_name_ts", "employee_id", "metric_name", "computed_at"),
    )
