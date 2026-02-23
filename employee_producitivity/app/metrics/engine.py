"""MetricEngine: orchestrates all metric computations.

Reads from activity_events, writes to metric_snapshots.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.metric_snapshot import MetricSnapshot
from app.models.base import new_uuid
from app.metrics.delivery import DeliveryMetrics
from app.metrics.quality import QualityMetrics
from app.metrics.team_experience import TeamExperienceMetrics
from app.metrics.business import BusinessMetrics

logger = logging.getLogger("epiap.metrics")


class MetricEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.delivery = DeliveryMetrics(session)
        self.quality = QualityMetrics(session)
        self.team_exp = TeamExperienceMetrics(session)
        self.business = BusinessMetrics(session)

    async def compute_all(self, window_days: int = 30):
        """Compute all metrics for all active employees over the given window."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=window_days)

        result = await self.session.execute(
            select(Employee).where(Employee.is_active == True)
        )
        employees = result.scalars().all()

        for emp in employees:
            logger.info(f"Computing metrics for {emp.employee_id}")

            metric_groups = [
                ("delivery", self.delivery),
                ("quality", self.quality),
                ("team_exp", self.team_exp),
                ("business", self.business),
            ]

            for category_name, metric_class in metric_groups:
                try:
                    metric_results = await metric_class.compute(
                        emp.employee_id, window_start, now
                    )
                    for metric_name, value, unit, details in metric_results:
                        snapshot = MetricSnapshot(
                            snapshot_id=new_uuid(),
                            employee_id=emp.employee_id,
                            metric_name=metric_name,
                            metric_category=category_name,
                            value=value,
                            unit=unit,
                            window_start=window_start,
                            window_end=now,
                            details=details,
                        )
                        self.session.add(snapshot)
                except Exception as e:
                    logger.error(
                        f"Error computing {category_name} for {emp.employee_id}: {e}",
                        exc_info=True,
                    )

        await self.session.commit()
        logger.info(
            f"Metric computation complete for {len(employees)} employees"
        )
