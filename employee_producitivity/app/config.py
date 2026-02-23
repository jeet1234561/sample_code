from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://epiap:epiap_dev_secret@localhost:5432/epiap"
    database_url_sync: str = "postgresql://epiap:epiap_dev_secret@localhost:5432/epiap"

    # Jira
    jira_base_url: str = ""
    jira_api_token: str = ""
    jira_user_email: str = ""
    jira_projects: str = ""  # Comma-separated project keys (e.g., "JET,ILCWA,VBP"). Empty = all projects

    # GitLab
    gitlab_base_url: str = ""
    gitlab_token: str = ""
    gitlab_groups: str = ""  # Comma-separated group paths. Empty = all accessible projects

    # Jenkins
    jenkins_base_url: Optional[str] = None
    jenkins_user: Optional[str] = None
    jenkins_api_token: Optional[str] = None

    # Claude AI
    claude_usage_api_url: Optional[str] = None
    claude_api_key: Optional[str] = None

    # Polling intervals (seconds)
    jira_poll_interval: int = 1800
    gitlab_poll_interval: int = 900
    cicd_poll_interval: int = 300
    claude_poll_interval: int = 3600
    bizvalue_poll_interval: int = 7200
    metric_compute_interval: int = 86400

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def jira_projects_list(self) -> List[str]:
        if not self.jira_projects:
            return []
        return [p.strip() for p in self.jira_projects.split(",")]

    @property
    def gitlab_groups_list(self) -> List[str]:
        if not self.gitlab_groups:
            return []
        return [g.strip() for g in self.gitlab_groups.split(",")]


settings = Settings()
