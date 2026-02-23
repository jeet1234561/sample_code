"""A2b: GitLab Connector — Fetches commits, MRs, and pipelines from GitLab API v4."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from dateutil.parser import isoparse
from sqlalchemy import text

from app.connectors.base import BaseConnector
from app.models.activity_event import ActivityEvent
from app.models.base import new_uuid
from app.config import settings
from app.utils.retry import async_retry

logger = logging.getLogger("epiap.gitlab")


class GitLabConnector(BaseConnector):
    connector_name = "gitlab"

    def __init__(self, session, http_client):
        super().__init__(session, http_client)
        self._seen_users: Dict[str, dict] = {}
        self._email_to_eid: Dict[str, str] = {}  # email -> existing employee_id

    @property
    def _headers(self):
        return {"PRIVATE-TOKEN": settings.gitlab_token}

    @property
    def _base(self):
        return settings.gitlab_base_url.rstrip("/")

    @async_retry(max_retries=3, backoff_base=2.0)
    async def fetch_raw(self, since: Optional[datetime] = None) -> List[dict]:
        """Fetch commits, merge requests, and pipelines from all accessible projects."""
        if not settings.gitlab_base_url or not settings.gitlab_token:
            return []

        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=90)

        since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Get all projects
        projects = await self._get_projects()
        logger.info(f"Fetching data from {len(projects)} GitLab projects")

        all_records = []
        for proj in projects:
            pid = proj["id"]
            pname = proj["path_with_namespace"]

            # Fetch commits
            commits = await self._paginate(
                f"{self._base}/api/v4/projects/{pid}/repository/commits",
                params={"since": since_iso, "per_page": 100},
            )
            for c in commits:
                c["_record_type"] = "commit"
                c["_project"] = pname
                c["_project_id"] = pid

            # Fetch merge requests
            mrs = await self._paginate(
                f"{self._base}/api/v4/projects/{pid}/merge_requests",
                params={
                    "state": "all",
                    "updated_after": since_iso,
                    "per_page": 100,
                    "order_by": "updated_at",
                    "sort": "desc",
                },
            )
            for mr in mrs:
                mr["_record_type"] = "merge_request"
                mr["_project"] = pname
                mr["_project_id"] = pid

            # Fetch pipelines
            pipelines = await self._paginate(
                f"{self._base}/api/v4/projects/{pid}/pipelines",
                params={
                    "updated_after": since_iso,
                    "per_page": 100,
                    "order_by": "updated_at",
                    "sort": "desc",
                },
            )
            for pl in pipelines:
                pl["_record_type"] = "pipeline"
                pl["_project"] = pname
                pl["_project_id"] = pid

            all_records.extend(commits)
            all_records.extend(mrs)
            all_records.extend(pipelines)

        return all_records

    async def _get_projects(self) -> List[dict]:
        """Get all accessible projects, optionally filtered by groups."""
        if settings.gitlab_groups_list:
            projects = []
            for group in settings.gitlab_groups_list:
                group_projects = await self._paginate(
                    f"{self._base}/api/v4/groups/{group}/projects",
                    params={"per_page": 100, "include_subgroups": True},
                )
                projects.extend(group_projects)
            return projects
        else:
            return await self._paginate(
                f"{self._base}/api/v4/projects",
                params={"membership": True, "per_page": 100, "order_by": "last_activity_at"},
            )

    async def _paginate(self, url: str, params: dict) -> List[dict]:
        """Handle GitLab page-based pagination."""
        results = []
        page = 1
        while True:
            p = {**params, "page": page}
            resp = await self.http.get(url, params=p, headers=self._headers)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            results.extend(data)
            # Check if there are more pages
            total_pages = int(resp.headers.get("x-total-pages", 1))
            if page >= total_pages:
                break
            page += 1
        return results

    def normalize(self, raw_records: List[dict]) -> List[ActivityEvent]:
        events = []
        for record in raw_records:
            rtype = record["_record_type"]
            if rtype == "commit":
                event = self._normalize_commit(record)
            elif rtype == "merge_request":
                event = self._normalize_mr(record)
            elif rtype == "pipeline":
                event = self._normalize_pipeline(record)
            else:
                continue
            if event:
                events.append(event)
        return events

    def _normalize_commit(self, raw: dict) -> Optional[ActivityEvent]:
        author_email = raw.get("author_email", "")
        author_name = raw.get("author_name", "unknown")

        # Track user for auto-population
        if author_email:
            self._seen_users[author_email] = {"name": author_name, "email": author_email}

        try:
            ts = isoparse(raw.get("created_at", raw.get("committed_date", "")))
        except (ValueError, TypeError):
            return None

        return ActivityEvent(
            event_id=new_uuid(),
            employee_id=self._resolve_employee_id(author_email),
            source="Git",
            timestamp=ts,
            payload={
                "commitID": raw["short_id"],
                "full_sha": raw["id"],
                "message": (raw.get("message") or "")[:200],
                "repo": raw["_project"],
                "filesChanged": len(raw.get("stats", {}).get("files", [])) if isinstance(raw.get("stats"), dict) else 0,
                "additions": raw.get("stats", {}).get("additions", 0) if isinstance(raw.get("stats"), dict) else 0,
                "deletions": raw.get("stats", {}).get("deletions", 0) if isinstance(raw.get("stats"), dict) else 0,
                "platform": "gitlab",
            },
            raw_source_id=f"gl-commit-{raw['id']}",
        )

    def _normalize_mr(self, raw: dict) -> Optional[ActivityEvent]:
        author = raw.get("author", {})
        author_email = author.get("email", "") or ""
        author_username = author.get("username", "unknown")

        if not author_email and author_username:
            author_email = f"{author_username}@varaisys.com"

        if author_email:
            self._seen_users[author_email] = {
                "name": author.get("name", author_username),
                "email": author_email,
            }

        try:
            ts = isoparse(raw.get("updated_at", ""))
        except (ValueError, TypeError):
            return None

        # Calculate review time (created → merged)
        review_time_hours = None
        if raw.get("merged_at") and raw.get("created_at"):
            try:
                created = isoparse(raw["created_at"])
                merged = isoparse(raw["merged_at"])
                review_time_hours = round((merged - created).total_seconds() / 3600, 2)
            except (ValueError, TypeError):
                pass

        return ActivityEvent(
            event_id=new_uuid(),
            employee_id=self._resolve_employee_id(author_email),
            source="Git",
            timestamp=ts,
            payload={
                "MRID": f"MR-{raw['iid']}",
                "repo": raw["_project"],
                "title": (raw.get("title") or "")[:200],
                "state": raw.get("state", ""),
                "merged": raw.get("state") == "merged",
                "reviewTime": f"{review_time_hours}h" if review_time_hours else None,
                "reviewTimeHours": review_time_hours,
                "additions": raw.get("changes_count"),
                "platform": "gitlab",
            },
            raw_source_id=f"gl-mr-{raw['_project_id']}-{raw['iid']}-{raw.get('updated_at', '')}",
        )

    def _normalize_pipeline(self, raw: dict) -> Optional[ActivityEvent]:
        user = raw.get("user", {}) or {}
        username = user.get("username", "unknown")
        user_email = f"{username}@varaisys.com" if username != "unknown" else ""

        try:
            ts = isoparse(raw.get("updated_at", raw.get("created_at", "")))
        except (ValueError, TypeError):
            return None

        status = raw.get("status", "unknown")
        build_status = {
            "success": "SUCCESS",
            "failed": "FAILURE",
            "canceled": "CANCELED",
            "running": "RUNNING",
            "pending": "PENDING",
        }.get(status, status.upper())

        # Calculate duration
        duration_seconds = raw.get("duration")

        return ActivityEvent(
            event_id=new_uuid(),
            employee_id=self._resolve_employee_id(user_email),
            source="CICD",
            timestamp=ts,
            payload={
                "pipelineID": f"gl-pipeline-{raw['_project_id']}-{raw['id']}",
                "repo": raw["_project"],
                "ref": raw.get("ref", ""),
                "buildStatus": build_status,
                "durationSeconds": duration_seconds,
                "durationMinutes": round(duration_seconds / 60, 2) if duration_seconds else None,
                "triggeredBy": username,
                "platform": "gitlab",
            },
            raw_source_id=f"gl-pipeline-{raw['_project_id']}-{raw['id']}-{raw.get('updated_at', '')}",
        )

    async def _build_email_map(self):
        """Build mapping of email -> existing employee_id from employees table."""
        result = await self.session.execute(
            text("SELECT employee_id, email FROM employees WHERE email IS NOT NULL")
        )
        for row in result.fetchall():
            self._email_to_eid[row.email.lower()] = row.employee_id

    def _resolve_employee_id(self, email: str) -> str:
        """Return existing employee_id if email matches, else gl-{email}."""
        if not email:
            return "unknown"
        existing = self._email_to_eid.get(email.lower())
        if existing:
            return existing
        return f"gl-{email}"

    async def run(self):
        """Override run to resolve identities and auto-populate employees after ingestion."""
        await self._build_email_map()
        await super().run()
        await self._auto_populate_employees()

    async def _auto_populate_employees(self):
        """Create employee records for any new GitLab users seen during this poll."""
        if not self._seen_users:
            return

        for email, info in self._seen_users.items():
            if "@noreply" in email or not email:
                continue
            employee_id = f"gl-{email}"
            username = email.split("@")[0] if "@" in email else email
            await self.session.execute(
                text(
                    "INSERT INTO employees (employee_id, display_name, email, role, team, gitlab_username) "
                    "VALUES (:eid, :name, :email, 'Developer', 'Engineering', :gl_user) "
                    "ON CONFLICT DO NOTHING"
                ),
                {
                    "eid": employee_id,
                    "name": info["name"],
                    "email": email,
                    "gl_user": username,
                },
            )
        await self.session.commit()
        logger.info(f"Auto-populated {len(self._seen_users)} GitLab employee records")
