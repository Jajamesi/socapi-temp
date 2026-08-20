from typing import Optional, List, Any
from datetime import datetime
from enum import IntEnum, StrEnum
from pydantic import BaseModel, Field, model_validator



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


class Jump(Logic):
    block_id: Optional[int] = None
    question_id: int

    target_block_id: Optional[int] = None
    target_question_id: Optional[int] = None
    target_page_id: Optional[int] = None

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


class DisplayAnswers(Logic):
    answer_id: int


class GetLogicPayload(BaseModel):
    poll_id: int