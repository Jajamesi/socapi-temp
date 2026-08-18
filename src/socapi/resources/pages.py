from enum import IntEnum

from ..text_worker import parse_text

from pydantic import BaseModel, Field, ConfigDict

class PageData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str

    @property
    def human_description(self) -> str:
        return parse_text(self.description)


class PageType(IntEnum):
    GREETING = 1
    FINISH=2
    DISQUALIFICATION=3


class Page(BaseModel):
    """
    returned by /api/page/getall
    """
    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., ge=1)
    name: str
    data: PageData
    type_id: PageType = Field(..., ge=1)
    poll_id: int = Field(..., ge=1)




class GetPagesPayload(BaseModel):
    poll_id: int = Field(..., ge=1)