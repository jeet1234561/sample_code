"""B4: Business Metrics — Dollar Productivity.

- Dollar Productivity = SUM(feature_value x contribution_factor) per employee
"""

from datetime import datetime
from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business_value import BusinessValueTag, FeatureContribution


class BusinessMetrics:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute(
        self, employee_id: str, window_start: datetime, window_end: datetime
    ) -> List[Tuple[str, float, str, dict]]:
        results = []

        dollar = await self._dollar_productivity(employee_id)
        results.append(
            ("dollar_productivity", dollar["total_dollars"], "dollars", dollar)
        )

        return results

    async def _dollar_productivity(self, employee_id: str) -> dict:
        """Dollar Productivity = SUM(feature_dollar_value * contribution_factor)."""
        query = (
            select(
                FeatureContribution.feature_id,
                FeatureContribution.contribution_factor,
                BusinessValueTag.dollar_value,
                BusinessValueTag.feature_name,
            )
            .join(
                BusinessValueTag,
                FeatureContribution.feature_id == BusinessValueTag.feature_id,
            )
            .where(FeatureContribution.employee_id == employee_id)
        )
        result = await self.session.execute(query)
        rows = result.all()

        total = 0.0
        breakdown = []
        for row in rows:
            contribution = row.dollar_value * row.contribution_factor
            total += contribution
            breakdown.append(
                {
                    "feature_id": row.feature_id,
                    "feature_name": row.feature_name,
                    "feature_value": row.dollar_value,
                    "contribution_factor": row.contribution_factor,
                    "attributed_value": round(contribution, 2),
                }
            )

        return {
            "total_dollars": round(total, 2),
            "features_count": len(breakdown),
            "breakdown": breakdown,
        }
