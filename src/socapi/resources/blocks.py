from typing import Optional, List, Any
from datetime import datetime
from enum import StrEnum, IntEnum
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

from .questions import Question


class Block(BaseModel):
    id: Optional[int] = None
    order: int = Field(..., ge=1)
    name: str
    title: str = Field(default="")
    description: str = Field(default="")
    created_at: Optional[datetime] = None
    questions: List[Question] | None = Field(default_factory=list)
    poll_id: int
    is_panel: bool = False


class BlockInclude(StrEnum):
    id = "id"
    name = "name"
    title = "title"
    description = "description"
    poll_id = "poll_id"
    order = "order"

ALL_BLOCK_INCLUDES = list(BlockInclude)

class GetBlocksPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    poll_id: int = Field(..., ge=1)
    includes: list[BlockInclude] = Field(default_factory=lambda: ALL_BLOCK_INCLUDES.copy())