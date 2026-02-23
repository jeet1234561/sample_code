"""B2: Quality & Engineering Health Metrics.

- Change Failure Rate: % of releases causing an error/rollback
- MTTR: Mean Time To Recovery from a failure
- Defect Density: defects per 1000 lines of code
- Test Coverage: % from automated tests
- Rework Ratio: % of work re-opened due to defects
"""

from datetime import datetime
from typing import List, Tuple

from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_event import ActivityEvent


class QualityMetrics:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute(
        self, employee_id: str, window_start: datetime, window_end: datetime
    ) -> List[Tuple[str, float, str, dict]]:
        results = []

        cfr = await self._change_failure_rate(employee_id, window_start, window_end)
        results.append(("change_failure_rate", cfr["rate_percent"], "percentage", cfr))

        mttr = await self._mttr(employee_id, window_start, window_end)
        results.append(("mttr", mttr["avg_hours"], "hours", mttr))

        defect = await self._defect_density(employee_id, window_start, window_end)
        results.append(("defect_density", defect["per_1k_lines"], "defects/kloc", defect))

        coverage = await self._test_coverage(employee_id, window_start, window_end)
        results.append(("test_coverage", coverage["percentage"], "percentage", coverage))

        rework = await self._rework_ratio(employee_id, window_start, window_end)
        results.append(("rework_ratio", rework["ratio_percent"], "percentage", rework))

        return results

    async def _change_failure_rate(
        self, employee_id: str, start: datetime, end: datetime
    ) -> dict:
        """CFR = failed deployments / total deployments * 100."""
        total_q = select(func.count()).where(
            and_(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.source == "CICD",
                ActivityEvent.timestamp.between(start, end),
            )
        )
        failed_q = select(func.count()).where(
            and_(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.source == "CICD",
                ActivityEvent.timestamp.between(start, end),
                ActivityEvent.payload["buildStatus"].astext == "FAILURE",
            )
        )
        total = (await self.session.execute(total_q)).scalar() or 0
        failed = (await self.session.execute(failed_q)).scalar() or 0
        rate = round((failed / total * 100) if total > 0 else 0, 2)
        return {"rate_percent": rate, "failed": failed, "total": total}

    async def _mttr(
        self, employee_id: str, start: datetime, end: datetime
    ) -> dict:
        """MTTR = average time between a FAILURE and the next SUCCESS for the same job."""
        events_q = (
            select(ActivityEvent)
            .where(
                and_(
                    ActivityEvent.employee_id == employee_id,
                    ActivityEvent.source == "CICD",
                    ActivityEvent.timestamp.between(start, end),
                )
            )
            .order_by(ActivityEvent.timestamp)
        )
        result = await self.session.execute(events_q)
        events = result.scalars().all()

        recovery_times = []
        last_failure = {}  # pipeline_id -> failure_timestamp
        for event in events:
            pid = event.payload.get("jobName") or event.payload.get(
                "pipelineID", ""
            )
            status = event.payload.get("buildStatus", "")
            if status == "FAILURE":
                last_failure[pid] = event.timestamp
            elif status == "SUCCESS" and pid in last_failure:
                delta_hours = (
                    event.timestamp - last_failure[pid]
                ).total_seconds() / 3600
                recovery_times.append(delta_hours)
                del last_failure[pid]

        avg = (
            sum(recovery_times) / len(recovery_times) if recovery_times else 0
        )
        return {"avg_hours": round(avg, 2), "incidents": len(recovery_times)}

    async def _defect_density(
        self, employee_id: str, start: datetime, end: datetime
    ) -> dict:
        """Defect Density = bug-type Jira issues / total lines changed * 1000."""
        # Count bug tickets
        bug_q = select(func.count()).where(
            and_(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.source == "Jira",
                ActivityEvent.timestamp.between(start, end),
                ActivityEvent.payload["type"].astext.in_(
                    ["Bug", "Defect", "bug"]
                ),
            )
        )
        bugs = (await self.session.execute(bug_q)).scalar() or 0

        # Sum lines changed from Git commits using raw SQL for JSONB int cast
        lines_q = text("""
            SELECT COALESCE(
                SUM(
                    (payload->>'additions')::int +
                    (payload->>'deletions')::int
                ), 0
            )
            FROM activity_events
            WHERE employee_id = :eid
              AND source = 'Git'
              AND "timestamp" BETWEEN :start AND :end
              AND payload ? 'additions'
        """)
        result = await self.session.execute(
            lines_q, {"eid": employee_id, "start": start, "end": end}
        )
        total_lines = result.scalar() or 0

        per_1k = round((bugs / max(total_lines, 1)) * 1000, 2)
        return {
            "per_1k_lines": per_1k,
            "bugs": bugs,
            "total_lines": total_lines,
        }

    async def _test_coverage(
        self, employee_id: str, start: datetime, end: datetime
    ) -> dict:
        """Test Coverage: extracted from CI/CD pipeline payload if available."""
        cov_q = (
            select(ActivityEvent)
            .where(
                and_(
                    ActivityEvent.employee_id == employee_id,
                    ActivityEvent.source == "CICD",
                    ActivityEvent.timestamp.between(start, end),
                    ActivityEvent.payload.has_key("testCoverage"),
                )
            )
            .order_by(ActivityEvent.timestamp.desc())
            .limit(1)
        )
        result = await self.session.execute(cov_q)
        event = result.scalar_one_or_none()

        if event and event.payload.get("testCoverage") is not None:
            return {
                "percentage": float(event.payload["testCoverage"]),
                "source": "ci_report",
            }
        return {"percentage": 0, "source": "not_available"}

    async def _rework_ratio(
        self, employee_id: str, start: datetime, end: datetime
    ) -> dict:
        """Rework Ratio = tickets reopened / total completed * 100."""
        reopen_q = select(func.count()).where(
            and_(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.source == "Jira",
                ActivityEvent.timestamp.between(start, end),
                ActivityEvent.payload["status_to"].astext == "In Progress",
                ActivityEvent.payload["status_from"].astext.in_(
                    ["Done", "In Review", "Closed"]
                ),
            )
        )
        reopened = (await self.session.execute(reopen_q)).scalar() or 0

        done_q = select(func.count()).where(
            and_(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.source == "Jira",
                ActivityEvent.timestamp.between(start, end),
                ActivityEvent.payload["status_to"].astext == "Done",
            )
        )
        done = (await self.session.execute(done_q)).scalar() or 0

        ratio = round((reopened / max(done, 1)) * 100, 2)
        return {"ratio_percent": ratio, "reopened": reopened, "completed": done}
