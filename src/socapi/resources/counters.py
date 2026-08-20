from enum import IntEnum

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from .logic import InternalCondition, JoinCondition


class PredicateTypes(IntEnum):
    selected = 1
    not_selected = 2
    answered = 3
    unanswered = 4


class CounterPredicateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    predicate_id: int = Field(..., ge=1)
    condition: InternalCondition


class CounterConditionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logic_join_condition: InternalCondition
    question_id: int = Field(..., ge=1)
    predicate: CounterPredicateRequest
    answer_ids: list[int] = Field(default_factory=list)

class CreateCounterPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    quota: int = Field(..., ge=0)
    description: str
    source_ids: list[int] = Field(default_factory=list)
    poll_id: int = Field(..., ge=1)
    is_disabled: bool = False
    conditions: list[CounterConditionRequest] = Field(default_factory=list)


class GetCounterPayload(BaseModel):
    poll_id: int


class CounterPredicate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counter_id: int
    counter_condition_id: int
    predicate_id: int
    poll_id: int
    condition: InternalCondition
    deleted_at: datetime | None = None


class CounterCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    counter_id: int
    question_id: int
    answer_ids: list[int]
    logic_join_condition: InternalCondition
    created_at: datetime
    deleted_at: datetime | None = None
    predicate: CounterPredicate


class CounterSource(BaseModel):
    """
    Шо это, где это? Легаси какое-то
    """
    model_config = ConfigDict(extra="forbid")
    pass


class Counter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    poll_id: int
    name: str
    description: str
    hits: int
    order: int
    quota: int
    is_disabled: bool
    created_at: datetime
    deleted_at: datetime | None = None
    conditions: list[CounterCondition] | None = None
    source_ids: list[int] | None = None
    sources: list[CounterSource] | None = None
