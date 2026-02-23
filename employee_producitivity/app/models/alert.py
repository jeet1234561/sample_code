"""Module D — Alert and AlertRule models.

D1: Rule Storage — admin-configurable trigger rules
D2: AlertRecord — generated when a rule is breached
"""

from sqlalchemy import Column, String, Float, Boolean, DateTime, Integer, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from app.models.base import Base, utcnow, new_uuid


class AlertRule(Base):
    """D1: Admin-configurable trigger rules.

    Example: IF LeadTime > 48h THEN alert TeamLead (priority=warning)
    """
    __tablename__ = "alert_rules"

    rule_id = Column(String, primary_key=True, default=new_uuid)
    metric_name = Column(String(50), nullable=False)        # lead_time, change_failure_rate, etc.
    operator = Column(String(5), nullable=False)             # >, <, >=, <=, ==
    threshold = Column(Float, nullable=False)                # numeric threshold value
    threshold_unit = Column(String(20), nullable=True)       # hours, percentage, count, etc.
    time_window = Column(String(20), nullable=True)          # "7 days", "30 days", "real-time"
    priority = Column(String(10), nullable=False)            # critical, warning, info
    targets = Column(String, nullable=False)                 # "Employee", "Team Lead", "Employee + TL", "Manager"
    description = Column(String, nullable=True)              # Human-readable rule description
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AlertRecord(Base):
    """D2: Generated when a rule breach is detected.

    Stores the alert with metric context for notification and dashboard display.
    """
    __tablename__ = "alert_records"

    alert_id = Column(String, primary_key=True, default=new_uuid)
    rule_id = Column(String, nullable=False, index=True)
    metric_name = Column(String(50), nullable=False)
    metric_value = Column(Float, nullable=False)             # actual value that breached
    threshold = Column(Float, nullable=False)                # threshold from the rule
    operator = Column(String(5), nullable=False)
    employee_id = Column(String, nullable=True, index=True)  # null if team-level
    team = Column(String, nullable=True)
    priority = Column(String(10), nullable=False)            # critical, warning, info
    status = Column(String(15), default="active")            # active, acknowledged, resolved
    targets = Column(String, nullable=False)                 # who should be notified
    message = Column(String, nullable=True)                  # auto-generated alert message
    details = Column(JSONB, nullable=True)                   # additional context
    fired_at = Column(DateTime(timezone=True), default=utcnow)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_alert_status", "status"),
        Index("ix_alert_priority_status", "priority", "status"),
        Index("ix_alert_fired_at", "fired_at"),
    )
