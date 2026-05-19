from typing import Optional, List, Any
from datetime import datetime
from enum import IntEnum, StrEnum
from pydantic import BaseModel, Field

class Comparator(IntEnum):
    LESS_THAN = 0
    GREATER_THAN = 1

class JoinCondition(IntEnum):
    LESS_THAN = 0
    GREATER_THAN = 1

class InternalCondition(StrEnum):
    OR = "OR"
    AND = "AND"


class Logic(BaseModel):
    id: int
    poll_id: int
    reference_question_id: int

    comparator_id: int
    join_condition_id: int

    disabled: bool

    internal_condition: str

    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    reference_answer_id: list[int] = Field(default_factory=list)
    reference_answer_value: list[str] = Field(default_factory=list)

# answer_id

class Jump(Logic):
    block_id: Optional[int] = None
    question_id: int

    target_block_id: Optional[int] = None
    target_question_id: Optional[int] = None
    target_page_id: Optional[int] = None


class Display(Logic):
    block_id: Optional[int] = None
    question_id: int

    target_block_id: Optional[int] = None
    target_question_id: Optional[int] = None
    target_page_id: Optional[int] = None

class DisplayAnswers(Logic):
    answer_id: int