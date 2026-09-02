from __future__ import annotations

from typing import Optional, List, Any, Literal
from datetime import datetime
from enum import IntEnum, StrEnum
from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator, PrivateAttr
from uuid import UUID
from itertools import chain

from ..text_worker import parse_text

from .counters import Counter
from . import logic
from .pages import Page
from .blocks import Block
from .sources import Source
from .questions import Question, ChildQuestion
from .. import io


class BackgroundColor(StrEnum):
    """Poll page background color preset."""
    LIGHT_BLUE = "#bdcff6"
    LIGHT_ORANGE = "#ffd1af"
    LIGHT_GREEN = "#b6ffb5"
    LIGHT_RED = "#ff7c7c"
    PURPLE = "#7059ff"
    NO_SET = ''


class Banner(StrEnum):
    """Poll header banner/illustration preset."""
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
    """Lifecycle status of a poll."""
    ACTIVE = 1
    CLOSED = 4
    PUBLISHED = 3
    DELETED = 2


class PollType(IntEnum):
    """How the poll presents its questions to a respondent."""
    ALL_AT_ONCE = 1    # Отображение респонденту всех вопросов сразу / all questions on one screen
    BY_BLOCK = 2        # Отображение опроса по блокам / one block per screen
    ONE_QUESTION = 3     # Отображение опроса по одному вопросу / one question per screen


class Poll(BaseModel):
    """
    A full poll (survey): header metadata plus its blocks, questions, pages,
    logic rules and counters. Constructing/validating a ``Poll`` (via
    ``Poll(...)`` or ``Poll.model_validate(...)``) automatically wires
    everything together - back-references (``_poll`` on blocks/questions/
    answers/logic rules, ``_parent_question`` on children), display order
    (``_poll_order``), and id-keyed lookup indexes - via the ``@model_validator``
    methods below. Nothing further needs to be called after construction;
    ``rebind_questions()``/``rebind_logics()``/``rebind_blocks()`` exist only
    to manually re-run that wiring later, e.g. after mutating ``self.blocks``
    in place post-construction.
    """
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
    is_multiple: bool = True       # can be used several times
    can_cameback: bool = False     # almost never used as True
    field_date: Optional[datetime] = None  # ?
    banner: Banner = Field(default=Banner.DEFAULT)
    background: BackgroundColor = Field(default=BackgroundColor.LIGHT_BLUE)

    poll_responsible: Optional[int] = None

    meta: Optional[List[int]] = Field(default=[0])  # missing in poll/full
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
    # Shape unknown (like counters.CounterSource) - typed Any rather than
    # None so a future non-null value doesn't fail validation outright.
    logic_panel: Any = None  # what's this?
    language_id: int = 1  # Russian

    # TODO: no `user` field yet - add `user: Optional[User] = None` here
    # once resources/user.py's User model is wired into this package.

    _question_counter: int = PrivateAttr(default=0)  # currently unused

    _question_by_id: dict[int, Question] = PrivateAttr(default_factory=dict)
    _children_by_id: dict[int, ChildQuestion] = PrivateAttr(default_factory=dict)
    _block_by_id: dict[int, Block] = PrivateAttr(default_factory=dict)
    _page_by_id: dict[int, Page] = PrivateAttr(default_factory=dict)

    @property
    def human_description(self) -> str:
        """``description`` with the constructor's markup/placeholders resolved to plain text."""
        return parse_text(self.description)

    @property
    def len_question(self) -> int:
        """Total number of top-level questions across all blocks."""
        return sum(len(block.questions) for block in self.blocks)

    @model_validator(mode="after")
    def _bind_questions_to_poll(self) -> Poll:
        """Set ``_poll`` on every block/question/answer (for compatibility with e.g. ``question.jumps``)."""
        for block in self.blocks:
            block._poll = self
            for question in block.questions:
                question._poll = self
                for answer in question.answers or []:
                    answer._poll = self
        return self

    @model_validator(mode="after")
    def _bind_child_to_parent(self) -> Poll:
        """Set ``_parent_question`` on every nested (matrix-row) child question."""
        for question in self.questions:
            for child in question.children:
                child._parent_question = question
        return self

    def rebind_questions(self) -> None:
        """Manually re-run :meth:`_bind_questions_to_poll` (already runs automatically on construction)."""
        self._bind_questions_to_poll()

    @model_validator(mode="after")
    def _bind_logics_to_poll(self) -> Poll:
        """Set ``_poll`` on every jump/display/display-answer logic rule."""
        for rules in (self.jumps, self.display_answers, self.displays):
            for rule in rules:
                rule._poll = self
        return self

    def rebind_logics(self) -> None:
        """Manually re-run :meth:`_bind_logics_to_poll` (already runs automatically on construction)."""
        self._bind_logics_to_poll()

    @model_validator(mode="after")
    def _bind_blocks_to_poll(self) -> Poll:
        """Set ``_poll`` on every block."""
        for block in self.blocks:
            block._poll = self
        return self

    def rebind_blocks(self) -> None:
        """Manually re-run :meth:`_bind_blocks_to_poll` (already runs automatically on construction)."""
        self._bind_blocks_to_poll()

    @property
    def questions(self) -> List[Question]:
        """All top-level questions across all blocks, in block order then question order."""
        return [
            question
            for block in sorted(self.blocks, key=lambda b: b.order)
            for question in sorted(block.questions, key=lambda q: q.order)
        ]

    @model_validator(mode="after")
    def count_questions(self) -> Poll:
        """
        Assign each top-level question a whole-number ``_poll_order`` (1, 2,
        3, ...) and each of its nested children a fractional order right
        after it (1.1, 1.2, ..., 2.1, ...), so sorting by ``_poll_order``
        gives the true respondent-facing sequence.
        """
        order = 1
        for question in self.questions:
            question._poll_order = order
            for j, child in enumerate(question.children, start=1):
                child._poll_order = order + j / 10
            order += 1
        return self

    def _rebuild_index(self, index_name: str, collection_name: str) -> None:
        """Rebuild a private ``{item.id: item}`` lookup from a list field."""
        setattr(
            self,
            index_name,
            {item.id: item for item in getattr(self, collection_name)},
        )

    @model_validator(mode="after")
    def index_questions(self) -> Poll:
        """Rebuild ``_question_by_id`` to cover both top-level questions and their nested children."""
        self._question_by_id = {
            item.id: item
            for question in self.questions
            for item in chain((question,), question.children)
        }
        return self

    @model_validator(mode="after")
    def index_blocks(self) -> Poll:
        self._rebuild_index(index_name="_block_by_id", collection_name="blocks")
        return self

    @model_validator(mode="after")
    def index_pages(self) -> Poll:
        self._rebuild_index(index_name="_page_by_id", collection_name="pages")
        return self

    def get_question_by_id(self, item_id: int) -> Optional[Question]:
        return self._question_by_id.get(item_id)

    def get_block_by_id(self, item_id: int) -> Optional[Block]:
        return self._block_by_id.get(item_id)

    def get_page_by_id(self, item_id: int) -> Optional[Page]:
        return self._page_by_id.get(item_id)

    def to_json_file(self, file_path: str) -> None:
        io.to_json(self=self, file_path=file_path)

    @classmethod
    def from_json_file(cls, file_path: str) -> Poll:
        return io.from_json(cls=cls, file_path=file_path)

    def to_docx(self, file_path: str) -> None:
        io.export_docx(poll=self, file_path=file_path)


class GetPollHeaderPayload(BaseModel):
    """Request body for fetching just a poll's header."""
    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., ge=1)


class GetPollListPayload(BaseModel):
    """
    Request body for listing/searching polls.
    """
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=11, ge=0, le=50)
    offset: int = Field(default=0, ge=0)
    is_in_track: bool = False
    meta: Optional[List[int]] = None
    sociologist_id: Optional[int] = None
    status_id: Optional[int] = None
    targetologist_id: Optional[int] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None


class ExportFormat(IntEnum):
    """File format for a poll data export."""
    XLSX = 1
    SAV = 2
    CSV = 5


class QuestionFilter(BaseModel):
    """Restricts an export to respondents who gave a specific answer to a specific question."""
    model_config = ConfigDict(extra="forbid")

    question_id: int = Field(..., ge=1)
    answer_id: int = Field(..., ge=1)


class ExportFilter(BaseModel):
    """Filter criteria for a poll data export."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    counters_ids: Optional[List[int]] = None
    from_: Optional[datetime] = Field(default=None, alias="from")
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
    """Request body for triggering a poll data export."""
    model_config = ConfigDict(extra="forbid")

    poll_id: int = Field(..., ge=1)
    filter: ExportFilter = Field(default_factory=ExportFilter)
    format_id: ExportFormat | EXPORT_FORMATS = Field(default=ExportFormat.CSV)

    @field_validator("format_id", mode="before")
    @classmethod
    def _coerce_format_id(cls, v: Any) -> Any:
        """Accept either the ``ExportFormat`` enum or its lowercase string name (``"csv"`` -> ``ExportFormat.CSV``)."""
        if isinstance(v, str):
            return ExportFormat[v.upper()]
        return v


class DownloadPayload(BaseModel):
    """Request body for downloading or acknowledging a finished export, identified by its job uuid."""
    model_config = ConfigDict(extra="forbid")

    uuid: UUID


class ExportStatus(StrEnum):
    """Status of an in-progress export job."""
    DONE = "done"
    ERROR = "error"
    IN_PROGRESS = "in_progress"


class ProgressStatus(BaseModel):
    """Status of one export job, as returned by the progress endpoint."""
    user_id: int
    uuid: UUID
    jwt_uuid: UUID
    params: ExportPayload
    status: str