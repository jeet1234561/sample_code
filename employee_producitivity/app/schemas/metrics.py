from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class MetricSnapshotResponse(BaseModel):
    employee_id: str
    metric_name: str
    category: str
    value: float
    unit: Optional[str] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    computed_at: datetime
    details: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}
