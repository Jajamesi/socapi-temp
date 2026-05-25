from typing import Optional, List, Any
from datetime import datetime
from enum import StrEnum, IntEnum
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

from .questions import Question


class Block(BaseModel):
    id: Optional[int] = None
    order: int
    name: str
    title: str
    description: str
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    questions: Optional[List[Question]]
    poll_id: int
    is_panel: bool = False