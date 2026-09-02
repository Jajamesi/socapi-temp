from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from .logic import InternalCondition


class PredicateTypes(IntEnum):
    """Kind of condition a counter predicate checks against a question's answers."""
    selected = 1
    not_selected = 2
    answered = 3
    unanswered = 4


class CounterPredicateRequest(BaseModel):
    """One predicate (e.g. "answer X selected") inside a counter condition, for create/update calls."""
    model_config = ConfigDict(extra="forbid")

    predicate_id: int = Field(..., ge=1)
    condition: InternalCondition


class CounterConditionRequest(BaseModel):
    """One condition (a question + predicate + candidate answers) inside a counter, for create/update calls."""
    model_config = ConfigDict(extra="forbid")

    logic_join_condition: InternalCondition
    question_id: int = Field(..., ge=1)
    predicate: CounterPredicateRequest
    answer_ids: list[int] = Field(default_factory=list)


class CreateCounterPayload(BaseModel):
    """Request body for creating (or fully redefining) a counter."""
    model_config = ConfigDict(extra="forbid")

    name: str
    quota: int = Field(..., ge=0)
    description: str
    source_ids: list[int] = Field(default_factory=list)
    poll_id: int = Field(..., ge=1)
    is_disabled: bool = False
    conditions: list[CounterConditionRequest] = Field(default_factory=list)


class GetCounterPayload(BaseModel):
    """Request body for listing the counters of a poll."""
    model_config = ConfigDict(extra="forbid")

    poll_id: int = Field(..., ge=1)


class CounterPredicate(BaseModel):
    """One predicate inside a counter condition, as returned by the API."""
    model_config = ConfigDict(extra="forbid")

    counter_id: int
    counter_condition_id: int
    predicate_id: int
    poll_id: int
    condition: InternalCondition
    deleted_at: datetime | None = None


class CounterCondition(BaseModel):
    """One condition inside a counter, as returned by the API."""
    model_config = ConfigDict(extra="forbid")

    id: int
    counter_id: int
    question_id: int
    answer_ids: list[int]
    logic_join_condition: InternalCondition  # see the note in CounterConditionRequest above
    created_at: datetime
    deleted_at: datetime | None = None
    predicate: CounterPredicate


class CounterSource(BaseModel):
    """
    Шо это, где это? Легаси какое-то
    """
    pass


class Counter(BaseModel):
    """A poll counter (quota-style tally), as returned by the API."""
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