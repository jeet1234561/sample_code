from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, utcnow


class ConnectorState(Base):
    __tablename__ = "connector_states"

    connector_name = Column(String, primary_key=True)
    last_sync_at = Column(DateTime(timezone=True))
    last_cursor = Column(String, nullable=True)
    events_fetched_total = Column(Integer, default=0)
    status = Column(String(20), default="idle")  # idle, running, error, healthy
    error_detail = Column(String, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
