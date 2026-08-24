from enum import IntEnum
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

class Source(BaseModel):
    """
    returned by /api/source/list
    """
    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., ge=1)
    name: str
    utm: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    name_sort_weight: int
    visible: bool
    is_active: bool
    activate: bool