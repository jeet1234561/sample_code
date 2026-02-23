"""Module D2 — Alert Evaluation Engine.

Evaluates all active rules every cycle (default: 10 minutes).
For each breach, generates one AlertRecord.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertRule, AlertRecord
from app.models.metric_snapshot import MetricSnapshot
from app.models.employee import Employee
from app.models.base import new_uuid

logger = logging.getLogger("epiap.alerts")

# Operator mapping for threshold comparison
OPERATORS = {
    ">": lambda val, thresh: val > thresh,
    "<": lambda val, thresh: val < thresh,
    ">=": lambda val, thresh: val >= thresh,
    "<=": lambda val, thresh: val <= thresh,
    "==": lambda val, thresh: val == thresh,
}


class AlertEngine:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate_all_rules(self):
        """Evaluate all active rules against latest metrics.

        For each breach found, create an AlertRecord if one doesn't already
        exist (active) for the same rule + employee + metric.
        """
        # Get all active rules
        result = await self.session.execute(
            select(AlertRule).where(AlertRule.is_active == True)
        )
        rules = result.scalars().all()

        if not rules:
            logger.info("No active alert rules to evaluate")
            return

        # Get all active employees
        emp_result = await self.session.execute(
            select(Employee).where(Employee.is_active == True)
        )
        employees = emp_result.scalars().all()

        alerts_fired = 0
        for rule in rules:
            for emp in employees:
                breached = await self._evaluate_rule_for_employee(rule, emp)
                if breached:
                    alerts_fired += 1

        await self.session.commit()
        logger.info(
            f"Alert evaluation complete: {len(rules)} rules x {len(employees)} employees, "
            f"{alerts_fired} new alerts fired"
        )

    async def _evaluate_rule_for_employee(
        self, rule: AlertRule, employee: Employee
    ) -> bool:
        """Check if a rule is breached for a specific employee.

        Returns True if a new alert was created.
        """
        # Get the latest metric value for this metric + employee
        latest_metric = await self._get_latest_metric(
            employee.employee_id, rule.metric_name
        )
        if latest_metric is None:
            return False

        # Check if the threshold is breached
        op_fn = OPERATORS.get(rule.operator)
        if not op_fn:
            logger.warning(f"Unknown operator '{rule.operator}' in rule {rule.rule_id}")
            return False

        if not op_fn(latest_metric.value, rule.threshold):
            # Not breached — auto-resolve any existing active alert for this rule+employee
            await self._auto_resolve(rule.rule_id, employee.employee_id)
            return False

        # Breached — check if an active alert already exists (avoid duplicates)
        existing = await self._find_active_alert(
            rule.rule_id, employee.employee_id
        )
        if existing:
            return False  # Already alerted, don't duplicate

        # Create new alert
        message = self._generate_message(rule, employee, latest_metric.value)
        alert = AlertRecord(
            alert_id=new_uuid(),
            rule_id=rule.rule_id,
            metric_name=rule.metric_name,
            metric_value=latest_metric.value,
            threshold=rule.threshold,
            operator=rule.operator,
            employee_id=employee.employee_id,
            team=employee.team,
            priority=rule.priority,
            status="active",
            targets=rule.targets,
            message=message,
            details={
                "rule_description": rule.description,
                "metric_unit": latest_metric.unit,
                "window_start": latest_metric.window_start.isoformat()
                if latest_metric.window_start
                else None,
                "window_end": latest_metric.window_end.isoformat()
                if latest_metric.window_end
                else None,
                "employee_name": employee.display_name,
                "employee_team": employee.team,
            },
        )
        self.session.add(alert)
        logger.info(
            f"ALERT FIRED: [{rule.priority.upper()}] {rule.metric_name} "
            f"{rule.operator} {rule.threshold} for {employee.display_name} "
            f"(actual: {latest_metric.value})"
        )
        return True

    async def _get_latest_metric(
        self, employee_id: str, metric_name: str
    ) -> Optional[MetricSnapshot]:
        """Get the most recent metric snapshot for an employee+metric."""
        query = (
            select(MetricSnapshot)
            .where(
                and_(
                    MetricSnapshot.employee_id == employee_id,
                    MetricSnapshot.metric_name == metric_name,
                )
            )
            .order_by(MetricSnapshot.computed_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _find_active_alert(
        self, rule_id: str, employee_id: str
    ) -> Optional[AlertRecord]:
        """Check if there's already an active alert for this rule+employee."""
        query = select(AlertRecord).where(
            and_(
                AlertRecord.rule_id == rule_id,
                AlertRecord.employee_id == employee_id,
                AlertRecord.status == "active",
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _auto_resolve(self, rule_id: str, employee_id: str):
        """Auto-resolve active alerts when the metric goes back to normal."""
        query = select(AlertRecord).where(
            and_(
                AlertRecord.rule_id == rule_id,
                AlertRecord.employee_id == employee_id,
                AlertRecord.status == "active",
            )
        )
        result = await self.session.execute(query)
        active_alerts = result.scalars().all()
        now = datetime.now(timezone.utc)
        for alert in active_alerts:
            alert.status = "resolved"
            alert.resolved_at = now
            logger.info(
                f"AUTO-RESOLVED: {alert.metric_name} alert for {employee_id}"
            )

    @staticmethod
    def _generate_message(
        rule: AlertRule, employee: Employee, actual_value: float
    ) -> str:
        """Generate a human-readable alert message."""
        return (
            f"{rule.metric_name} is {actual_value} "
            f"(threshold: {rule.operator} {rule.threshold}) "
            f"for {employee.display_name} ({employee.team} Team). "
            f"Priority: {rule.priority}."
        )
