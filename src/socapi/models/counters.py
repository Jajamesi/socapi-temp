from enum import IntEnum

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from .logic import InternalCondition

class PredicateTypes(IntEnum):
    selected = 1
    not_selected = 2
    answered = 3
    unanswered = 4

class Predicate(BaseModel):
    counter_id: int
    counter_condition_id: int
    predicate_id: PredicateTypes
    poll_id: int
    condition: InternalCondition # wtf?
    deleted_at: Optional[datetime] = None

class Condition(BaseModel):
    id: int
    counter_id: int
    question_id: int
    answer_ids: Optional[List[int]]
    logic_join_condition: InternalCondition
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    deleted_at: Optional[datetime] = None


    # add validation based on predicate


class Counter(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    hits: int = 0
    order: int
    quota: int = 0
    is_disabled: bool = False
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    deleted_at: Optional[datetime] = None
    conditions: Optional[List[Condition]] = None
    source_ids: Optional[List[int]] = Field(default=[])