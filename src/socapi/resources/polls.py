from __future__ import annotations

from typing import Optional, List, Any, Literal, Generator, overload, Annotated
from datetime import datetime
from enum import IntEnum, StrEnum
from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator, PrivateAttr, AliasChoices
from uuid import UUID
from itertools import chain

from ..text_worker import parse_text, md_to_html

from .counters import Counter, CounterCondition
from . import logic, counters
from .pages import Page, PageData, PageType, PageTypeName, coerce_page_type
from .blocks import Block
from .sources import Source
from .questions import Question, ChildQuestion
from ..utils import is_draft_id
from .. import io

from dataclasses import dataclass, field
import ambers as am


class BackgroundColor(StrEnum):
    """Poll page background color preset."""
    LIGHT_BLUE = "#bdcff6"
    LIGHT_ORANGE = "#ffd1af"
    LIGHT_GREEN = "#b6ffb5"
    LIGHT_RED = "#ff7c7c"
    PURPLE = "#7059ff"
    NO_SET = ''


class Banner(StrEnum):
    """Poll header banner/illustration preset."""
    DEFAULT = "DEFAULT"
    HEAT_MAP_02 = "HEAT_MAP_02"
    HOMELESS_ANIMALS_AND_HUNT_01 = "HOMELESS_ANIMALS_AND_HUNT_01"
    INTERNET_SERVICES_01 = "INTERNET_SERVICES_01"
    PUBLIC_TRANSPORT_01 = "PUBLIC_TRANSPORT_01"
    ROADS_01 = "ROADS_01"
    REGION_CFO_01 = "REGION_CFO_01"
    REGION_DFO_01 = "REGION_DFO_01"
    REGION_PFO_01 = "REGION_PFO_01"
    REGION_SFO_01 = "REGION_SFO_01"
    REGION_SKFO_01 = "REGION_SKFO_01"
    REGION_SKFO_02 = "REGION_SKFO_02"
    REGION_SZFO_01 = "REGION_SZFO_01"
    REGION_UFO_01 = "REGION_UFO_01"
    REGION_URALFO_01 = "REGION_URALFO_01"
    NO_THEME_01 = "NO_THEME_01"
    ECOLOGY_01 = "ECOLOGY_01"
    DIGITAL_TECHNOLOGY_01 = "DIGITAL_TECHNOLOGY_01"
    NO_SET = ''


class PollStatus(IntEnum):
    """Lifecycle status of a poll."""
    ACTIVE = 1
    CLOSED = 4
    PUBLISHED = 3
    DELETED = 2


class PollType(IntEnum):
    """How the poll presents its questions to a respondent."""
    ALL_AT_ONCE = 1    # Отображение респонденту всех вопросов сразу / all questions on one screen
    BY_BLOCK = 2        # Отображение опроса по блокам / one block per screen
    ONE_QUESTION = 3     # Отображение опроса по одному вопросу / one question per screen

PollTypeName = Literal["all_at_once", "by_block", "one_question"]

def coerce_poll_type(value: "PollType | PollTypeName | int") -> PollType:
    """``"all_at_once"`` / ``PageType.ALL_AT_ONCE`` / ``1`` -> ``PollType.ALL_AT_ONCE``; ``ValueError`` for anything else."""
    if isinstance(value, str):
        try:
            return PollType[value.strip().upper()]
        except KeyError:
            pass
    else:
        try:
            return PollType(value)
        except ValueError:
            pass
    allowed = ", ".join(repr(t.name.lower()) for t in PageType)
    raise ValueError(f"Unknown poll type {value!r}; allowed: {allowed}")


class Poll(BaseModel):
    """
    Полный опрос (survey), включающий метаданные, блоки, вопросы, страницы,
    правила логики и счётчики.

    При создании и валидации ``Poll`` — через ``Poll(...)`` или
    ``Poll.model_validate(...)`` — модель автоматически связывает все вложенные
    объекты между собой. Устанавливаются обратные ссылки ``_poll`` для блоков,
    вопросов, ответов и правил логики, ``_parent_question`` для дочерних вопросов,
    а также порядок отображения ``_poll_order`` и внутренние индексы для быстрого
    поиска объектов по их ``id``.

    После создания ``Poll`` дополнительно вызывать методы привязки не требуется.
    Методы ``rebind_questions()``, ``rebind_logics()`` и ``rebind_blocks()``
    предназначены только для повторной синхронизации этих связей после
    последующего изменения соответствующих списков, например после изменения
    ``self.blocks`` непосредственно.

    Для создания опроса достаточно передать обязательные поля модели, в частности
    ``name``, ``user_id`` и ``type_id``. Остальные поля имеют значения по умолчанию
    или являются необязательными.

    Основные способы работы с содержимым опроса:

    - ``add_page(page)`` — добавить уже созданный объект ``Page``;
    - ``add_page(name=..., page_type=..., ...)`` — создать и добавить страницу
      непосредственно из аргументов;
    - аналогичные методы используются для добавления и связывания других
      составляющих опроса.

    При добавлении объектов ``Poll`` самостоятельно назначает необходимые
    идентификаторы, устанавливает обратные ссылки на себя и обновляет внутренние
    индексы.

    Private attributes (поля с префиксом ``_``) являются внутренним состоянием
    модели и не должны задаваться при создании ``Poll`` напрямую.
    """
    id: int | None = None
    uuid: UUID | None = None
    name: str
    title: str = Field(default="")
    description: str = Field(default="")
    created_at: Optional[datetime] = None
    user_id: int
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    status_id: PollStatus = Field(default=PollStatus.ACTIVE, description="Default state for created poll")
    status_updated_at: Optional[datetime] = None
    type_id: PollType | PollTypeName
    is_multiple: bool = True       # can be used several times
    can_cameback: bool = False     # almost never used as True
    track_repeats: bool = True     # almost never used as False
    field_date: Optional[datetime] = None  # ?
    banner: Banner = Field(default=Banner.DEFAULT)
    background: BackgroundColor = Field(default=BackgroundColor.LIGHT_BLUE)

    poll_responsible: Optional[int] = None

    meta: Optional[List[int] | int] = Field(default=[0])  # missing in poll/full
    counters: Optional[List[Counter]] = Field(default_factory=list)
    notify_flag: bool = False

    blocks: List[Block] = Field(default_factory=list)
    jumps: List[logic.Jump] = Field(default_factory=list)
    displays: List[logic.Display] = Field(default_factory=list)
    display_answers: List[logic.DisplayAnswers] = Field(default_factory=list)
    pages: List[Page] = Field(default_factory=list)

    sources: List[Source] = Field(default_factory=list)
    source_id: Optional[List[int]] = None
    state_id: int = 0
    # Shape unknown (like counters.CounterSource) - typed Any rather than
    # None so a future non-null value doesn't fail validation outright.
    logic_panel: Any = None  # what's this?
    language_id: int = 1  # Russian
    domain_id: int = 1

    # TODO: no `user` field yet - add `user: Optional[User] = None` here
    # once resources/user.py's User model is wired into this package.

    _question_counter: int = PrivateAttr(default=0)  # currently unused

    _question_by_id: dict[int, Question] = PrivateAttr(default_factory=dict)
    _children_by_id: dict[int, ChildQuestion] = PrivateAttr(default_factory=dict)
    _block_by_id: dict[int, Block] = PrivateAttr(default_factory=dict)
    _page_by_id: dict[int, Page] = PrivateAttr(default_factory=dict)
    _id_generator: Generator[int, None, None] = PrivateAttr(default=None)

    @property
    def human_description(self) -> str:
        """``description`` with the constructor's markup/placeholders resolved to plain text."""
        return parse_text(self.description)

    @property
    def len_question(self) -> int:
        """Total number of top-level questions across all blocks."""
        return sum(len(block.questions) for block in self.blocks)

    @model_validator(mode="after")
    def _bind_questions_to_poll(self) -> Poll:
        """Set ``_poll`` on every block/question/answer (for compatibility with e.g. ``question.jumps``)."""
        for block in self.blocks:
            block._poll = self
            for question in block.questions:
                question._poll = self
                for answer in question.answers or []:
                    answer._poll = self
        return self

    @field_validator('type_id', mode='before')
    @classmethod
    def validate_type_id(cls, value: str| int | PollType) -> PollType:
        return coerce_poll_type(value)

    @field_validator('meta', mode='before')
    @classmethod
    def validate_meta(cls, value: int | List[int]) -> List[int]:
        if isinstance(value, list):
            return value
        elif isinstance(value, int):
            return [value]


    @model_validator(mode="after")
    def _bind_child_to_parent(self) -> Poll:
        """Set ``_parent_question`` on every nested (matrix-row) child question."""
        for question in self.questions:
            for child in question.children:
                child._parent_question = question
        return self

    def rebind_questions(self) -> None:
        """Manually re-run :meth:`_bind_questions_to_poll` (already runs automatically on construction)."""
        self._bind_questions_to_poll()

    @model_validator(mode="after")
    def _bind_logics_to_poll(self) -> Poll:
        """Set ``_poll`` on every jump/display/display-answer logic rule."""
        for rules in (self.jumps, self.display_answers, self.displays):
            for rule in rules:
                rule._poll = self
        return self

    def rebind_logics(self) -> None:
        """Manually re-run :meth:`_bind_logics_to_poll` (already runs automatically on construction)."""
        self._bind_logics_to_poll()

    @model_validator(mode="after")
    def _bind_blocks_to_poll(self) -> Poll:
        """Set ``_poll`` on every block."""
        for block in self.blocks:
            block._poll = self
        return self

    def rebind_blocks(self) -> None:
        """Manually re-run :meth:`_bind_blocks_to_poll` (already runs automatically on construction)."""
        self._bind_blocks_to_poll()

    @field_validator('counters', mode='before')
    @classmethod
    def validate_counters(cls, value: None | int| List[int]) -> List[int]:
        if value is None:
            return []
        return value

    @model_validator(mode="after")
    def _bind_counters_to_poll(self) -> Poll:
        """Set ``_poll`` on every counter."""
        for counter in self.counters:
            counter._poll = self
        return self

    def rebind_counter(self) -> None:
        """Manually re-run :meth:`_bind_counters_to_poll` (already runs automatically on construction)."""
        self._bind_counters_to_poll()

    @property
    def questions(self) -> List[Question]:
        """All top-level questions across all blocks, in block order then question order."""
        return [
            question
            for block in sorted(self.blocks, key=lambda b: b.order)
            for question in sorted(block.questions, key=lambda q: q.order)
        ]

    @model_validator(mode="after")
    def count_questions(self) -> Poll:
        """
        Assign each top-level question a whole-number ``_poll_order`` (1, 2,
        3, ...) and each of its nested children a fractional order right
        after it (1.1, 1.2, ..., 2.1, ...), so sorting by ``_poll_order``
        gives the true respondent-facing sequence.
        """
        order = 1
        for question in self.questions:
            question._poll_order = order
            for j, child in enumerate(question.children, start=1):
                child._poll_order = order + j / 10
            order += 1
        return self

    def formats_to_polars_schema(self, variable_formats: dict[str, str]) -> dict:
        """
        variable_formats — это то же самое, что meta.variable_formats
        (например {"q0001_1": "F8.2", "q0007_1": "A12000", ...}).

        Правило: тип SPSS-переменной целиком определяется первой буквой формата.
          A...  -> текст   -> pl.Utf8
          F...  -> число   -> pl.Float64

        Везде Float64, а не Int64 — потому что decimal_comma=True и часть F-колонок
        (слайдеры, ranking) может содержать нецелые значения; смешивать Int/Float
        по количеству знаков после точки в формате (F8.0 vs F8.2) смысла нет —
        это тот же csv и тот же паттерн ошибки, только для другой колонки.
        """
        import polars as pl

        return {
            name: (pl.Utf8 if fmt.startswith("A") else pl.Float64)
            for name, fmt in variable_formats.items()
        }

    @property
    def spss_metadata(self):

        NOT_SELECTED = "Не выбран"

        NUMERIC = {"format_": "F8.2", "alignment": "right", "width": 8}
        TEXT = {"format_": "A12000", "alignment": "left", "width": 40}

        TECHNICAL_VARIABLES = {
            "CollectorNM": {"label": "CollectorNM", "format": "A40", "measure": "nominal", "alignment": "left",
                            "width": 40},
            "respondent_id": {"label": "respondent_id", "format": "A40", "measure": "nominal", "alignment": "left",
                              "width": 40},
            "collector_id": {"label": "collector_id", "format": "F4.0", "measure": "nominal", "alignment": "right",
                             "width": 8},
            "date_created": {"label": "date_created", "format": "A40", "measure": "nominal", "alignment": "left",
                             "width": 40},
            "date_modified": {"label": "date_modified", "format": "A40", "measure": "nominal", "alignment": "left",
                              "width": 40},
            "survey_time": {"label": "survey_time", "format": "A40", "measure": "nominal", "alignment": "left",
                            "width": 40},
            "ip_address": {"label": "ip_address", "format": "A40", "measure": "nominal", "alignment": "left",
                           "width": 40},
            "domain_id": {"label": "domain_id", "format": "F8.0", "measure": "nominal", "alignment": "right",
                          "width": 8},
            "language_id": {"label": "language_id", "format": "F8.0", "measure": "nominal", "alignment": "right",
                            "width": 8},
        }

        @dataclass
        class MetadataBuilder:
            """Копит переменные по мере обхода вопросов, в конце собирает SpssMetadata."""

            labels: dict = field(default_factory=dict)
            value_labels: dict = field(default_factory=dict)
            formats: dict = field(default_factory=dict)
            measures: dict = field(default_factory=dict)
            alignments: dict = field(default_factory=dict)
            widths: dict = field(default_factory=dict)

            def add(self, name, label, *, measure, format_, alignment, width, value_labels=None):
                self.labels[name] = label
                self.formats[name] = format_
                self.measures[name] = measure
                self.alignments[name] = alignment
                self.widths[name] = width
                if value_labels is not None:
                    self.value_labels[name] = value_labels

            def build(self):
                return am.SpssMetadata(
                    variable_labels=self.labels,
                    variable_value_labels=self.value_labels,
                    variable_formats=self.formats,
                    variable_measures=self.measures,
                    variable_alignments=self.alignments,
                    variable_display_widths=self.widths,
                )

        def _by_order(items):
            return sorted(items, key=lambda i: i.order)

        def _full_value_labels(question) -> dict[float, str]:
            """0 = «не выбран», дальше — все ответы вопроса по порядку."""
            labels = {0.0: NOT_SELECTED}
            labels.update({float(a.order): a.human_title for a in question.answers if a.human_title})
            return labels

        def _binary_value_labels(answer) -> dict[float, str]:
            """0/1 для одного конкретного варианта ответа (мультивыбор)."""
            return {0.0: NOT_SELECTED, 1.0: answer.human_title}

        # ---------------------------------------------------------------------------
        # Обработчики по type_id — каждый превращает один Question в одну или
        # несколько переменных.
        # ---------------------------------------------------------------------------

        def _add_single(builder, qname, question):
            """single_answer(1) / dropdown(2) / slider(9) / info_material(11):
            один вопрос — одна переменная."""
            builder.add(
                qname, question.human_title,
                measure=question.measure.value,
                value_labels=_full_value_labels(question),
                **NUMERIC,
            )

        def _add_single_choice(builder, qname, question):
            """single_answer(1) / dropdown(2): переменная вопроса + текстовые поля
            "другое" для ответов со свободным вводом. Один такой ответ — qname_other,
            несколько — qname_other_1, qname_other_2, ..."""
            _add_single(builder, qname, question)
            other_answers = [a for a in question.answers if a.has_input]
            if len(other_answers) == 1:
                builder.add(f"{qname}_other", other_answers[0].human_title, measure="nominal", **TEXT)
            else:
                for i, answer in enumerate(other_answers, start=1):
                    builder.add(f"{qname}_other_{i}", answer.human_title, measure="nominal", **TEXT)

        def _add_ranking(builder, qname, question):
            """ranking(8): по переменной на каждый ранжируемый вариант; подпись —
            заголовок вопроса, значения — все варианты ответа."""
            value_labels = _full_value_labels(question)
            for answer in _by_order(question.answers):
                builder.add(
                    f"{qname}_{answer.order}", question.human_title,
                    measure=question.measure.value, value_labels=value_labels, **NUMERIC,
                )

        def _add_single_per_row(builder, qname, question):
            """single_answer_per_row(3): по переменной на каждую строку (child);
            подпись — заголовок строки."""
            value_labels = _full_value_labels(question)
            for child in _by_order(question.children):
                builder.add(
                    f"{qname}_{child.order}", child.human_title,
                    measure=question.measure.value, value_labels=value_labels, **NUMERIC,
                )

        def _add_multiple_choice(builder, qname, question):
            """multiple_choice(4): по переменной на каждый вариант; подпись —
            заголовок вопроса, значения — 0/1 для этого варианта."""
            for answer in _by_order(question.answers):
                builder.add(
                    f"{qname}_{answer.order}", question.human_title,
                    measure=question.measure.value,
                    value_labels=_binary_value_labels(answer), **NUMERIC,
                )

        def _add_multiple_choice_per_row(builder, qname, question):
            """multiple_choice_per_row(10): по переменной на каждую пару строка×вариант."""
            for child in _by_order(question.children):
                for answer in _by_order(question.answers):
                    builder.add(
                        f"{qname}_{child.order}_{answer.order}", child.human_title,
                        measure=question.measure.value,
                        value_labels=_binary_value_labels(answer), **NUMERIC,
                    )

        def _add_open(builder, qname, question):
            """open_question(7): по текстовой переменной на каждый под-вопрос;
            подпись — "заголовок вопроса^заголовок под-вопроса"."""
            for answer in _by_order(question.answers):
                suffix = f"^{answer.human_title}" if answer.human_title else "^"
                builder.add(
                    f"{qname}_{answer.order}", f"{question.human_title}{suffix}",
                    measure="nominal", **TEXT,
                )

        def _add_email(builder, qname, question):
            """email_request(12): одна текстовая переменная с суффиксом _1."""
            builder.add(f"{qname}_1", question.human_title, measure="nominal", **TEXT)

        QUESTION_HANDLERS = {
            1: _add_single_choice,  # single_answer
            2: _add_single_choice,  # dropdown
            3: _add_single_per_row,  # single_answer_per_row
            4: _add_multiple_choice,  # multiple_choice
            7: _add_open,  # open_question
            8: _add_ranking,  # ranking
            9: _add_single,  # slider
            10: _add_multiple_choice_per_row,  # multiple_choice_per_row
            11: _add_single,  # info_material
            12: _add_email,  # email_request
        }

        def questions_to_metadata(questions):
            builder = MetadataBuilder()

            for name, cfg in TECHNICAL_VARIABLES.items():
                builder.add(
                    name, cfg["label"], measure=cfg["measure"],
                    format_=cfg["format"], alignment=cfg["alignment"], width=cfg["width"],
                )

            # questions уже приходят от API в правильном порядке отображения — order
            # внутри Question сбрасывается в каждом новом блоке, поэтому сортировать
            # по нему нельзя. Номер переменной qNNNN — это просто позиция вопроса
            # в списке, а не question.order (order остаётся значимым только внутри
            # вопроса — для answers/children).
            for question in questions:
                qname = f"q{question.poll_order:04d}"
                handler = QUESTION_HANDLERS.get(question.type_id.value)
                if handler is None:
                    raise ValueError(
                        f"Неизвестный type_id={question.type_id.value} "
                        f"для question id={question.id}"
                    )
                handler(builder, qname, question)

            return builder.build()

        return questions_to_metadata(self.questions)


    def to_sql_table(self, table_name: str = "my_table"):
        """
        Export poll structure to SQL table creation string query
        """
        def get_var_type(var_type: str) -> str:
            match var_type:
                case "F8.2":
                    return "INTEGER"
                case "A12000" | "A40":
                    return "TEXT"

        def gen_row(var, var_type):
            return f"   {var} {get_var_type(var_type)}"

        meta = self.spss_metadata
        return (
            f"CREATE TABLE IF NOT EXISTS {table_name} (\n" 
            f"{",\n".join([gen_row(var, var_format) for var, var_format in meta.variable_formats.items()])}" 
            "\n)"
                )




    def _rebuild_index(self, index_name: str, collection_name: str) -> None:
        """Rebuild a private ``{item.id: item}`` lookup from a list field."""
        setattr(
            self,
            index_name,
            {item.id: item for item in getattr(self, collection_name)},
        )

    @model_validator(mode="after")
    def index_questions(self) -> Poll:
        """Rebuild ``_question_by_id`` to cover both top-level questions and their nested children."""
        self._question_by_id = {
            item.id: item
            for question in self.questions
            for item in chain((question,), question.children)
        }
        return self

    @model_validator(mode="after")
    def index_blocks(self) -> Poll:
        self._rebuild_index(index_name="_block_by_id", collection_name="blocks")
        return self

    @model_validator(mode="after")
    def index_pages(self) -> Poll:
        self._rebuild_index(index_name="_page_by_id", collection_name="pages")
        return self

    def get_question_by_id(self, item_id: int) -> Optional[Question]:
        return self._question_by_id.get(item_id)

    def get_block_by_id(self, item_id: int) -> Optional[Block]:
        return self._block_by_id.get(item_id)

    def get_page_by_id(self, item_id: int) -> Optional[Page]:
        return self._page_by_id.get(item_id)

    def to_json_file(self, file_path: str) -> None:
        io.to_json(model=self, file_path=file_path)

    @classmethod
    def from_json_file(cls, file_path: str) -> Poll:
        return io.from_json(cls=cls, file_path=file_path)

    def to_docx(self, file_path: str) -> None:
        io.export_docx(poll=self, file_path=file_path)

    def dump_create_payload(self):
        """Use to filter fields in create poll request"""
        fields = {
            "can_cameback",
            "description",
            "domain_id",
            "is_multiple",
            "language_id",
            "meta",
            "name",
            "source_id",
            "state_id",
            "title",
            "track_id",
            "type_id",
        }
        payload = self.model_dump(include=fields)
        payload["title"] = md_to_html(payload["title"])
        payload["description"] = md_to_html(payload["description"])
        return payload

    @classmethod
    def decrement_id(cls):
        i = 0
        while True:
            i -= 1
            yield i

    @model_validator(mode="after")
    def child_id_generator(self) -> Poll:
        self._id_generator = self.decrement_id()
        return self

    # ------------------------------------------------------------------
    # Draft building: a poll created from scratch, then uploaded with
    # ``PollResource.upload_poll``. Items get temporary negative ids so
    # that logic can reference them before the server assigned real ones.
    # ------------------------------------------------------------------

    @property
    def is_draft(self) -> bool:
        """True while the poll has not been created on the server."""
        return self.id is None

    def _next_id(self) -> int:
        """Next temporary (negative) id for a draft item."""
        return next(self._id_generator)

    def _refresh(self) -> None:
        """Recompute question numbering and id lookups after the draft structure changed."""
        self.count_questions()
        self.index_questions()
        self.index_blocks()
        self.index_pages()
        for question in self.questions:
            question.index_answers()

    def _attach_logic(self, rule: logic.Logic, collection: list) -> None:
        """Give a new logic rule a temporary id, bind it to this poll and store it in ``collection``."""
        rule.id = self._next_id()
        rule._poll = self
        collection.append(rule)

    @overload
    def add_block(self, block: Block) -> Block:
        ...

    @overload
    def add_block(
            self,
            *,
            name: str,
            title: Optional[str] = None,
            description: Optional[str] = None,
            is_panel: bool = False,
    ) -> Block:
        ...

    def add_block(
            self,
            block: Block | None = None,
            *,
            name: str | None = None,
            title: Optional[str] = None,
            description: Optional[str] = None,
            is_panel: bool = False,
    ) -> Block:
        """
        Добавляет блок (группу вопросов) в опрос.

        Блок можно передать двумя способами:

        1. Готовый объект ``Block``: ``poll.add_block(block)``.

        2. Аргументы для создания блока::

               block = poll.add_block(name="Блок 1", title="О вас")

        Блоки идут в том порядке, в котором добавлены. Блоку автоматически
        назначаются ``order`` и временный ``id``. Вопросы, уже лежащие в
        переданном ``Block(questions=[...])``, тоже получают ``id`` и
        привязываются к опросу; дальше вопросы удобнее добавлять через
        ``block.add_question(...)``.

        Args:
            block: Готовый объект ``Block``. Если указан, остальные
                аргументы указывать нельзя.
            name: Служебное название блока. Обязательно, если ``block``
                не передан.
            title: Заголовок блока, который видит респондент.
            description: Описание блока.
            is_panel: Признак панельного блока.

        Returns:
            Добавленный объект ``Block``.

        Raises:
            ValueError: Блок уже принадлежит опросу; переданы и ``block``,
                и аргументы для создания; не указан ``name``.
        """
        if block is not None:
            if name is not None or title is not None or description is not None or is_panel:
                raise ValueError("Pass either a ready Block or arguments to create one, not both.")
        else:
            if name is None:
                raise ValueError("name is required when no Block object is passed.")
            block = Block(name=name, title=title or "", description=description or "", is_panel=is_panel)

        if block._poll is not None:
            raise ValueError("This block already belongs to a poll.")

        # questions given to the Block constructor are adopted below, one by one,
        # so they get ids / numbering like any question added later
        preset_questions, block.questions = list(block.questions), []

        block.order = len(self.blocks) + 1
        block.id = self._next_id()
        block.poll_id = self.id
        block._id_generator = self._id_generator
        block._poll = self

        self.blocks.append(block)
        self._refresh()
        for question in preset_questions:
            block.add_question(question)
        return block

    def _draft_items(self) -> tuple[set[int], list[logic.Logic]]:
        """Ids of every draft question/row/answer/block, and every logic rule."""
        known: set[int] = {block.id for block in self.blocks}
        for question in self.questions:
            known.add(question.id)
            known.update(answer.id for answer in question.answers or [])
            known.update(child.id for child in question.children or [])
        rules = [*self.jumps, *self.displays, *self.display_answers]
        return known, rules

    def validate_draft(self) -> None:
        """
        Check that every logic rule references items that exist in this
        poll, so a broken draft fails *before* anything is sent.

        Draft ids must belong to this poll; real (positive) ids are assumed
        to be existing server items, e.g. a finish page.

        :raises ValueError: listing every problem found.
        """
        known, rules = self._draft_items()

        def bad(value: int | None) -> bool:
            return is_draft_id(value) and value not in known

        problems: list[str] = []
        for rule in rules:
            refs = {
                "reference_question_id": [rule.reference_question_id],
                "reference_answer_id": rule.reference_answer_id,
                "question_id": [getattr(rule, "question_id", None)],
                "answer_id": [getattr(rule, "answer_id", None)],
                "target_question_id": [getattr(rule, "target_question_id", None)],
            }
            for name, values in refs.items():
                problems.extend(
                    f"{type(rule).__name__} {rule.id}: {name}={value} is not part of this poll"
                    for value in values if bad(value)
                )
        if problems:
            raise ValueError("Poll draft is inconsistent:\n" + "\n".join(problems))

    @overload
    def add_page(self, page: Page) -> Page:
        ...

    @overload
    def add_page(
            self,
            *,
            name: str,
            type_id: PageType | PageTypeName,
            title: Optional[str] = None,
            description: Optional[str] = None,
    ) -> Page:
        ...

    def add_page(
            self,
            page: Page | None = None,
            *,
            name: str | None = None,
            type_id: PageType | PageTypeName | None = None,
            title: Optional[str] = None,
            description: Optional[str] = None,
    ) -> Page:
        """
        Добавляет в опрос страницу: приветствие, завершение или дисквалификацию.

        Страницу можно передать двумя способами:

        1. Готовый объект ``Page``: ``poll.add_page(page)``.
           Все данные должны быть заданы при создании ``Page``.

        2. Аргументы для создания ``Page``::

               finish = poll.add_page(
                   name="Спасибо",
                   page_type="finish",
                   title="Опрос завершён",
                   description="Спасибо за участие!",
               )

        Страницы каждого типа бывают только по одной. Странице автоматически
        назначаются временный ``id`` и ``poll_id``, и она привязывается к
        опросу, так что на неё можно ссылаться в переходах:
        ``question.add_jump(finish, ...)``.

        Args:
            page: Готовый объект ``Page``. Если указан, остальные аргументы
                указывать нельзя.
            name: Название страницы. Обязательно, если ``page`` не передан.
            type_id: Тип страницы: ``PageType`` или строка ``"greeting"``,
                ``"finish"``, ``"disqualification"``. Обязателен, если
                ``page`` не передан.
            title: Заголовок страницы (по умолчанию пустой).
            description: Текст страницы (по умолчанию пустой).

        Returns:
            Добавленный объект ``Page``.

        Raises:
            ValueError: Переданы и ``page``, и аргументы для создания; не
                указан ``name`` или ``page_type``; неизвестный тип страницы;
                страница уже принадлежит опросу; страница такого типа в
                этом опросе уже есть.
        """
        if page is not None:
            if any(v is not None for v in (name, type_id, title, description)):
                raise ValueError("Pass either a ready Page or arguments to create one, not both.")
        else:
            if name is None or type_id is None:
                raise ValueError("name and page_type are required when no Page object is passed.")
            page = Page(
                name=name,
                data=PageData(title=title or "", description=description or ""),
                type_id=coerce_page_type(type_id),
            )

        if page._poll is not None:
            raise ValueError("This page already belongs to a poll.")

        if page.type_id in [p.type_id for p in self.pages]:
            raise ValueError("Page of the same type already exists.")

        page.id = self._next_id()
        page.poll_id = self.id
        page._id_generator = self._id_generator
        page._poll = self

        self.pages.append(page)
        self.index_pages()
        return page

    @overload
    def add_counter(self, counter: Counter) -> Counter:
        ...

    @overload
    def add_counter(
            self,
            *,
            name: str,
            quota: int,

            description: Optional[str] = None,
            source_ids: list[int] | None = None,
            conditions: list[CounterCondition] | None = None

    ) -> Counter:
        ...

    def add_counter(
            self,
            counter: Counter | None = None,
            *,
            name: str,
            quota: int,

            description: Optional[str] = None,
            source_ids: list[int] | None = None,
            conditions: list[CounterCondition] | None = None
    ) -> Counter:
        """

        """
        if counter is not None:
            if any(v is not None for v in (name, quota, all(i is None for i  in [source_ids, conditions]))):
                raise ValueError("Pass either a ready Page or arguments to create one, not both.")
        else:
            if name is None or quota is None or all(i is None for i  in [source_ids, conditions]):
                raise ValueError("name, quota and source_ids / conditions are required when no Counter object is passed.")
            counter = Counter(
                name=name,
                quota=quota,
                description=description,
                source_ids=source_ids,
                conditions=conditions or None,
            )

        if counter._poll is not None:
            raise ValueError("This counter already belongs to a poll.")

        counter.id = self._next_id()
        counter.poll_id = self.id
        counter._poll = self

        self.counters.append(counter)

        return counter


class GetPollHeaderPayload(BaseModel):
    """Request body for fetching just a poll's header."""
    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., ge=1)


class DuplicatePollPayload(BaseModel):
    id: int = Field(..., ge=1)
    with_counters: bool = Field(default=False)

class CreatePersonalLinks(BaseModel):
    link_count: int = Field(..., ge=1, le=5000)
    poll_id: int = Field(..., ge=1)

class UpdateMeta(BaseModel):
    id: int = Field(..., ge=1)
    meta: List[int]

class GetPollListPayload(BaseModel):
    """
    Request body for listing/searching polls.
    """
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=11, ge=0, le=50)
    offset: int = Field(default=0, ge=0)
    is_in_track: bool = False
    meta: Optional[List[int]] = None
    sociologist_id: Optional[int] = None
    status_id: Optional[int] = None
    targetologist_id: Optional[int] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None


class ExportFormat(IntEnum):
    """File format for a poll data export."""
    XLSX = 1
    SAV = 2
    CSV = 5


class QuestionFilter(BaseModel):
    """Restricts an export to respondents who gave a specific answer to a specific question."""
    model_config = ConfigDict(extra="forbid")

    question_id: int = Field(..., ge=1)
    answer_id: int = Field(..., ge=1)


class ExportFilter(BaseModel):
    """Filter criteria for a poll data export."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    counters_ids: Optional[List[int]] = None
    from_: Optional[datetime] = Field(default=None, alias="from")
    to: Optional[datetime] = Field(default=None)
    is_disqualified: Optional[bool] = None
    is_only_plan: Optional[bool] = None
    questions: Optional[List[QuestionFilter]] = None
    utm_source: Optional[List[int]] = None

    domain_ids: List[int] = Field(default=[1])
    is_poll_complete: bool = Field(default=True)
    is_poll_in_progress: bool = Field(default=True)


EXPORT_FORMATS = Literal["xlsx", "sav", "csv"]


class ExportPayload(BaseModel):
    """Request body for triggering a poll data export."""
    model_config = ConfigDict(extra="forbid")

    poll_id: int = Field(..., ge=1)
    filter: ExportFilter = Field(default_factory=ExportFilter)
    format_id: ExportFormat | EXPORT_FORMATS = Field(default=ExportFormat.CSV)

    @field_validator("format_id", mode="before")
    @classmethod
    def _coerce_format_id(cls, v: Any) -> Any:
        """Accept either the ``ExportFormat`` enum or its lowercase string name (``"csv"`` -> ``ExportFormat.CSV``)."""
        if isinstance(v, str):
            return ExportFormat[v.upper()]
        return v


class DownloadPayload(BaseModel):
    """Request body for downloading or acknowledging a finished export, identified by its job uuid."""
    model_config = ConfigDict(extra="forbid")

    uuid: UUID


class ExportStatus(StrEnum):
    """Status of an in-progress export job."""
    DONE = "done"
    ERROR = "error"
    IN_PROGRESS = "in_progress"


class ProgressStatus(BaseModel):
    """Status of one export job, as returned by the progress endpoint."""
    user_id: int
    uuid: UUID
    jwt_uuid: UUID
    params: ExportPayload
    status: str


class UpdatePollPayload(BaseModel):
    id: int
    background: Optional[BackgroundColor] = None
    can_cameback: Optional[bool] = None
    description: Optional[str] = None
    domain_id: Optional[int] = None
    field_date: Optional[datetime] = None
    is_multiple: Optional[bool] = None
    language_id: Optional[int] = None
    meta: Optional[list[int]] = None
    name: Optional[str] = None
    notify_flag: Optional[bool] = None
    poll_responsible: Optional[int] = None
    source_id: Optional[str] = None
    state_id: Optional[int] = None
    status_id: Optional[PollStatus] = None
    title: Optional[str] = None
    type_id: Optional[PollType] = None


class ExportRepeatPassagesPayload(BaseModel):
    poll_id: int = Field(..., ge=1)

# Block/Question/Poll reference each other by name only (blocks.py imports
# Question/Poll under TYPE_CHECKING to avoid circular imports), so pydantic can't
# finish building them on its own: without this, ``Poll(...)`` raises
# "`Poll` is not fully defined" whenever it is called from inside a function
# that doesn't have ``Question`` in its local scope.
_NAMESPACE = {"Poll": Poll, "Block": Block, "Question": Question, "ChildQuestion": ChildQuestion}
Question.model_rebuild(_types_namespace=_NAMESPACE)
Block.model_rebuild(_types_namespace=_NAMESPACE)
Poll.model_rebuild(_types_namespace=_NAMESPACE)