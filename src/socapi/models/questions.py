from typing import Optional, List, Any
from datetime import datetime
from enum import StrEnum, IntEnum
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


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
    ordered="ordered"


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


class ChildQuestion(BaseModel):
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
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
    status_id: int = 1

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



class Question(ChildQuestion):

    answers: Optional[List[Answer]] = None
    children: Optional[List[ChildQuestion]] = Field(default_factory=list)

    parent_id: int = 0  # for children question otherwise 0
    block_id: Optional[int] = None