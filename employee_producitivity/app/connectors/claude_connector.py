"""A4: Claude AI Usage Logs Connector.

Designed to pull from an internal usage log endpoint.
Currently a stub — the exact API depends on how Claude Teams exposes usage data.
"""

from datetime import datetime
from typing import List, Optional

from app.connectors.base import BaseConnector
from app.models.activity_event import ActivityEvent
from app.models.base import new_uuid


class ClaudeAIConnector(BaseConnector):
    connector_name = "claude_ai"

    async def fetch_raw(self, since: Optional[datetime] = None) -> List[dict]:
        # Placeholder: fetch from internal usage API or CSV export
        # Expected format: list of {user_email, prompt, model, response_accepted, timestamp}
        return []

    def normalize(self, raw_records: List[dict]) -> List[ActivityEvent]:
        events = []
        for record in raw_records:
            quality_flag = record.get("response_accepted", "unknown")
            events.append(
                ActivityEvent(
                    event_id=new_uuid(),
                    employee_id=record.get("employee_id", "unknown"),
                    source="ClaudeAI",
                    timestamp=datetime.fromisoformat(record["timestamp"]),
                    payload={
                        "model": record.get("model"),
                        "prompt_length": len(record.get("prompt", "")),
                        "quality_flag": quality_flag,
                        "context": record.get("context"),
                    },
                    raw_source_id=f"claude-{record.get('log_id', new_uuid())}",
                )
            )
        return events
