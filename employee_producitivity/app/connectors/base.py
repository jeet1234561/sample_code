from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_event import ActivityEvent
from app.models.connector_state import ConnectorState


class BaseConnector(ABC):
    """Abstract connector that all data source connectors must implement.

    Lifecycle per poll cycle:
      1. load_state()    -- read cursor from DB
      2. fetch_raw()     -- call external API, get raw data
      3. normalize()     -- convert raw -> List[ActivityEvent]
      4. save_state()    -- persist new cursor to DB
    """

    connector_name: str

    def __init__(self, session: AsyncSession, http_client):
        self.session = session
        self.http = http_client

    async def load_state(self) -> Optional[ConnectorState]:
        result = await self.session.get(ConnectorState, self.connector_name)
        return result

    async def save_state(self, state: ConnectorState):
        self.session.add(state)
        await self.session.flush()

    @abstractmethod
    async def fetch_raw(self, since: Optional[datetime] = None) -> List[dict]:
        """Fetch raw records from the external API.

        Must handle pagination internally.
        """
        ...

    @abstractmethod
    def normalize(self, raw_records: List[dict]) -> List[ActivityEvent]:
        """Convert raw API records into normalized ActivityEvent objects."""
        ...

    async def run(self):
        """Full poll cycle. Called by the scheduler."""
        state = await self.load_state()
        since = state.last_sync_at if state else None

        if not state:
            state = ConnectorState(connector_name=self.connector_name)

        state.status = "running"
        await self.save_state(state)

        try:
            raw = await self.fetch_raw(since=since)
            events = self.normalize(raw)

            for event in events:
                await self._upsert_event(event)

            state.last_sync_at = datetime.now(timezone.utc)
            state.events_fetched_total = (state.events_fetched_total or 0) + len(events)
            state.status = "healthy"
            state.error_detail = None
            await self.save_state(state)
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            state.status = "error"
            state.error_detail = str(e)[:500]
            await self.save_state(state)
            await self.session.commit()
            raise

    async def _upsert_event(self, event: ActivityEvent):
        """Insert event, skip if raw_source_id already exists (dedup)."""
        stmt = (
            insert(ActivityEvent)
            .values(
                event_id=event.event_id,
                employee_id=event.employee_id,
                source=event.source,
                timestamp=event.timestamp,
                payload=event.payload,
                raw_source_id=event.raw_source_id,
            )
            .on_conflict_do_nothing(
                index_elements=["raw_source_id", "timestamp"],
                index_where=text("raw_source_id IS NOT NULL"),
            )
        )
        await self.session.execute(stmt)
