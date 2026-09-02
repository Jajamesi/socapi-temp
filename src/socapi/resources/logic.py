from __future__ import annotations

from typing import Optional, Any, TYPE_CHECKING

from .questions import ChildQuestion, Question

if TYPE_CHECKING:
    from .polls import Poll
from datetime import datetime
from enum import IntEnum, StrEnum
from pydantic import BaseModel, Field, ConfigDict, model_validator, PrivateAttr


class Comparator(IntEnum):
    """How a logic rule's reference answer(s)/value is compared against a respondent's answer."""
    IS_SELECTED = 1
    IS_NOT_SELECTED = 2
    IS_ANSWERED = 3
    IS_NOT_ANSWERED = 4

    CONTAINS = 5
    EQUAL = 6
    STARTS_WITH = 7
    ENDS_WITH = 8

    EQUAL_NUM = 9
    LESS_THAN = 10
    GREATER_THAN = 11

    IS_ANSWERED_TEXT = 12
    IS_NOT_ANSWERED_TEXT = 13


# Human-readable (Russian) rendering of each Comparator, for Logic.human_display().
COMPARATOR_TEMPLATES: dict[Comparator, str] = {
    Comparator.IS_SELECTED: "выбран ответ {reference_answers}",
    Comparator.IS_NOT_SELECTED: "не выбран ответ {reference_answers}",
    Comparator.IS_ANSWERED: "отвечено",
    Comparator.IS_NOT_ANSWERED: "не отвечено",
    Comparator.CONTAINS: "содержит {reference_answers}",
    Comparator.EQUAL: "равнозначно {reference_answers}",
    Comparator.STARTS_WITH: "начинается с {reference_answers}",
    Comparator.ENDS_WITH: "заканчивается {reference_answers}",
    Comparator.EQUAL_NUM: "равно {reference_answers}",
    Comparator.LESS_THAN: "меньше {reference_answers}",
    Comparator.GREATER_THAN: "больше {reference_answers}",
    Comparator.IS_ANSWERED_TEXT: "IS_ANSWERED_TEXT {reference_answers}",  # TODO: placeholder text
    Comparator.IS_NOT_ANSWERED_TEXT: "IS_NOT_ANSWERED_TEXT {reference_answers}",  # TODO: placeholder text
}


class JoinCondition(IntEnum):
    """How separate logic rules are combined with each other (top-level AND/OR)."""
    OR = 1
    AND = 2


JOIN_CONDITION_TO_STR = {
    JoinCondition.OR: "ИЛИ",
    JoinCondition.AND: "И",
}


class InternalCondition(StrEnum):
    """
    How the reference answers *within* a single logic rule/condition are
    combined with each other (e.g. "answer A AND answer B both selected"),
    as distinct from :class:`JoinCondition`, which combines separate rules.
    """
    OR = "OR"
    AND = "AND"


class Logic(BaseModel):
    """Base shape shared by all logic rule types (jumps, question/answer display)."""
    id: int
    poll_id: int
    reference_question_id: int

    comparator_id: Comparator
    join_condition_id: JoinCondition

    disabled: bool

    internal_condition: InternalCondition

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    reference_answer_id: list[int] = Field(default_factory=list)
    reference_answer_value: list[str] = Field(default_factory=list)

    _poll: Optional[Poll] = PrivateAttr(default=None)

    _str_template: str = PrivateAttr(default="в вопросе {reference_question_order} {comparator_reference}.")

    def human_display(self, show_join: bool = True) -> str:
        """
        Render this rule as a human-readable (Russian) sentence.

        :param show_join: currently has no effect - the base template
            doesn't include a join-condition placeholder, so the computed
            join text is discarded. Kept for API-compatibility with the
            eventual intended behavior; not yet implemented.
        """
        if self._poll is None:
            raise RuntimeError(
                f"{type(self).__name__}._poll is not set - human_display() needs the "
                "owning Poll to look up the reference question."
            )

        reference_question = self._poll.get_question_by_id(self.reference_question_id)

        # Exact-type check (not isinstance): Question subclasses ChildQuestion,
        # so isinstance(x, ChildQuestion) would also match a real Question and
        # misclassify it - we need to know which concrete type this is.
        if type(reference_question) is ChildQuestion:
            answer_source_question = reference_question._parent_question
        elif type(reference_question) is Question:
            answer_source_question = reference_question
        else:
            raise ValueError("Incorrect reference question type")

        if self.reference_answer_id:
            reference_answer = sorted(
                answer.order
                for answer_id in self.reference_answer_id
                if (answer := answer_source_question.get_answer_by_id(answer_id)) is not None
            )
        elif self.reference_answer_value:
            reference_answer = self.reference_answer_value
        else:
            reference_answer = None

        comparator_template = COMPARATOR_TEMPLATES.get(
            self.comparator_id, f"<no template for {self.comparator_id.name}>"
        )

        return self._str_template.format(
            reference_question_order=reference_question.poll_order,
            comparator_reference=comparator_template.format(reference_answers=reference_answer),
            join_condition=JOIN_CONDITION_TO_STR.get(self.join_condition_id),
        )


class Jump(Logic):
    """A skip-logic rule: if its condition holds, the respondent jumps to a target block/question/page."""
    block_id: Optional[int] = None
    question_id: int

    target_block_id: Optional[int] = None
    target_question_id: Optional[int] = None
    target_page_id: Optional[int] = None

    _str_template: str = PrivateAttr(default="Если {conditions} переход на {target_type} {target}.") # TODO

    def to_str(self) -> str:
        """Render this jump as a human-readable sentence. Not implemented yet."""
        raise NotImplementedError

    @model_validator(mode="before")
    @classmethod
    def validate_targets(cls, data: Any) -> Any:
        """Exactly one of the three target_* fields must be set - a jump needs exactly one destination."""
        targets = (
            data.get("target_block_id"),
            data.get("target_question_id"),
            data.get("target_page_id"),
        )

        if sum(target is not None for target in targets) != 1:
            raise ValueError(
                "Exactly one of target_block_id, target_question_id, "
                "target_page_id must be provided"
            )

        return data


class Display(Logic):
    """A display/visibility rule: if its condition holds, a target block/question/page is shown."""
    block_id: Optional[int] = None
    question_id: int

    target_block_id: Optional[int] = None
    target_question_id: Optional[int] = None
    target_page_id: Optional[int] = None

    # TODO: Display doesn't yet have its own human_display() override /
    # _str_template - it currently just inherits Logic's, which is worded
    # for jump-style rules ("in question X ...") rather than display rules.


class DisplayAnswers(Logic):
    """A display/visibility rule scoped to a single answer option rather than a whole question."""
    answer_id: int


class GetLogicPayload(BaseModel):
    """Request body shared by the jump/display/answer-display logic list endpoints."""
    model_config = ConfigDict(extra="forbid")

    poll_id: int = Field(..., ge=1)