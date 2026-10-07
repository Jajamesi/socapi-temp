from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only needed for the `_poll` backref type hint; importing at runtime
    # would create a circular import with polls.py (Poll owns Blocks).
    from .polls import Poll
    from .questions import Question

from typing import Optional, List, Tuple, Generator
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr



class Block(BaseModel):
    """
    A block (question group) within a poll.

    ``_poll`` is an optional back-reference to the owning :class:`Poll`,
    populated once ``PollResource.get_poll_structure`` wires nested items
    together (see the ``TODO`` in ``client.py``); it's not set by plain
    ``model_validate(**api_response)`` construction.
    """
    id: Optional[int] = None
    order: Optional[int] = None
    name: str
    title: str = Field(default="")
    description: str = Field(default="")
    created_at: Optional[datetime] = None
    questions: List[Question] = Field(default_factory=list)
    poll_id: int | None = None
    is_panel: bool = False

    _poll: Optional[Poll] = PrivateAttr(default=None)
    _id_generator: Generator[int, None, None] = PrivateAttr(default=None)

    def dump_create_payload(self):
        """Use to filter fields in create block request"""
        fields = {
            "description",
            "name",
            "order",
            "poll_id",
            "title",
        }

        return self.model_dump(include=fields)

    def add_question(self, question: Question) -> Question:
        """
        Append ``question`` (with its answers / matrix rows) to this block.

        The block must already belong to a poll (``poll.add_block(block)``):
        the poll hands out the temporary ids used until the poll is uploaded.
        """
        poll = self._poll
        if poll is None:
            raise ValueError("Add this block to a poll first (poll.add_block(block)).")
        if question._poll is not None:
            raise ValueError("This question already belongs to a poll.")

        question.order = len(self.questions) + 1
        question.block_id = self.id
        question.id = poll._next_id()
        question._id_generator = poll._id_generator
        question._poll = poll
        self.questions.append(question)

        # answers / matrix rows passed to the constructor get their ids here,
        # which lets logic reference them right away
        for answer in question.answers or []:
            question._adopt_answer(answer)
        for child in question.children or []:
            question._adopt_child(child)

        poll._refresh()
        return question


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


