from typing import Optional, List, Any, Literal, Dict
from datetime import datetime
from enum import IntEnum, StrEnum, auto
from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator, PrivateAttr
from uuid import UUID

from ..text_worker import parse_text

from .counters import Counter
from . import logic
from  .pages import Page
from .blocks import Block
from .sources import Source
from .questions import Question
from .. import io

class BackgroundColor(StrEnum):
    LIGHT_BLUE = "#bdcff6"
    LIGHT_ORANGE = "#ffd1af"
    LIGHT_GREEN = "#b6ffb5"
    LIGHT_RED = "#ff7c7c"
    PURPLE = "#7059ff"
    NO_SET = ''



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
    NO_SET = ''


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

    _question_counter: int = PrivateAttr(default=0)

    _question_by_id: dict[int, Question] = PrivateAttr(default_factory=dict)
    _block_by_id: dict[int, Block] = PrivateAttr(default_factory=dict)
    _page_by_id: dict[int, Page] = PrivateAttr(default_factory=dict)




    # user: Optional[User] = Field(default=None)

    @property
    def human_description(self) -> str:
        return parse_text(self.description)

    @property
    def len_question(self):
        i = 0
        for b in self.blocks:
            i+=len(b.questions)
        return i



    @model_validator(mode="after")
    def _bind_questions_to_poll(self) -> "Poll":
        """
        for compatibility to call parent methods like question.logics
        """
        for block in self.blocks:
            block._poll = self
            for question in block.questions:
                question._poll = self
                for answer in question.answers:
                    answer._poll = self
        return self

    def rebind_questions(self):
        self._bind_questions_to_poll()

    @model_validator(mode="after")
    def _bind_logics_to_poll(self) -> "Poll":
        """
        for compatibility to call parent methods like question.logics
        """
        for logic_type in [self.jumps, self.display_answers, self.displays]:
            for logic in logic_type:
                logic._poll = self

        return self

    def rebind_logics(self):
        self._bind_logics_to_poll()

    @model_validator(mode="after")
    def _bind_blocks_to_poll(self) -> "Poll":
        """
        for compatibility to call parent methods like question.logics
        """
        for block in self.blocks:
            block._poll = self

        return self

    def rebind_blocks(self):
        self._bind_blocks_to_poll()

    @property
    def questions(self):
        return [
            q
            for block in sorted(self.blocks, key=lambda x: x.order)
            for q in sorted(block.questions, key=lambda x: x.order)
        ]

    def count_questions(self):
        i = 1
        for q in self.questions:
            q._poll_order = i
            i+=1

    def _rebuild_index(self, index_name: str, collection_name: str):
        setattr(
            self,
            index_name,
            {
                item.id: item
                for item in getattr(self, collection_name)
            },
        )

    @model_validator(mode="after")
    def index_questions(self):
        self._rebuild_index(index_name="_question_by_id", collection_name="questions")
        return self

    @model_validator(mode="after")
    def index_blocks(self):
        self._rebuild_index(index_name="_block_by_id", collection_name="blocks")
        return self

    @model_validator(mode="after")
    def index_pages(self):
        self._rebuild_index(index_name="_page_by_id", collection_name="pages")
        return self

    def get_question_by_id(self, item_id: int):
        return self._question_by_id.get(item_id)
    def get_block_by_id(self, item_id: int):
        return self._block_by_id.get(item_id)
    def get_page_by_id(self, item_id: int):
        return self._page_by_id.get(item_id)


    def to_json_file(self, file_path: str):
        io.to_json(self=self, file_path=file_path)

    @classmethod
    def from_json_file(cls, file_path: str):
        return io.from_json(cls=cls, file_path=file_path)


    def to_docx(self, file_path: str):
        io.export_docx(poll=self, file_path=file_path)




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


class QuestionFilter(BaseModel):
    question_id: int = Field(..., ge=1)
    answer_id: int = Field(..., ge=1)

class ExportFilter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    counters_ids: Optional[List[int]] = None
    from_:Optional[datetime] = Field(default=None, alias="from")
    to: Optional[datetime] = Field(default=None)
    is_disqualified: Optional[bool] = None
    is_only_plan: Optional[bool] = None
    questions: Optional[List[QuestionFilter]] = None
    utm_source: Optional[List[int]] = None

    domain_ids: List[int] = Field(default=[1])
    is_poll_complete: bool = Field(default=True)
    is_poll_in_progress: bool = Field(default=True)



EXPORT_FORMATS = Literal["xlsx", "sav", "csv"]

class ExportPayload(BaseModel):
    poll_id: int = Field(..., ge=1)
    filter: ExportFilter = Field(default_factory=ExportFilter)
    format_id: ExportFormat | EXPORT_FORMATS = Field(default=ExportFormat.CSV)

    @field_validator('format_id', mode='before')
    @classmethod
    def form_literal(cls, v):
        if isinstance(v, str):
            return ExportFormat[v.upper()]
        else:
            return v



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