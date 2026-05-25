from typing import Optional, List, Any
from datetime import datetime
from enum import StrEnum, Enum, IntEnum
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

from .counters import Counter
from . import logic
from .questions import Question
from .users import User


class PollType(BaseModel):
    id: int
    name: str
    disabled: bool


class PollTypes:
    all_at_once = PollType(id=1, name="Отображение респонденту всех вопросов сразу", disabled=False)
    by_block = PollType(id=2, name="Отображение опроса по блокам", disabled=False)
    one_question  = PollType(id=3, name="Отображение опроса по одному вопросу", disabled=False)

    _map = {
        "all_at_once": all_at_once,
        "by_block": by_block,
        "one_question": one_question ,
    }

    @classmethod
    def from_str(cls, value: str) -> PollType:
        return cls._map[value]


class PollStatus(BaseModel):
    id: int
    name: str
    disabled: bool


class PollStatuses:
    active = PollStatus(id=1, name="Активный", disabled=False)
    closed = PollStatus(id=4, name="Завершенный", disabled=False)
    published = PollStatus(id=3, name="Опубликован", disabled=False)
    deleted = PollStatus(id=2, name="Удаленный", disabled=False)

    _map = {
        "active": active,
        "closed": closed,
        "published": published,
        "deleted": deleted,
    }

    @classmethod
    def from_str(cls, value: str) -> PollStatus:
        return cls._map[value]


class Language(IntEnum):
    rus = 1
    eng = 2


class Block(BaseModel):
    id: int
    order: int
    name: str
    title: str
    description: str
    created_at: datetime
    poll_id: int
    questions: List[Question]
    is_panel: bool = False

class PageData(BaseModel):
    title: str
    description: str

class Page(BaseModel):
    id: int
    name: str
    data: PageData
    type_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    poll_id: int

class Poll(BaseModel):
    id: int
    uuid: UUID
    name: str
    title: str = Field(default="")
    description: str = Field(default="")
    created_at: datetime = Field(default=datetime.now())
    user_id: int
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    status_id: int
    status_updated_at: Optional[datetime] = None
    type_id: int
    is_multiple: bool
    can_cameback: bool
    field_date: Optional[datetime] = None
    banner: str = Field(default="")
    background: str = Field(default="")
    poll_responsible: Optional[int] = None
    meta: Optional[List[int]] = Field(default=[0]) # missing in poll/full
    counters: Optional[List[Counter]] = None
    notify_flag: bool = False

    blocks: List[Block] = Field(default=[])
    jumps: List[logic.Jump] = Field(default=[])
    displays: List[logic.Display] = Field(default=[])
    display_answers: List[logic.DisplayAnswers] = Field(default=[])
    pages: List[Page] = Field(default=[])

    sources: List[Any] = Field(default=[])
    source_id: Optional[str] = None
    state_id: int = 0
    logic_panel: None = None # what's this?
    language_id: int = 1 # Russian


    # utility properties todo
    user: Optional[User] = Field(default=None)




class PollGetListPayload(BaseModel):
    limit: int = Field(default=11, ge=0, le=50)
    offset: int = Field(default=0, ge=0)
    is_in_track: bool = False,
    meta: List[int] = None,
    sociologist_id: int = None,
    status_id: int = None,
    targetologist_id: int = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,