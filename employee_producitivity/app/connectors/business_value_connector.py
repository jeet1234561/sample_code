"""A5: Business Value Tags Connector.

Pulls from a product analytics feed or admin API/CSV upload.
Currently a stub — data is populated via admin API endpoints in Module F.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.connectors.base import BaseConnector
from app.models.activity_event import ActivityEvent
from app.models.base import new_uuid


class BusinessValueConnector(BaseConnector):
    connector_name = "business_value"

    async def fetch_raw(self, since: Optional[datetime] = None) -> List[dict]:
        # In practice, this could be:
        # 1. An internal REST endpoint exposing PM-assigned values
        # 2. A CSV upload processed via a separate admin endpoint
        # 3. A product analytics tool API (Amplitude, Mixpanel)
        return []

    def normalize(self, raw_records: List[dict]) -> List[ActivityEvent]:
        events = []
        for record in raw_records:
            events.append(
                ActivityEvent(
                    event_id=new_uuid(),
                    employee_id=record.get("employee_id", "system"),
                    source="BizValue",
                    timestamp=datetime.now(timezone.utc),
                    payload={
                        "featureID": record["feature_id"],
                        "featureName": record.get("feature_name"),
                        "dollarValue": record["dollar_value"],
                        "adoptionRate": record.get("adoption_rate"),
                        "taggedBy": record.get("tagged_by"),
                    },
                    raw_source_id=f"biz-{record['feature_id']}-{record.get('version', '1')}",
                )
            )
        return events
