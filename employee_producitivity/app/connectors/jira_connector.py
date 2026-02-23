"""A1: Jira Connector — Fetches task/ticket activity from Jira REST API v3."""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from dateutil.parser import isoparse
from sqlalchemy import text

from app.connectors.base import BaseConnector
from app.models.activity_event import ActivityEvent
from app.models.base import new_uuid
from app.config import settings
from app.utils.retry import async_retry

logger = logging.getLogger("epiap.jira")


class JiraConnector(BaseConnector):
    connector_name = "jira"

    def __init__(self, session, http_client):
        super().__init__(session, http_client)
        self._seen_assignees: Dict[str, dict] = {}

    @async_retry(max_retries=3, backoff_base=2.0)
    async def fetch_raw(self, since: Optional[datetime] = None) -> List[dict]:
        """Fetch issues updated since the last sync using JQL search.

        Uses /rest/api/3/search/jql with token-based pagination.
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=90)

        project_filter = ""
        if settings.jira_projects_list:
            keys = ",".join(settings.jira_projects_list)
            project_filter = f' AND project IN ({keys})'

        jql = f'updated >= "{since.strftime("%Y-%m-%d %H:%M")}"{project_filter} ORDER BY updated ASC'
        all_issues = []
        next_page_token = None
        max_results = 100

        while True:
            params = {
                "jql": jql,
                "maxResults": max_results,
                "fields": (
                    "summary,status,issuetype,assignee,created,updated,"
                    "resolutiondate,customfield_10016,changelog,project"
                ),
                "expand": "changelog",
            }
            if next_page_token:
                params["nextPageToken"] = next_page_token

            response = await self.http.get(
                f"{settings.jira_base_url}/rest/api/3/search/jql",
                params=params,
                auth=(settings.jira_user_email, settings.jira_api_token),
            )
            response.raise_for_status()
            data = response.json()
            all_issues.extend(data.get("issues", []))

            if data.get("isLast", True):
                break
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

        return all_issues

    def normalize(self, raw_records: List[dict]) -> List[ActivityEvent]:
        events = []
        for issue in raw_records:
            fields = issue["fields"]
            assignee = fields.get("assignee")
            employee_id = self._resolve_employee_id(assignee)

            # Track assignee details for auto-population
            if assignee and assignee.get("accountId"):
                self._seen_assignees[assignee["accountId"]] = {
                    "display_name": assignee.get("displayName", "Unknown"),
                    "email": assignee.get("emailAddress", ""),
                    "project": fields.get("project", {}).get("name", ""),
                }

            # One event per status transition from changelog
            for history in issue.get("changelog", {}).get("histories", []):
                for item in history.get("items", []):
                    if item["field"] == "status":
                        events.append(
                            ActivityEvent(
                                event_id=new_uuid(),
                                employee_id=employee_id,
                                source="Jira",
                                timestamp=isoparse(history["created"]),
                                payload={
                                    "issueID": issue["key"],
                                    "type": fields["issuetype"]["name"],
                                    "status_from": item["fromString"],
                                    "status_to": item["toString"],
                                    "storyPoints": fields.get("customfield_10016"),
                                    "assignee": employee_id,
                                    "summary": fields.get("summary", "")[:200],
                                },
                                raw_source_id=f"jira-{issue['key']}-{history['id']}-status",
                            )
                        )

            # Snapshot event for the issue's current state
            events.append(
                ActivityEvent(
                    event_id=new_uuid(),
                    employee_id=employee_id,
                    source="Jira",
                    timestamp=isoparse(fields["updated"]),
                    payload={
                        "issueID": issue["key"],
                        "type": fields["issuetype"]["name"],
                        "status": fields["status"]["name"],
                        "storyPoints": fields.get("customfield_10016"),
                        "assignee": employee_id,
                        "created": fields.get("created"),
                        "resolutiondate": fields.get("resolutiondate"),
                    },
                    raw_source_id=f"jira-{issue['key']}-snapshot-{fields['updated']}",
                )
            )

        return events

    async def run(self):
        """Override run to auto-populate employees after ingestion."""
        await super().run()
        await self._auto_populate_employees()

    async def _auto_populate_employees(self):
        """Create employee records for any new Jira users seen during this poll."""
        if not self._seen_assignees:
            return

        for account_id, info in self._seen_assignees.items():
            employee_id = f"jira-{account_id}"
            await self.session.execute(
                text(
                    "INSERT INTO employees (employee_id, display_name, email, role, team, jira_account_id) "
                    "VALUES (:eid, :name, :email, 'Developer', :team, :jira_id) "
                    "ON CONFLICT (employee_id) DO UPDATE SET "
                    "display_name = EXCLUDED.display_name, "
                    "email = CASE WHEN EXCLUDED.email != '' THEN EXCLUDED.email ELSE employees.email END"
                ),
                {
                    "eid": employee_id,
                    "name": info["display_name"],
                    "email": info["email"] or f"{account_id}@unknown",
                    "team": info["project"] or "Engineering",
                    "jira_id": account_id,
                },
            )
        await self.session.commit()
        logger.info(f"Auto-populated {len(self._seen_assignees)} employee records")

    @staticmethod
    def _resolve_employee_id(assignee_data: Optional[dict]) -> str:
        if not assignee_data:
            return "unassigned"
        account_id = assignee_data.get("accountId", "unknown")
        return f"jira-{account_id}"
