from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only needed for the `_poll` backref type hint; importing at runtime
    # would create a circular import with polls.py (Poll owns Blocks).
    from .polls import Poll

from typing import Optional, List, Tuple
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr

from .questions import Question


class Block(BaseModel):
    """
    A block (question group) within a poll.

    ``_poll`` is an optional back-reference to the owning :class:`Poll`,
    populated once ``PollResource.get_poll_structure`` wires nested items
    together (see the ``TODO`` in ``client.py``); it's not set by plain
    ``model_validate(**api_response)`` construction.
    """
    id: Optional[int] = None
    order: int = Field(..., ge=1)
    name: str
    title: str = Field(default="")
    description: str = Field(default="")
    created_at: Optional[datetime] = None
    questions: Optional[List[Question]] = Field(default_factory=list)
    poll_id: int
    is_panel: bool = False

    _poll: Optional[Poll] = PrivateAttr(default=None)


class BlockInclude(StrEnum):
    """Fields of :class:`Block` that can be requested via ``includes``."""
    id = "id"
    name = "name"
    title = "title"
    description = "description"
    poll_id = "poll_id"
    order = "order"

ALL_BLOCK_INCLUDES: Tuple[BlockInclude, ...] = tuple(BlockInclude)

class GetBlocksPayload(BaseModel):
    """Request body for listing the blocks of a poll."""
    model_config = ConfigDict(extra="forbid")

    poll_id: int = Field(..., ge=1)
    includes: list[BlockInclude] = Field(default_factory=lambda: list(ALL_BLOCK_INCLUDES))