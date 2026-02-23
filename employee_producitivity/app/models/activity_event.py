from sqlalchemy import Column, String, DateTime, Index, text
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, utcnow, new_uuid


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    event_id = Column(String, primary_key=True, default=new_uuid)
    employee_id = Column(String, nullable=False, index=True)
    source = Column(String(20), nullable=False)  # Jira, Git, CICD, ClaudeAI, BizValue
    timestamp = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    payload = Column(JSONB, nullable=False)
    raw_source_id = Column(String, nullable=True)
    ingested_at = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_activity_source_ts", "source", "timestamp"),
        Index("ix_activity_employee_ts", "employee_id", "timestamp"),
        Index(
            "ix_activity_raw_source_id",
            "raw_source_id",
            "timestamp",
            unique=True,
            postgresql_where=text("raw_source_id IS NOT NULL"),
        ),
    )
