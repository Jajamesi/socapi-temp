from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from polls import Poll

from typing import Optional, List, Any
from datetime import datetime
from enum import StrEnum, IntEnum
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, field_validator, model_validator
from uuid import UUID
from ..text_worker import parse_text

class AnswerTypes(IntEnum):
    single_answer = 1                  # Один ответ
    dropdown = 2                       # Выпадающий список
    single_answer_per_row = 3          # Один ответ по строке
    multiple_choice = 4                # Множественный выбор
    open_question = 7                  # Открытый вопрос
    ranking = 8                        # Ранжирование
    slider = 9                         # Ползунок
    multiple_choice_per_row = 10       # Множественный выбор по строке
    info_material = 11                 # Ознакомительный материал
    email_request = 12                 # Запрос почты


class Measures(StrEnum):
    nominal="nominal"
    scale="scale"
    ordinal="ordinal"


class InputValidations(StrEnum):
    text="text"
    email="email"
    number="number"
    date_time="mask|99.99.99 99:99"
    date = "mask|99.99.99"
    time="mask|99:99"
    date_time_from_to="mask|99.99.99 99:99 до 99.99.99 99:99"
    date_from_to = "mask|99.99.99 до 99.99.99"
    time_from_to = "mask|99:99 до 99:99"
    phone="mask|8 (999) 999-99-99"
    none=""


class Answer(BaseModel):
    id: Optional[int]=None
    order: int
    title: str
    has_input: bool = False
    skip_randomize: bool = False
    exclude_answer: bool = False
    optional: bool = False
    question_id: int
    input_validation: InputValidations
    is_panel: bool = False

    _poll: Optional['Poll'] = PrivateAttr(default=None)

    @field_validator('input_validation', 'title' , mode='before')
    @classmethod
    def handle_none(cls, v):
        if v is None:
            return ''
        return v

    @property
    def human_title(self) -> str:
        return parse_text(self.title)


    @property
    def display_answers(self):
        if self._poll is None:
            return []
        return [l for l in self._poll.display_answers if l.answer_id == self.id]


class ChildQuestion(BaseModel):
    created_at: Optional[datetime] = None
    title: str
    answer_type: str = ""
    condition_type: str = ""
    id: Optional[int] = None
    parent_id: Optional[int] = None
    updated_at: Optional[datetime] = None
    measure: Measures
    type_id: AnswerTypes
    max_answer: int
    min_answer: int
    order: int
    status_id: int = 1 # ?

    _poll: Optional['Poll'] = PrivateAttr(default=None)

    optional: bool  = False
    has_input: bool  = False
    input_validation: InputValidations = InputValidations.none
    randomized: bool = False
    transpose: bool = False
    display_labels: bool = False
    children_randomized: bool = False
    is_panel: bool = False

    block_id: int = Field(default=0, init=False)
    children: List = Field(default_factory=list, init=False)


    @field_validator('input_validation', mode='before')
    @classmethod
    def handle_none(cls, v):
        if v is None:
            return ''
        return v

    @property
    def human_title(self) -> str:
        return parse_text(self.title)


    @property
    def jumps(self):
        if self._poll is None:
            return []
        return [l for l in self._poll.jumps if l.question_id == self.id]

    @property
    def displays(self):
        if self._poll is None:
            return []
        return [l for l in self._poll.displays if l.question_id == self.id]

    @property
    def display_answers(self):
        if self._poll is None:
            return []
        return [l for l in self._poll.display_answers if l.reference_question_id == self.id]





class Question(ChildQuestion):

    answers: Optional[List[Answer]] = None
    children: Optional[List[ChildQuestion]] = Field(default_factory=list)

    parent_id: int = 0  # for children question otherwise 0
    block_id: Optional[int] = None

    _poll_order: Optional[int] = PrivateAttr(default=0) # unnested order in poll
    _answers_by_id: dict[int, Question] = PrivateAttr(default_factory=dict)

    _str_template: str = PrivateAttr(default="Вопрос будет показан, если {conditions}.")

    @field_validator('answers', mode='after')
    @classmethod
    def sort_answers(cls, v):
        if isinstance(v, list):
            return sorted(v, key=lambda x: x.order)
        return v

    def _rebuild_index(self, index_name: str, collection_name: str):
        setattr(
            self,
            index_name,
            {
                item.id: item
                for item in getattr(self, collection_name)
            },
        )

    @model_validator(mode="after")
    def index_answers(self):
        self._rebuild_index(index_name="_answers_by_id", collection_name="answers")
        return self

    @property
    def poll_order(self):
        return self._poll_order

    def get_answer_by_id(self, item_id: int):
        return self._answers_by_id.get(item_id)


class QuestionInclude(StrEnum):
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

ALL_QUESTION_INCLUDES = list(QuestionInclude)

class GetBlockQuestionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: int = Field(..., ge=1)
    includes: list[QuestionInclude] = Field(default_factory=lambda: ALL_QUESTION_INCLUDES.copy())


class GetPollQuestionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    poll_id: int = Field(..., ge=1)
    includes: list[QuestionInclude] = Field(default_factory=lambda: ALL_QUESTION_INCLUDES.copy())