"""A3: CI/CD Pipeline Connector — Jenkins."""

from datetime import datetime, timezone
from typing import List, Optional

from app.connectors.base import BaseConnector
from app.models.activity_event import ActivityEvent
from app.models.base import new_uuid
from app.config import settings
from app.utils.retry import async_retry


class JenkinsCICDConnector(BaseConnector):
    connector_name = "cicd_jenkins"

    @async_retry(max_retries=3, backoff_base=2.0)
    async def fetch_raw(self, since: Optional[datetime] = None) -> List[dict]:
        """Fetch recent Jenkins builds via JSON API."""
        if not settings.jenkins_base_url:
            return []

        response = await self.http.get(
            f"{settings.jenkins_base_url}/api/json",
            params={
                "tree": (
                    "jobs[name,builds[number,result,timestamp,duration,"
                    "actions[causes[userId]]]{0,50}]"
                )
            },
            auth=(settings.jenkins_user, settings.jenkins_api_token),
        )
        response.raise_for_status()
        data = response.json()

        builds = []
        since_ts = int(since.timestamp() * 1000) if since else 0
        for job in data.get("jobs", []):
            for build in job.get("builds", []):
                if build.get("timestamp", 0) >= since_ts:
                    build["_job_name"] = job["name"]
                    builds.append(build)
        return builds

    def normalize(self, raw_records: List[dict]) -> List[ActivityEvent]:
        events = []
        for build in raw_records:
            user_id = "unknown"
            for action in build.get("actions", []):
                for cause in action.get("causes", []):
                    if "userId" in cause:
                        user_id = cause["userId"]

            events.append(
                ActivityEvent(
                    event_id=new_uuid(),
                    employee_id=f"jenkins-{user_id}",
                    source="CICD",
                    timestamp=datetime.fromtimestamp(
                        build["timestamp"] / 1000, tz=timezone.utc
                    ),
                    payload={
                        "pipelineID": f"{build['_job_name']}#{build['number']}",
                        "jobName": build["_job_name"],
                        "buildNumber": build["number"],
                        "buildStatus": build.get("result", "UNKNOWN"),
                        "durationMs": build.get("duration", 0),
                        "durationMinutes": round(
                            build.get("duration", 0) / 60000, 2
                        ),
                        "triggeredBy": user_id,
                    },
                    raw_source_id=f"jenkins-{build['_job_name']}-{build['number']}",
                )
            )
        return events
