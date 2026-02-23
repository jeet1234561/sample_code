"""APScheduler setup for periodic polling of all connectors and metric computation."""

import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.connectors.jira_connector import JiraConnector
from app.connectors.cicd_connector import JenkinsCICDConnector
from app.connectors.gitlab_connector import GitLabConnector
from app.connectors.claude_connector import ClaudeAIConnector
from app.connectors.business_value_connector import BusinessValueConnector
from app.database import AsyncSessionLocal
from app.metrics.engine import MetricEngine
from app.scoring.engine import ScoringEngine
from app.alerts.engine import AlertEngine

logger = logging.getLogger("epiap.scheduler")

scheduler = AsyncIOScheduler()


async def _run_connector(connector_class):
    """Generic wrapper: creates a session, instantiates the connector, and runs it."""
    async with AsyncSessionLocal() as session:
        async with httpx.AsyncClient(timeout=60.0) as http:
            connector = connector_class(session=session, http_client=http)
            try:
                await connector.run()
                logger.info(
                    f"[{connector.connector_name}] sync completed successfully"
                )
            except Exception as e:
                logger.error(
                    f"[{connector.connector_name}] sync failed: {e}",
                    exc_info=True,
                )


async def _run_metric_engine():
    """Run the metric computation engine."""
    async with AsyncSessionLocal() as session:
        engine = MetricEngine(session=session)
        try:
            await engine.compute_all()
            logger.info("[MetricEngine] computation completed successfully")
        except Exception as e:
            logger.error(
                f"[MetricEngine] computation failed: {e}", exc_info=True
            )


async def _run_scoring_engine():
    """Run the scoring engine (Module C)."""
    async with AsyncSessionLocal() as session:
        engine = ScoringEngine(session=session)
        try:
            await engine.compute_all_scores()
            logger.info("[ScoringEngine] computation completed successfully")
        except Exception as e:
            logger.error(
                f"[ScoringEngine] computation failed: {e}", exc_info=True
            )


async def _run_alert_engine():
    """Run the alert evaluation engine (Module D)."""
    async with AsyncSessionLocal() as session:
        engine = AlertEngine(session=session)
        try:
            await engine.evaluate_all_rules()
            logger.info("[AlertEngine] evaluation completed successfully")
        except Exception as e:
            logger.error(
                f"[AlertEngine] evaluation failed: {e}", exc_info=True
            )


def register_jobs():
    """Register all polling jobs. Called once at application startup."""
    scheduler.add_job(
        _run_connector,
        IntervalTrigger(seconds=settings.jira_poll_interval),
        args=[JiraConnector],
        id="jira_poll",
        name="Jira Connector Poll",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _run_connector,
        IntervalTrigger(seconds=settings.gitlab_poll_interval),
        args=[GitLabConnector],
        id="gitlab_poll",
        name="GitLab Connector Poll",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _run_connector,
        IntervalTrigger(seconds=settings.cicd_poll_interval),
        args=[JenkinsCICDConnector],
        id="jenkins_poll",
        name="Jenkins CI/CD Poll",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _run_connector,
        IntervalTrigger(seconds=settings.claude_poll_interval),
        args=[ClaudeAIConnector],
        id="claude_poll",
        name="Claude AI Poll",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _run_connector,
        IntervalTrigger(seconds=settings.bizvalue_poll_interval),
        args=[BusinessValueConnector],
        id="bizvalue_poll",
        name="Business Value Poll",
        replace_existing=True,
        max_instances=1,
    )
    # Metric computation — daily by default, can be triggered manually
    scheduler.add_job(
        _run_metric_engine,
        IntervalTrigger(seconds=settings.metric_compute_interval),
        id="metric_compute",
        name="Daily Metric Computation",
        replace_existing=True,
        max_instances=1,
    )
    # Scoring — runs after metric computation (daily)
    scheduler.add_job(
        _run_scoring_engine,
        IntervalTrigger(seconds=settings.metric_compute_interval),
        id="scoring_compute",
        name="Daily Scoring Computation",
        replace_existing=True,
        max_instances=1,
    )
    # Alert evaluation — every 10 minutes (FRD requirement)
    scheduler.add_job(
        _run_alert_engine,
        IntervalTrigger(seconds=600),
        id="alert_evaluate",
        name="Alert Rule Evaluation (10min)",
        replace_existing=True,
        max_instances=1,
    )
