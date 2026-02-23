"""B1: Delivery Performance Metrics.

- Lead Time for Changes: time between commit/PR creation and merge/deployment
- Deployment Frequency: count of successful deployments per week
- Cycle Time: time from ticket start (In Progress) to ticket completion (Done)
"""

from datetime import datetime
from typing import List, Tuple

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_event import ActivityEvent


class DeliveryMetrics:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute(
        self, employee_id: str, window_start: datetime, window_end: datetime
    ) -> List[Tuple[str, float, str, dict]]:
        """Returns list of (metric_name, value, unit, details)."""
        results = []

        lead_time = await self._lead_time(employee_id, window_start, window_end)
        results.append(("lead_time", lead_time["avg_hours"], "hours", lead_time))

        deploy_freq = await self._deployment_frequency(
            employee_id, window_start, window_end
        )
        results.append(
            ("deployment_frequency", deploy_freq["per_week"], "deploys/week", deploy_freq)
        )

        cycle_time = await self._cycle_time(employee_id, window_start, window_end)
        results.append(("cycle_time", cycle_time["avg_hours"], "hours", cycle_time))

        return results

    async def _lead_time(
        self, employee_id: str, start: datetime, end: datetime
    ) -> dict:
        """Lead Time = MR creation -> merge time (reviewTimeHours from Git events)."""
        pr_query = select(ActivityEvent).where(
            and_(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.source == "Git",
                ActivityEvent.timestamp.between(start, end),
                ActivityEvent.payload["merged"].astext == "true",
            )
        )
        result = await self.session.execute(pr_query)
        merged_prs = result.scalars().all()

        if not merged_prs:
            return {"avg_hours": 0, "sample_size": 0, "note": "no merged PRs in window"}

        lead_times = []
        for pr in merged_prs:
            review_hours = pr.payload.get("reviewTimeHours")
            if review_hours and review_hours > 0:
                lead_times.append(float(review_hours))

        if not lead_times:
            return {"avg_hours": 0, "sample_size": 0, "note": "no review time data"}

        sorted_times = sorted(lead_times)
        avg = sum(sorted_times) / len(sorted_times)
        return {
            "avg_hours": round(avg, 2),
            "median_hours": round(
                sorted_times[len(sorted_times) // 2], 2
            ),
            "p90_hours": round(
                sorted_times[int(len(sorted_times) * 0.9)], 2
            ),
            "sample_size": len(sorted_times),
        }

    async def _deployment_frequency(
        self, employee_id: str, start: datetime, end: datetime
    ) -> dict:
        """Deployment Frequency = successful deployments per week."""
        deploy_query = select(func.count()).where(
            and_(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.source == "CICD",
                ActivityEvent.timestamp.between(start, end),
                ActivityEvent.payload["buildStatus"].astext == "SUCCESS",
            )
        )
        result = await self.session.execute(deploy_query)
        total_deploys = result.scalar() or 0

        weeks = max(1, (end - start).days / 7)
        per_week = round(total_deploys / weeks, 2)

        return {
            "total_deployments": total_deploys,
            "per_week": per_week,
            "window_weeks": round(weeks, 1),
        }

    async def _cycle_time(
        self, employee_id: str, start: datetime, end: datetime
    ) -> dict:
        """Cycle Time = Jira 'In Progress' -> 'Done' delta."""
        # Get "In Progress" transitions
        in_progress_query = select(ActivityEvent).where(
            and_(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.source == "Jira",
                ActivityEvent.timestamp.between(start, end),
                ActivityEvent.payload["status_to"].astext == "In Progress",
            )
        )
        result = await self.session.execute(in_progress_query)
        started_events = {
            e.payload["issueID"]: e.timestamp
            for e in result.scalars().all()
        }

        # Get "Done" transitions
        done_query = select(ActivityEvent).where(
            and_(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.source == "Jira",
                ActivityEvent.timestamp.between(start, end),
                ActivityEvent.payload["status_to"].astext == "Done",
            )
        )
        result = await self.session.execute(done_query)
        done_events = {
            e.payload["issueID"]: e.timestamp
            for e in result.scalars().all()
        }

        cycle_times = []
        for issue_id, start_time in started_events.items():
            if issue_id in done_events:
                delta = (done_events[issue_id] - start_time).total_seconds() / 3600
                if delta > 0:
                    cycle_times.append(delta)

        avg = sum(cycle_times) / len(cycle_times) if cycle_times else 0
        return {
            "avg_hours": round(avg, 2),
            "sample_size": len(cycle_times),
            "tickets_completed": len(done_events),
        }
