from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Optional, Generator
if TYPE_CHECKING:
    # Only needed for the `_poll` backref type hint; importing at runtime
    # would create a circular import with polls.py (Poll owns Blocks).
    from .polls import Poll

from ..text_worker import parse_text

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr


class PageData(BaseModel):
    """Localized/rich-text content of a page (title + body)."""
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str

    @property
    def human_description(self) -> str:
        """``description`` with the constructor's markup/placeholders resolved to plain text."""
        return parse_text(self.description)


class PageType(IntEnum):
    """The role a page plays in the poll flow."""
    GREETING = 1
    FINISH = 2
    DISQUALIFICATION = 3


class Page(BaseModel):
    """A greeting/finish/disqualification page of a poll, as returned by ``/api/page/getall``."""
    model_config = ConfigDict(extra="forbid")

    id: Optional[int] = Field(
        default=None,
        description="The page ID. Usually assigned by the server."
    )

    name: str = Field(
        description="The name of the page."
    )

    data: PageData = Field(
        default_factory=lambda: PageData(title="", description=""),
        description="The page content, including its title and description."
    )

    type_id: PageType = Field(
        ge=1,
        description="The type of page: greeting, finish, or disqualification."
    )

    poll_id: Optional[int] = Field(
        default=None,
        description="The ID of the poll this page belongs to."
    )

    _poll: Optional[Poll] = PrivateAttr(default=None)
    _id_generator: Generator[int, None, None] = PrivateAttr(default=None)


def dump_create_payload(self):
        """Use to filter fields in create page request"""
        fields = {
            "data",
            "name",
            "poll_id",
            "type_id",
        }

        return self.model_dump(include=fields)


class GetPagesPayload(BaseModel):
    """Request body for listing the pages of a poll."""
    model_config = ConfigDict(extra="forbid")

    poll_id: int = Field(..., ge=1)