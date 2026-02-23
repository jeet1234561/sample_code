from sqlalchemy import Column, String, Float, DateTime

from app.models.base import Base, utcnow, new_uuid


class BusinessValueTag(Base):
    __tablename__ = "business_value_tags"

    feature_id = Column(String, primary_key=True)
    feature_name = Column(String, nullable=False)
    dollar_value = Column(Float, nullable=False)
    tagged_by = Column(String)
    tagged_at = Column(DateTime(timezone=True), default=utcnow)


class FeatureContribution(Base):
    __tablename__ = "feature_contributions"

    id = Column(String, primary_key=True, default=new_uuid)
    feature_id = Column(String, nullable=False, index=True)
    employee_id = Column(String, nullable=False, index=True)
    contribution_factor = Column(Float, nullable=False)  # 0.0 to 1.0
    source_evidence = Column(String)  # e.g. "jira_issue:DASH-1234"
