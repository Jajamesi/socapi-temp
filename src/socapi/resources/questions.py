from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only needed for the `_poll` backref type hint; importing at runtime
    # would create a circular import with polls.py (Poll owns Questions).
    from .polls import Poll

from typing import Optional, List, Tuple, Any
from datetime import datetime
from enum import StrEnum, IntEnum
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, field_validator, model_validator

from ..text_worker import parse_text


class AnswerTypes(IntEnum):
    """Question type codes as used by the constructor API."""
    single_answer = 1                  # Один ответ / single choice
    dropdown = 2                       # Выпадающий список / dropdown
    single_answer_per_row = 3          # Один ответ по строке / single choice per row (matrix)
    multiple_choice = 4                # Множественный выбор / multiple choice
    open_question = 7                  # Открытый вопрос / open-ended text
    ranking = 8                        # Ранжирование / ranking
    slider = 9                         # Ползунок / slider
    multiple_choice_per_row = 10       # Множественный выбор по строке / multiple choice per row (matrix)
    info_material = 11                 # Ознакомительный материал / informational, no answer
    email_request = 12                 # Запрос почты / email capture


class Measures(StrEnum):
    """Statistical measurement level of a question's answers."""
    nominal = "nominal"
    scale = "scale"
    ordinal = "ordinal"


class InputValidations(StrEnum):
    """
    Validation/input-mask applied to free-text answers. Values that start
    with ``mask|`` encode the input mask shown to respondents (``9`` = digit
    placeholder); other values are named validators applied server-side.
    """
    text = "text"
    email = "email"
    number = "number"
    date_time = "mask|99.99.99 99:99"
    date = "mask|99.99.99"
    time = "mask|99:99"
    date_time_from_to = "mask|99.99.99 99:99 до 99.99.99 99:99"
    date_from_to = "mask|99.99.99 до 99.99.99"
    time_from_to = "mask|99:99 до 99:99"
    phone = "mask|8 (999) 999-99-99"
    none = ""


def _none_to_empty_str(value: Any) -> Any:
    """Coerce a ``None`` API value to ``""`` (used as a pre-validator for text fields)."""
    return "" if value is None else value


class Answer(BaseModel):
    """A single answer option belonging to a :class:`Question`."""
    id: Optional[int] = None
    order: int
    title: str
    has_input: bool = False
    skip_randomize: bool = False
    exclude_answer: bool = False
    optional: bool = False
    question_id: int
    input_validation: InputValidations
    is_panel: bool = False

    _poll: Optional[Poll] = PrivateAttr(default=None)

    @field_validator("input_validation", "title", mode="before")
    @classmethod
    def handle_none(cls, v: Any) -> Any:
        return _none_to_empty_str(v)

    @property
    def human_title(self) -> str:
        """``title`` with the constructor's markup/placeholders resolved to plain text."""
        return parse_text(self.title)

    @property
    def display_answers(self):
        """Answer-display logic rules that reference this answer, via the owning poll."""
        if self._poll is None:
            return []
        return [da for da in self._poll.display_answers if da.answer_id == self.id]

    def dump_create_payload(self):
        """Use to filter fields in create answer request"""

        """Use to filter Answer fields in create question request"""
        fields = {
            "order",
            "title",
            "has_input",
            "skip_randomize",
            "exclude_answer",
            "optional",
            "question_id",
            "input_validation",
        }
        return self.model_dump(include=fields)


class ChildQuestion(BaseModel):
    """
    Common question schema shared by a top-level :class:`Question` and the
    nested sub-questions found in ``Question.children`` (e.g. rows of a
    matrix/table question). ``Question`` extends this with ``answers`` and
    its own ``children`` list.
    """
    id: Optional[int] = None
    parent_id: Optional[int] = None
    order: int
    title: str
    answer_type: str = ""
    condition_type: str = ""
    measure: Measures
    type_id: AnswerTypes
    max_answer: int
    min_answer: int
    status_id: int = 1  # ?
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    optional: bool = False
    has_input: bool = False
    input_validation: InputValidations = InputValidations.none
    randomized: bool = False
    transpose: bool = False
    display_labels: bool = False
    children_randomized: bool = False
    is_panel: bool = False

    # NOTE: `init=False` only affects pydantic *dataclasses*; on a plain
    # BaseModel it is silently ignored, so `ChildQuestion(block_id=..., ...)`
    # will still work. These are populated by PollResource.get_poll_structure
    # after the fact (see the block/question wiring in client.py), not
    # from the raw API payload, but the constructor won't enforce that.
    block_id: int = Field(default=0, init=False)
    children: List[ChildQuestion] = Field(default_factory=list, init=False)

    _poll: Optional[Poll] = PrivateAttr(default=None)
    _poll_order: Optional[float | int] = PrivateAttr(default=0)  # unnested order in poll
    _parent_question: Optional[Question] = PrivateAttr(default=None)

    @property
    def poll_order(self) -> Optional[float | int]:
        return self._poll_order

    @field_validator("input_validation", mode="before")
    @classmethod
    def handle_none(cls, v: Any) -> Any:
        return _none_to_empty_str(v)

    @property
    def human_title(self) -> str:
        """``title`` with the constructor's markup/placeholders resolved to plain text."""
        return parse_text(self.title)

    @property
    def jumps(self):
        """Jump (skip-logic) rules that reference this question, via the owning poll."""
        if self._poll is None:
            return []
        return [jump for jump in self._poll.jumps if jump.question_id == self.id]

    @property
    def displays(self):
        """Question-display logic rules that reference this question, via the owning poll."""
        if self._poll is None:
            return []
        return [display for display in self._poll.displays if display.question_id == self.id]

    @property
    def display_answers(self):
        """Answer-display logic rules that reference this question as their trigger, via the owning poll."""
        if self._poll is None:
            return []
        return [da for da in self._poll.display_answers if da.reference_question_id == self.id]

    def dump_create_payload(self):
        """Use to filter fields in create question request"""
        fields = {
            "block_id",
            "children",
            "children_randomized",
            "display_labels",
            "is_panel",
            "max_answer",
            "measure",
            "min_answer",
            "optional",
            "order",
            "randomized",
            "status_id",
            "title",
            "transpose",
            "type_id"
        }
        return self.model_dump(include=fields)


class Question(ChildQuestion):
    """
    A top-level poll question. Adds ``answers`` and (for matrix/table-style
    questions) nested ``children`` sub-questions on top of the common
    :class:`ChildQuestion` schema.
    """
    answers: Optional[List[Answer]] = Field(default_factory=list)
    children: Optional[List[ChildQuestion]] = Field(default_factory=list)

    parent_id: int = 0  # for a child question; 0 for a top-level question
    block_id: Optional[int] = None

    _answers_by_id: dict[int, Answer] = PrivateAttr(default_factory=dict)
    _str_template: str = PrivateAttr(default="Вопрос будет показан, если {conditions}.")
    # ^ "The question will be shown if {conditions}." - used elsewhere to render logic as text.

    @field_validator("answers", mode="after")
    @classmethod
    def sort_answers(cls, v: Optional[List[Answer]]) -> Optional[List[Answer]]:
        if v is None:
            return list()

        if isinstance(v, list):
            return sorted(v, key=lambda answer: answer.order)
        return v

    def _rebuild_index(self, index_name: str, collection_name: str) -> None:
        """Rebuild a private ``{item.id: item}`` lookup from a (possibly ``None``) list field."""
        setattr(
            self,
            index_name,
            {item.id: item for item in getattr(self, collection_name) or []},
        )

    @model_validator(mode="after")
    def index_answers(self) -> Question:
        self._rebuild_index(index_name="_answers_by_id", collection_name="answers")
        return self

    def get_answer_by_id(self, item_id: int) -> Optional[Answer]:
        """Look up one of this question's answers by id, or ``None`` if not found."""
        return self._answers_by_id.get(item_id)


class QuestionInclude(StrEnum):
    """Fields (including dotted nested-children paths) selectable via ``includes``."""
    type_id = "type_id"
    answers = "answers"
    id = "id"
    title = "title"
    block_id = "block_id"
    order = "order"
    optional = "optional"
    max_answer = "max_answer"
    min_answer = "min_answer"
    has_input = "has_input"
    children = "children"
    children_type_id = "children.type_id"
    children_answers = "children.answers"


# A tuple, not a list: reused as a mutable-default-argument-style value
# elsewhere (e.g. QuestionResource.get_block_question/get_poll_questions in
# client.py), and a plain list there would be a shared, in-place-mutable
# default across calls.
ALL_QUESTION_INCLUDES: Tuple[QuestionInclude, ...] = tuple(QuestionInclude)


class GetBlockQuestionPayload(BaseModel):
    """Request body for listing the questions of a block."""
    model_config = ConfigDict(extra="forbid")

    block_id: int = Field(..., ge=1)
    includes: list[QuestionInclude] = Field(default_factory=lambda: list(ALL_QUESTION_INCLUDES))


class GetPollQuestionPayload(BaseModel):
    """Request body for listing every question of a poll (across all blocks)."""
    model_config = ConfigDict(extra="forbid")

    poll_id: int = Field(..., ge=1)
    includes: list[QuestionInclude] = Field(default_factory=lambda: list(ALL_QUESTION_INCLUDES))


