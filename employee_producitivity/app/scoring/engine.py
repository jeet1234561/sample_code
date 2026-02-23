"""Module C — Scoring Engine.

Combines computed metrics (from Module B) into meaningful
employee sub-scores and an overall score.

Score Formulas (from FRD):
  DeliveryScore     = f(DeploymentFreq, LeadTime, CycleTime)
  QualityScore      = f(ChangeFailureRate, MTTR, TestCoverage)
  TeamExpScore      = f(CodeReviewTurnaround, DXI, WIP)
  BusinessValueScore = DollarProductivity normalized
  OverallScore      = 0.25*Delivery + 0.25*Quality + 0.15*TeamExp + 0.35*Business
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.metric_snapshot import MetricSnapshot
from app.models.score import EmployeeScore
from app.models.base import new_uuid
from app.scoring.formulas import (
    compute_sub_score,
    compute_overall_score,
    OVERALL_WEIGHTS,
)

logger = logging.getLogger("epiap.scoring")


class ScoringEngine:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute_all_scores(self, window_days: int = 30):
        """Compute scores for all active employees."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=window_days)

        result = await self.session.execute(
            select(Employee).where(Employee.is_active == True)
        )
        employees = result.scalars().all()

        scores_created = 0
        for emp in employees:
            try:
                score = await self.compute_employee_score(
                    emp.employee_id, window_start, now
                )
                if score:
                    self.session.add(score)
                    scores_created += 1
            except Exception as e:
                logger.error(
                    f"Error scoring {emp.employee_id}: {e}", exc_info=True
                )

        await self.session.commit()
        logger.info(f"Scoring complete: {scores_created} scores computed")

    async def compute_employee_score(
        self,
        employee_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> Optional[EmployeeScore]:
        """Compute all sub-scores and overall score for one employee."""
        # Fetch the latest metric snapshots for this employee within the window
        metrics = await self._get_latest_metrics(
            employee_id, window_start, window_end
        )

        if not metrics:
            logger.warning(
                f"No metrics found for {employee_id}, skipping scoring"
            )
            return None

        # Group metric values by category
        category_metrics: Dict[str, Dict[str, float]] = {
            "delivery": {},
            "quality": {},
            "team_exp": {},
            "business": {},
        }
        for m in metrics:
            cat = m.metric_category
            if cat in category_metrics:
                category_metrics[cat][m.metric_name] = m.value

        # Compute sub-scores
        delivery_score, delivery_breakdown = compute_sub_score(
            "delivery", category_metrics["delivery"]
        )
        quality_score, quality_breakdown = compute_sub_score(
            "quality", category_metrics["quality"]
        )
        team_exp_score, team_exp_breakdown = compute_sub_score(
            "team_exp", category_metrics["team_exp"]
        )
        business_score, business_breakdown = compute_sub_score(
            "business", category_metrics["business"]
        )

        # Compute overall
        sub_scores = {
            "delivery": delivery_score,
            "quality": quality_score,
            "team_exp": team_exp_score,
            "business": business_score,
        }
        overall = compute_overall_score(sub_scores)

        logger.info(
            f"[{employee_id}] Delivery={delivery_score} Quality={quality_score} "
            f"TeamExp={team_exp_score} Business={business_score} Overall={overall}"
        )

        return EmployeeScore(
            score_id=new_uuid(),
            employee_id=employee_id,
            delivery_score=delivery_score,
            quality_score=quality_score,
            team_exp_score=team_exp_score,
            business_value_score=business_score,
            overall_score=overall,
            weights=OVERALL_WEIGHTS,
            details={
                "sub_scores": sub_scores,
                "delivery_breakdown": delivery_breakdown,
                "quality_breakdown": quality_breakdown,
                "team_exp_breakdown": team_exp_breakdown,
                "business_breakdown": business_breakdown,
                "raw_metrics": {
                    m.metric_name: m.value for m in metrics
                },
            },
            window_start=window_start,
            window_end=window_end,
        )

    async def _get_latest_metrics(
        self,
        employee_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> List[MetricSnapshot]:
        """Get the most recent metric snapshot per metric_name for an employee.

        Uses a DISTINCT ON query to pick the latest computed_at per metric.
        """
        # Subquery: latest computed_at per metric_name
        subq = (
            select(
                MetricSnapshot.metric_name,
                func.max(MetricSnapshot.computed_at).label("latest_at"),
            )
            .where(
                and_(
                    MetricSnapshot.employee_id == employee_id,
                    MetricSnapshot.computed_at.between(window_start, window_end),
                )
            )
            .group_by(MetricSnapshot.metric_name)
            .subquery()
        )

        query = (
            select(MetricSnapshot)
            .join(
                subq,
                and_(
                    MetricSnapshot.metric_name == subq.c.metric_name,
                    MetricSnapshot.computed_at == subq.c.latest_at,
                    MetricSnapshot.employee_id == employee_id,
                ),
            )
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_employee_score(
        self, employee_id: str
    ) -> Optional[EmployeeScore]:
        """Get the latest score for a specific employee."""
        query = (
            select(EmployeeScore)
            .where(EmployeeScore.employee_id == employee_id)
            .order_by(EmployeeScore.computed_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_latest_scores(self) -> List[EmployeeScore]:
        """Get the latest score for every employee (leaderboard)."""
        subq = (
            select(
                EmployeeScore.employee_id,
                func.max(EmployeeScore.computed_at).label("latest_at"),
            )
            .group_by(EmployeeScore.employee_id)
            .subquery()
        )

        query = (
            select(EmployeeScore)
            .join(
                subq,
                and_(
                    EmployeeScore.employee_id == subq.c.employee_id,
                    EmployeeScore.computed_at == subq.c.latest_at,
                ),
            )
            .order_by(EmployeeScore.overall_score.desc())
        )

        result = await self.session.execute(query)
        return result.scalars().all()
