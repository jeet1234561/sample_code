from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ConnectorStatusResponse(BaseModel):
    source: str
    events: int
    last_sync: Optional[datetime] = None
    status: str
    error: Optional[str] = None

    model_config = {"from_attributes": True}
