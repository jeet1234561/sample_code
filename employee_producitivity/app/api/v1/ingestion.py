from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.models.connector_state import ConnectorState
from app.models.activity_event import ActivityEvent
from app.schemas.connectors import ConnectorStatusResponse
from app.schemas.activity_event import ActivityEventResponse
from app.connectors.jira_connector import JiraConnector
from app.connectors.cicd_connector import JenkinsCICDConnector
from app.connectors.gitlab_connector import GitLabConnector
from app.connectors.claude_connector import ClaudeAIConnector
from app.connectors.business_value_connector import BusinessValueConnector

router = APIRouter()

# Map connector names to classes
CONNECTOR_MAP = {
    "jira": JiraConnector,
    "gitlab": GitLabConnector,
    "cicd_jenkins": JenkinsCICDConnector,
    "claude_ai": ClaudeAIConnector,
    "business_value": BusinessValueConnector,
}


@router.get("/status", response_model=List[ConnectorStatusResponse])
async def get_ingestion_status(db: AsyncSession = Depends(get_db)):
    """Returns the current status of all connectors."""
    result = await db.execute(select(ConnectorState))
    states = result.scalars().all()
    return [
        ConnectorStatusResponse(
            source=s.connector_name,
            events=s.events_fetched_total or 0,
            last_sync=s.last_sync_at,
            status=s.status or "idle",
            error=s.error_detail,
        )
        for s in states
    ]


async def _trigger_connector(connector_class):
    """Run a connector in the background."""
    async with AsyncSessionLocal() as session:
        async with httpx.AsyncClient(timeout=60.0) as http:
            connector = connector_class(session=session, http_client=http)
            await connector.run()


@router.post("/trigger/{connector_name}")
async def trigger_connector(
    connector_name: str,
    background_tasks: BackgroundTasks,
):
    """Manually trigger a connector sync.

    Valid connector names: jira, gitlab, cicd_jenkins, claude_ai, business_value
    """
    if connector_name not in CONNECTOR_MAP:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown connector '{connector_name}'. "
            f"Valid: {', '.join(CONNECTOR_MAP.keys())}",
        )

    connector_class = CONNECTOR_MAP[connector_name]
    background_tasks.add_task(_trigger_connector, connector_class)

    return {
        "status": "triggered",
        "connector": connector_name,
        "message": f"{connector_name} sync started in background",
    }


@router.get("/events", response_model=List[ActivityEventResponse])
async def get_events(
    db: AsyncSession = Depends(get_db),
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    source: Optional[str] = Query(None, description="Filter by source (Jira, Git, CICD)"),
    date_from: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    date_to: Optional[datetime] = Query(None, description="End date (ISO format)"),
    issue_id: Optional[str] = Query(None, description="Filter by Jira issue key (e.g., JET-83)"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Browse raw activity events with filters."""
    conditions = []

    if employee_id:
        conditions.append(ActivityEvent.employee_id == employee_id)
    if source:
        conditions.append(ActivityEvent.source == source)
    if date_from:
        conditions.append(ActivityEvent.timestamp >= date_from)
    if date_to:
        conditions.append(ActivityEvent.timestamp <= date_to)

    stmt = select(ActivityEvent)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    # JSONB filter for issue_id
    if issue_id:
        stmt = stmt.where(
            ActivityEvent.payload["issueID"].astext == issue_id
        )

    stmt = stmt.order_by(ActivityEvent.timestamp.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    events = result.scalars().all()
    return events


@router.get("/events/count")
async def get_events_count(
    db: AsyncSession = Depends(get_db),
    employee_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    """Get total event counts, optionally filtered."""
    conditions = ["1=1"]
    params = {}

    if employee_id:
        conditions.append("employee_id = :eid")
        params["eid"] = employee_id
    if source:
        conditions.append("source = :src")
        params["src"] = source

    where = " AND ".join(conditions)
    # Disable TimescaleDB vectorized aggregation to avoid varchar bug
    await db.execute(text("SET timescaledb.enable_vectorized_aggregation = OFF"))
    result = await db.execute(
        text(
            f"SELECT source, COUNT(*) FROM activity_events "
            f"WHERE {where} GROUP BY source ORDER BY COUNT(*) DESC"
        ),
        params,
    )
    rows = result.fetchall()
    total = sum(r[1] for r in rows)
    return {
        "total": total,
        "by_source": {r[0]: r[1] for r in rows},
    }
