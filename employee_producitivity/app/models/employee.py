from sqlalchemy import Column, String, Boolean, Index

from app.models.base import Base


class Employee(Base):
    __tablename__ = "employees"

    employee_id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    role = Column(String)
    team = Column(String)
    jira_account_id = Column(String, index=True)
    gitlab_username = Column(String, index=True)
    jenkins_username = Column(String, index=True)
    is_active = Column(Boolean, default=True)
