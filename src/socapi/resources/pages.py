from __future__ import annotations

from enum import IntEnum

from ..text_worker import parse_text

from pydantic import BaseModel, Field, ConfigDict


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

    id: int = Field(..., ge=1)
    name: str
    data: PageData
    # `ge=1` here is redundant: PageType's members are already exactly
    # {1, 2, 3} (validated by enum membership), so it can't reject anything
    # membership doesn't already reject - kept only because it's harmless.
    type_id: PageType = Field(..., ge=1)
    poll_id: int = Field(..., ge=1)


class GetPagesPayload(BaseModel):
    """Request body for listing the pages of a poll."""
    model_config = ConfigDict(extra="forbid")

    poll_id: int = Field(..., ge=1)