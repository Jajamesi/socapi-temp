from typing import Optional, List, Any
from datetime import datetime
from enum import IntEnum, StrEnum, auto
from pydantic import BaseModel, Field
from uuid import UUID

from ..text_worker import parse_text

from .counters import Counter
from . import logic
from  .pages import Page
from .blocks import Block
from .sources import Source

class BackgroundColor(StrEnum):
    LIGHT_BLUE = "#bdcff6"
    LIGHT_ORANGE = "#ffd1af"
    LIGHT_GREEN = "#b6ffb5"
    LIGHT_RED = "#ff7c7c"
    PURPLE = "#7059ff"



class Banner(StrEnum):
    DEFAULT = "DEFAULT"
    HEAT_MAP_02 = "HEAT_MAP_02"
    HOMELESS_ANIMALS_AND_HUNT_01 = "HOMELESS_ANIMALS_AND_HUNT_01"
    INTERNET_SERVICES_01 = "INTERNET_SERVICES_01"
    PUBLIC_TRANSPORT_01 = "PUBLIC_TRANSPORT_01"
    ROADS_01 = "ROADS_01"
    REGION_CFO_01 = "REGION_CFO_01"
    REGION_DFO_01 = "REGION_DFO_01"
    REGION_PFO_01 = "REGION_PFO_01"
    REGION_SFO_01 = "REGION_SFO_01"
    REGION_SKFO_01 = "REGION_SKFO_01"
    REGION_SKFO_02 = "REGION_SKFO_02"
    REGION_SZFO_01 = "REGION_SZFO_01"
    REGION_UFO_01 = "REGION_UFO_01"
    REGION_URALFO_01 = "REGION_URALFO_01"
    NO_THEME_01 = "NO_THEME_01"
    ECOLOGY_01 = "ECOLOGY_01"


class PollStatus(IntEnum):
    ACTIVE = 1
    CLOSED = 4
    PUBLISHED = 3
    DELETED = 2

class PollType(IntEnum):
    ALL_AT_ONCE = 1 # Отображение респонденту всех вопросов сразу
    BY_BLOCK = 2 # Отображение опроса по блокам
    ONE_QUESTION = 3 # Отображение опроса по одному вопросу

class Poll(BaseModel):
    id: int
    uuid: UUID
    name: str
    title: str = Field(default="")
    description: str = Field(default="")
    created_at: Optional[datetime] = None
    user_id: int
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    status_id: PollStatus = Field(default=PollStatus.ACTIVE, description="Default state for created poll")
    status_updated_at: Optional[datetime] = None
    type_id: PollType
    is_multiple: bool = True # can be used several times
    can_cameback: bool = False # almost never used as True
    field_date: Optional[datetime] = None # ?
    banner: Banner = Field(default=Banner.DEFAULT)
    background: BackgroundColor = Field(default=BackgroundColor.LIGHT_BLUE)

    poll_responsible: Optional[int] = None

    meta: Optional[List[int]] = Field(default=[0]) # missing in poll/full
    counters: Optional[List[Counter]] = None
    notify_flag: bool = False

    blocks: List[Block] = Field(default_factory=list)
    jumps: List[logic.Jump] = Field(default_factory=list)
    displays: List[logic.Display] = Field(default_factory=list)
    display_answers: List[logic.DisplayAnswers] = Field(default_factory=list)
    pages: List[Page] = Field(default_factory=list)

    sources: List[Source] = Field(default_factory=list)
    source_id: Optional[str] = None
    state_id: int = 0
    logic_panel: None = None # what's this?
    language_id: int = 1 # Russian


    # user: Optional[User] = Field(default=None)

    @property
    def human_description(self) -> str:
        return parse_text(self.description)


class GetPollHeaderPayload(BaseModel):
    id: int = Field(..., ge=1)


class GetPollListPayload(BaseModel):
    limit: int = Field(default=11, ge=0, le=50)
    offset: int = Field(default=0, ge=0)
    is_in_track: bool = False,
    meta: List[int] = None,
    sociologist_id: int = None,
    status_id: int = None,
    targetologist_id: int = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,


class ExportFormat(IntEnum):
    XLSX=1
    SAV=2
    CSV=5


class ExportFilter(BaseModel):
    domain_ids: List[int] = Field(default=[1])
    is_poll_complete: bool = Field(default=True)
    is_poll_in_progress: bool = Field(default=True)
    ...

class ExportPayload(BaseModel):
    poll_id: int = Field(..., ge=1)
    filter: ExportFilter = Field(default_factory=ExportFilter)
    format_id: ExportFormat = Field(default=ExportFormat.CSV)


class DownloadPayload(BaseModel):
    uuid: UUID


class ExportStatus(StrEnum):
    DONE = "done"
    ERROR = "error"
    IN_PROGRESS = "in_progress"


class ProgressStatus(BaseModel):
    user_id: int
    uuid: UUID
    jwt_uuid: UUID
    params: ExportPayload
    status: str