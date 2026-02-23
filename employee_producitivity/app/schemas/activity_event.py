from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class ActivityEventResponse(BaseModel):
    event_id: str
    employee_id: str
    source: str
    timestamp: datetime
    payload: Dict[str, Any]
    raw_source_id: Optional[str] = None
    ingested_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
