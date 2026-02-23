"""B3: Team Experience & Collaboration Metrics.

- Code Review Turnaround Time: PR creation to final review/merge
- WIP Count: tasks currently in active state
- Developer Experience Index (DXI): composite of flow and interruptions
"""

from datetime import datetime
from typing import List, Tuple

from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_event import ActivityEvent


class TeamExperienceMetrics:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute(
        self, employee_id: str, window_start: datetime, window_end: datetime
    ) -> List[Tuple[str, float, str, dict]]:
        results = []

        review = await self._code_review_turnaround(
            employee_id, window_start, window_end
        )
        results.append(
            ("code_review_turnaround", review["avg_hours"], "hours", review)
        )

        wip = await self._wip_count(employee_id, window_end)
        results.append(("wip_count", wip["count"], "count", wip))

        dxi = await self._developer_experience_index(
            employee_id, window_start, window_end
        )
        results.append(("dxi", dxi["score"], "score", dxi))

        return results

    async def _code_review_turnaround(
        self, employee_id: str, start: datetime, end: datetime
    ) -> dict:
        """Code Review Turnaround = avg reviewTimeHours from merged MRs."""
        pr_q = select(ActivityEvent).where(
            and_(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.source == "Git",
                ActivityEvent.timestamp.between(start, end),
                ActivityEvent.payload.has_key("MRID"),
                ActivityEvent.payload["merged"].astext == "true",
            )
        )
        result = await self.session.execute(pr_q)
        prs = result.scalars().all()

        review_times = [
            float(pr.payload["reviewTimeHours"])
            for pr in prs
            if pr.payload.get("reviewTimeHours") is not None
            and pr.payload["reviewTimeHours"] > 0
        ]

        avg = sum(review_times) / len(review_times) if review_times else 0
        return {
            "avg_hours": round(avg, 2),
            "sample_size": len(review_times),
            "max_hours": round(max(review_times), 2) if review_times else 0,
        }

    async def _wip_count(self, employee_id: str, as_of: datetime) -> dict:
        """WIP = count of Jira issues currently in 'In Progress' state."""
        wip_q = select(
            func.count(func.distinct(ActivityEvent.payload["issueID"].astext))
        ).where(
            and_(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.source == "Jira",
                ActivityEvent.payload["status"].astext == "In Progress",
            )
        )
        result = await self.session.execute(wip_q)
        count = result.scalar() or 0
        return {"count": count}

    async def _developer_experience_index(
        self, employee_id: str, start: datetime, end: datetime
    ) -> dict:
        """DXI = 100 - (context_switch_penalty + long_review_penalty + high_wip_penalty).

        Penalties:
        - context_switch: days with events across 3+ sources * 2 (max 30)
        - long_review: avg review turnaround > 24h adds 15
        - high_wip: WIP > 5 adds 10 per excess item (max 30)
        """
        # Context switching: days with 3+ different sources
        switch_q = text("""
            SELECT day, source_count FROM (
                SELECT date_trunc('day', "timestamp") AS day,
                       COUNT(DISTINCT source) AS source_count
                FROM activity_events
                WHERE employee_id = :eid
                  AND "timestamp" BETWEEN :start AND :end_ts
                GROUP BY date_trunc('day', "timestamp")
            ) sub
        """)
        result = await self.session.execute(
            switch_q, {"eid": employee_id, "start": start, "end_ts": end}
        )
        rows = result.all()
        high_switch_days = sum(1 for row in rows if row.source_count >= 3)
        context_penalty = min(high_switch_days * 2, 30)

        # Review turnaround penalty
        review_data = await self._code_review_turnaround(
            employee_id, start, end
        )
        review_penalty = 15 if review_data["avg_hours"] > 24 else 0

        # WIP penalty
        wip_data = await self._wip_count(employee_id, end)
        excess_wip = max(0, wip_data["count"] - 5)
        wip_penalty = min(excess_wip * 10, 30)

        score = max(0, 100 - context_penalty - review_penalty - wip_penalty)
        return {
            "score": round(score, 1),
            "context_switch_penalty": context_penalty,
            "review_penalty": review_penalty,
            "wip_penalty": wip_penalty,
            "high_switch_days": high_switch_days,
        }
