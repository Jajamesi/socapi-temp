from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only needed for the `_poll` backref type hint; importing at runtime
    # would create a circular import with polls.py (Poll owns Questions).
    from .polls import Poll
from .logic import DisplayAnswers, Jump, Display, Comparator, JoinCondition, InternalCondition
from .pages import Page

from typing import Optional, List, Tuple, Any, Collection, Iterable, Sequence, Union, Generator
from datetime import datetime
from enum import StrEnum, IntEnum
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, field_validator, model_validator

from ..text_worker import parse_text, md_to_html
from ..utils import increment


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


def _answers_source(question: "ChildQuestion") -> List["Answer"]:
    """
    Answers a logic rule can reference for ``question``. A matrix row
    (:class:`ChildQuestion`) has no answers of its own - it shares the
    answers of its parent question.
    """
    if isinstance(question, Question):
        return question.answers or []
    parent = question._parent_question
    return (parent.answers or []) if parent is not None else []


def _resolve_reference_answers(
        reference_question: "ChildQuestion",
        orders: int | Sequence[int] | None,
) -> List[int]:
    """
    Translate human answer positions (``order``, 1-based) of
    ``reference_question`` into the answers' ids.

    :param orders: one position, several positions, or ``None`` (no answers,
        e.g. for ``Comparator.IS_ANSWERED``).
    :raises ValueError: if a position doesn't exist on the reference question.
    """
    if orders is None:
        return []
    if isinstance(orders, int):
        orders = [orders]

    by_order = {answer.order: answer for answer in _answers_source(reference_question)}
    ids: List[int] = []
    for order in orders:
        if order not in by_order:
            raise ValueError(
                f"Question {reference_question.title!r} has no answer with order={order}; "
                f"available: {sorted(by_order)}"
            )
        ids.append(by_order[order].id)
    return ids


class Answer(BaseModel):
    """A single answer option belonging to a :class:`Question`."""
    id: Optional[int] = None
    order: int = 0
    title: str
    has_input: bool = False
    skip_randomize: bool = False
    exclude_answer: bool = False
    optional: bool = False
    question_id: Optional[int] = None
    input_validation: InputValidations = InputValidations.none
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

    def add_display(
            self,
            reference_question: "ChildQuestion | Question",
            comparator: Comparator,
            reference_answer_order: int | Sequence[int] | None = None,
            join_condition: JoinCondition = JoinCondition.OR,
            internal_condition: InternalCondition = InternalCondition.OR,
            reference_answer_value: Sequence[str] | None = None,
    ) -> DisplayAnswers:
        """
        Show this answer only if the condition on ``reference_question`` holds.

        Requires the answer to be attached to a poll (add its question to a
        block first). Returns the created rule, also stored in ``poll.display_answers``.
        """
        if self._poll is None:
            raise ValueError("Attach the question to a block of a poll before adding logic to its answers.")

        rule = DisplayAnswers(
            poll_id=self._poll.id or 0,  # real id is substituted on upload
            answer_id=self.id,
            reference_question_id=reference_question.id,
            comparator_id=comparator,
            join_condition_id=join_condition,
            internal_condition=internal_condition,
            disabled=False,
            reference_answer_id=_resolve_reference_answers(reference_question, reference_answer_order),
            reference_answer_value=list(reference_answer_value or []),
        )
        self._poll._attach_logic(rule, self._poll.display_answers)
        return rule


class ChildQuestion(BaseModel):
    """
    Common question schema shared by a top-level :class:`Question` and the
    nested sub-questions found in ``Question.children`` (e.g. rows of a
    matrix/table question). ``Question`` extends this with ``answers`` and
    its own ``children`` list.
    """
    id: Optional[int] = None
    parent_id: Optional[int] = None
    order: int = 0
    title: str
    answer_type: str = ""
    condition_type: str = ""
    measure: Measures = Measures.nominal
    type_id: AnswerTypes
    max_answer: int = 1
    min_answer: int = 1
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
    _id_generator: Generator[int, None, None] = PrivateAttr(default=None)

    # @model_validator(mode='before')
    # @classmethod
    # def validate_min_max_answers(cls, **v):
    #     pass


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
        dump = self.model_dump(include=fields)
        dump["title"] = md_to_html(dump["title"])
        return  dump

    @property
    def is_child(self):
        return True


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

    @property
    def is_child(self):
        return False

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

    @field_validator('answers', mode="before")
    @classmethod
    def order_answers(cls, answers: Iterable[Answer | dict] | None) -> Iterable[Answer | dict] | None:
        """Give answers without an ``order`` their 1-based position. Accepts models and raw API dicts."""
        if answers is None:
            return answers
        result = []
        for i, answer in enumerate(answers, start=1):
            if isinstance(answer, dict):
                answer = {**answer, "order": answer.get("order") or i}
            else:
                answer.order = answer.order or i
            result.append(answer)
        return result

    def dump_create_payload(self):
        """Create-question payload; matrix rows are nested without their temporary ids."""
        payload = super().dump_create_payload()
        payload["children"] = [child.dump_create_payload() for child in self.children or []]
        return payload

    # ------------------------------------------------------------------
    # Draft building (poll created from scratch, not yet uploaded).
    # Draft items get temporary negative ids from the poll; real ids are
    # substituted by ``PollResource.upload_poll``.
    # ------------------------------------------------------------------

    def _require_poll(self) -> Poll:
        if self._poll is None:
            raise ValueError("Add this question to a block of a poll first (block.add_question(...)).")
        return self._poll

    def _adopt_answer(self, answer: Answer) -> None:
        """Give ``answer`` a temporary id and wire it to this question and its poll."""
        poll = self._require_poll()
        answer.id = poll._next_id()
        answer.question_id = self.id
        answer._poll = poll

    def _adopt_child(self, child: ChildQuestion) -> None:
        """Give a matrix row a temporary id and wire it to this question and its poll."""
        poll = self._require_poll()
        child.id = poll._next_id()
        child.parent_id = self.id
        child.block_id = self.block_id or 0
        child._poll = poll
        child._parent_question = self

    def add_answer(self, answer: Answer) -> Answer:
        """Append ``answer`` to this (already attached) question."""
        self._require_poll()
        answer.order = len(self.answers) + 1
        self._adopt_answer(answer)
        self.answers.append(answer)
        self._poll._refresh()
        return answer

    def add_child(self, child: ChildQuestion) -> ChildQuestion:
        """Append a matrix row to this (already attached) question."""
        self._require_poll()
        child.order = len(self.children) + 1
        self._adopt_child(child)
        self.children.append(child)
        self._poll._refresh()
        return child

    def add_display(
            self,
            reference_question: ChildQuestion | Question,
            comparator: Comparator,
            reference_answer_order: int | Sequence[int] | None = None,
            join_condition: JoinCondition = JoinCondition.OR,
            internal_condition: InternalCondition = InternalCondition.OR,
            reference_answer_value: Sequence[str] | None = None,
    ) -> Display:
        """
        Show this question only if the condition on ``reference_question`` holds.

        :param reference_answer_order: 1-based position(s) of the answer(s)
            of ``reference_question`` the comparator is checked against.
        :param reference_answer_value: free-text values, for text comparators.
        :return: the created rule, also stored in ``poll.displays``.
        """
        poll = self._require_poll()
        rule = Display(
            poll_id=poll.id or 0,  # real id is substituted on upload
            question_id=self.id,
            reference_question_id=reference_question.id,
            comparator_id=comparator,
            join_condition_id=join_condition,
            internal_condition=internal_condition,
            disabled=False,
            reference_answer_id=_resolve_reference_answers(reference_question, reference_answer_order),
            reference_answer_value=list(reference_answer_value or []),
        )
        poll._attach_logic(rule, poll.displays)
        return rule

    def add_jump(
            self,
            target: Question | Page,
            comparator: Comparator,
            reference_answer_order: int | Sequence[int] | None = None,
            reference_question: ChildQuestion | None = None,
            join_condition: JoinCondition = JoinCondition.OR,
            internal_condition: InternalCondition = InternalCondition.OR,
            reference_answer_value: Sequence[str] | None = None,
    ) -> Jump:
        """
        After this question, jump to ``target`` if the condition holds.

        :param target: a question of the same poll, or an existing (server
            side) :class:`Page` such as the finish / disqualification page.
        :param reference_question: question whose answer is checked;
            defaults to this question.
        :return: the created rule, also stored in ``poll.jumps``.
        """
        poll = self._require_poll()
        reference_question = reference_question or self

        targets: dict[str, int] = {}
        if isinstance(target, Question):
            targets["target_question_id"] = target.id
        elif isinstance(target, Page):
            targets["target_page_id"] = target.id
        else:
            raise TypeError(f"Jump target must be a Question or a Page, got {type(target).__name__}")

        rule = Jump(
            poll_id=poll.id or 0,  # real id is substituted on upload
            question_id=self.id,
            reference_question_id=reference_question.id,
            comparator_id=comparator,
            join_condition_id=join_condition,
            internal_condition=internal_condition,
            disabled=False,
            reference_answer_id=_resolve_reference_answers(reference_question, reference_answer_order),
            reference_answer_value=list(reference_answer_value or []),
            **targets,
        )

        poll._attach_logic(rule, poll.jumps)
        return rule



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


