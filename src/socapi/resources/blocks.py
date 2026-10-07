from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only needed for the `_poll` backref type hint; importing at runtime
    # would create a circular import with polls.py (Poll owns Blocks).
    from .polls import Poll

from typing import Any, Optional, List, Sequence, Tuple, Generator, overload
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr

from .questions import Answer, AnswerTypes, ChildQuestion, Question, QuestionTypeName, _coerce_enum
from ..text_worker import md_to_html


class Block(BaseModel):
    """
    A block (question group) within a poll.

    ``_poll`` is an optional back-reference to the owning :class:`Poll`,
    populated once ``PollResource.get_poll_structure`` wires nested items
    together (see the ``TODO`` in ``client.py``); it's not set by plain
    ``model_validate(**api_response)`` construction.
    """
    id: Optional[int] = None
    order: Optional[int] = None
    name: str
    title: str = Field(default="")
    description: str = Field(default="")
    created_at: Optional[datetime] = None
    questions: List[Question] = Field(default_factory=list)
    poll_id: int | None = None
    is_panel: bool = False

    _poll: Optional[Poll] = PrivateAttr(default=None)
    _id_generator: Generator[int, None, None] = PrivateAttr(default=None)

    def dump_create_payload(self):
        """Use to filter fields in create block request"""
        fields = {
            "description",
            "name",
            "order",
            "poll_id",
            "title",
        }
        payload = self.model_dump(include=fields)
        payload["title"] = md_to_html(payload["title"])
        return payload

    @overload
    def add_question(self, question: Question) -> Question:
        ...

    @overload
    def add_question(
            self,
            *,
            title: str,
            type_id: AnswerTypes | QuestionTypeName,
            answers: Sequence[Answer | str] | None = None,
            rows: Sequence[ChildQuestion | str] | None = None,
            **options: Any,
    ) -> Question:
        ...

    def add_question(
            self,
            question: Question | None = None,
            *,
            title: str | None = None,
            type_id: AnswerTypes | QuestionTypeName | None = None,
            answers: Sequence[Answer | str] | None = None,
            rows: Sequence[ChildQuestion | str] | None = None,
            **options: Any,
    ) -> Question:
        """
        Добавляет вопрос в блок.

        Вопрос можно передать двумя способами:

        1. Готовый объект ``Question``: ``block.add_question(question)``.

        2. Аргументы для его создания::

               block.add_question(
                   title="Как вы добираетесь до работы?",
                   type_id="single_answer",
                   answers=["Пешком", "Транспорт", Answer(title="Другое", has_input=True)],
               )

        Блок уже должен быть добавлен в опрос (``poll.add_block(...)``): опрос
        выдаёт временные id, по которым потом строится логика
        (``add_display`` / ``add_jump``). Вопросу автоматически назначаются
        ``order`` (следующий по счёту в блоке), ``id`` и ``block_id``; ответам
        и строкам матрицы — ``id`` и ``order``.

        Args:
            question: Готовый ``Question``. Если указан, остальные аргументы
                указывать нельзя.
            title: Текст вопроса. Обязателен, если ``question`` не передан.
            type_id: Тип вопроса: член ``AnswerTypes`` или его имя строкой
                (``"single_answer"``, ``"dropdown"``, ``"single_answer_per_row"``,
                ``"multiple_choice"``, ``"open_question"``, ``"ranking"``,
                ``"slider"``, ``"multiple_choice_per_row"``, ``"info_material"``,
                ``"email_request"``). Обязателен, если ``question`` не передан.
            answers: Варианты ответа: строки или объекты ``Answer``. Строка
                превращается в ``Answer(title=строка)``; если нужен ответ со
                свободным вводом («Другое»), передайте
                ``Answer(title=..., has_input=True)``.
            rows: Строки матрицы (для ``single_answer_per_row`` и
                ``multiple_choice_per_row``): строки или ``ChildQuestion``.
                Строка получает тот же ``type_id``, что и вопрос.
            **options: Любые другие поля ``Question``, например
                ``optional=True``, ``randomized=True``, ``min_answer=1``,
                ``max_answer=3``, ``measure="ordinal"``.

        Returns:
            Добавленный объект ``Question``.

        Raises:
            ValueError: Блок не добавлен в опрос; вопрос уже принадлежит
                опросу; переданы и ``question``, и аргументы для создания;
                не указан ``title`` или ``type_id``; неизвестный тип вопроса.
        """
        if question is not None:
            if any(v is not None for v in (title, type_id, answers, rows)) or options:
                raise ValueError("Pass either a ready Question or arguments to create one, not both.")
        else:
            if title is None or type_id is None:
                raise ValueError("title and type_id are required when no Question object is passed.")
            type_id = _coerce_enum(AnswerTypes, type_id, "question type")
            question = Question(
                title=title,
                type_id=type_id,
                answers=[a if isinstance(a, Answer) else Answer(title=a, input_validation="none") for a in answers or []],
                children=[
                    r if isinstance(r, ChildQuestion) else ChildQuestion(title=r, type_id=type_id)
                    for r in rows or []
                ],
                **options,
            )

        poll = self._poll
        if poll is None:
            raise ValueError("Add this block to a poll first (poll.add_block(block)).")
        if question._poll is not None:
            raise ValueError("This question already belongs to a poll.")

        question.order = len(self.questions) + 1
        question.block_id = self.id
        question.id = poll._next_id()
        question._id_generator = poll._id_generator
        question._poll = poll
        self.questions.append(question)

        # answers / matrix rows passed to the constructor get their ids here,
        # which lets logic reference them right away
        for answer in question.answers or []:
            question._adopt_answer(answer)
        for child in question.children or []:
            question._adopt_child(child)

        poll._refresh()
        return question


class BlockInclude(StrEnum):
    """Fields of :class:`Block` that can be requested via ``includes``."""
    id = "id"
    name = "name"
    title = "title"
    description = "description"
    poll_id = "poll_id"
    order = "order"

ALL_BLOCK_INCLUDES: Tuple[BlockInclude, ...] = tuple(BlockInclude)

class GetBlocksPayload(BaseModel):
    """Request body for listing the blocks of a poll."""
    model_config = ConfigDict(extra="forbid")

    poll_id: int = Field(..., ge=1)
    includes: list[BlockInclude] = Field(default_factory=lambda: list(ALL_BLOCK_INCLUDES))

