from typing import Optional, List, Any, TYPE_CHECKING
if TYPE_CHECKING:
    from .polls import Poll
from datetime import datetime
from enum import IntEnum, StrEnum
from pydantic import BaseModel, Field, model_validator, PrivateAttr


class Comparator(IntEnum):
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

COMPARATOR_MAPPING = {
    Comparator.IS_SELECTED: "выбрано",
    Comparator.IS_NOT_SELECTED: "не выбрано",
    Comparator.IS_ANSWERED: "отвечено",
    Comparator.IS_NOT_ANSWERED: "не отвечено",
    Comparator.CONTAINS: "содержит",
    Comparator.EQUAL: "равнозначно",
    Comparator.STARTS_WITH: "начинается с",
    Comparator.ENDS_WITH: "заканчивается",
    Comparator.EQUAL_NUM: "равно",
    Comparator.LESS_THAN: "меньше",
    Comparator.GREATER_THAN: "больше",
    Comparator.IS_ANSWERED_TEXT: "IS_ANSWERED_TEXT",
    Comparator.IS_NOT_ANSWERED_TEXT: "IS_NOT_ANSWERED_TEXT",
}

class JoinCondition(IntEnum):
    OR = 1
    AND = 2

class InternalCondition(StrEnum):
    OR = "OR"
    AND = "AND"

class Logic(BaseModel):
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

    _poll: Optional['Poll'] = PrivateAttr(default=None)


class Jump(Logic):
    block_id: Optional[int] = None
    question_id: int

    target_block_id: Optional[int] = None
    target_question_id: Optional[int] = None
    target_page_id: Optional[int] = None

    _str_template: str = PrivateAttr(default="Если {conditions} переход на {tartet_type} {target}.")

    def to_str(self):
        pass

    @model_validator(mode='before')
    @classmethod
    def validate_targets(cls, data: Any) -> Any:
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
    block_id: Optional[int] = None
    question_id: int

    target_block_id: Optional[int] = None
    target_question_id: Optional[int] = None
    target_page_id: Optional[int] = None

    _str_template: str = PrivateAttr(default="в вопросе {reference_question_order} "
                                             "{comparator} "
                                             "ответ {reference_answers}")

    def human_display(self):

        reference_question = self._poll.get_question_by_id(self.reference_question_id)

        if self.reference_answer_id:
            reference_answer = sorted([reference_question.get_answer_by_id(a).order for a in self.reference_answer_id])
        elif self.reference_answer_value:
            reference_answer = self.reference_answer_value
        else:
            reference_answer = None

        return self._str_template.format(
            reference_question_order = reference_question.poll_order,
            comparator = COMPARATOR_MAPPING.get(self.comparator_id),
            reference_answers = reference_answer,
        )


class DisplayAnswers(Logic):
    answer_id: int


class GetLogicPayload(BaseModel):
    poll_id: int