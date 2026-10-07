"""Tests for building a poll from scratch and uploading it through a fake constructor API."""
import json
import pytest

from socapi import (
    ParserClient, Poll, PollType, Block, Question, Answer, AnswerTypes, ChildQuestion,
    Comparator, exceptions,
)
from socapi.client import Response
from socapi.resources.questions import InputValidations


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def build_poll():
    poll = Poll(name="hello test", user_id=561, type_id=PollType.ONE_QUESTION, meta=[0])
    intro = poll.add_block(Block(name="intro"))
    age = intro.add_question(Question(
        title="age", type_id=AnswerTypes.single_answer,
        answers=[
            Answer(title="under 16"),
            Answer(title="16-24", has_input=True, input_validation=InputValidations.number),
            Answer(title="25-59"),
        ],
    ))
    gender = intro.add_question(Question(
        title="gender", type_id=AnswerTypes.single_answer,
        answers=[Answer(title="m"), Answer(title="f")],
    ))
    return poll, intro, age, gender


class FakeServer:
    """Stands in for the constructor: hands out ids, echoes payloads, records the call order."""

    def __init__(self, fail_on: str | None = None):
        self.calls: list[tuple[str, object]] = []
        self._next = 100
        self.fail_on = fail_on

    def _id(self) -> int:
        self._next += 1
        return self._next

    async def __call__(self, request):
        endpoint = str(request.endpoint)
        payload = json.loads(json.dumps(request.json_))  # must be JSON-serialisable, like on the wire
        self.calls.append((endpoint, payload))
        if self.fail_on and endpoint.endswith(self.fail_on):
            raise exceptions.UnknownError(status=500, error="boom")

        if endpoint.endswith("/poll/create"):
            result = {**payload, "id": self._id(), "user_id": 561}
        elif endpoint.endswith("/block/create") or endpoint.endswith("/answer/create"):
            result = {**payload, "id": self._id()}
        elif endpoint.endswith("/question/create"):
            children = [{**c, "id": self._id()} for c in payload["children"]]
            result = {**payload, "id": self._id(), "children": children}
        elif "/logic/" in endpoint:
            result = [{**payload[0], "id": self._id()}]
        else:  # pragma: no cover
            raise AssertionError(f"unexpected endpoint {endpoint}")
        return Response(status=200, error=None, result=result)


@pytest.fixture
def client():
    return ParserClient(host="online-sociology.ru", access_token="token")


def attach(client, monkeypatch, server):
    """Route every HTTP call of the client to the fake server."""
    async def fake_request(self, request):
        return await server(request)

    monkeypatch.setattr(ParserClient, "_request", fake_request)


def negative_ints(value):
    """Every negative integer anywhere in a JSON-like structure."""
    if isinstance(value, bool):
        return []
    if isinstance(value, int):
        return [value] if value < 0 else []
    if isinstance(value, dict):
        return [n for v in value.values() for n in negative_ints(v)]
    if isinstance(value, list):
        return [n for v in value for n in negative_ints(v)]
    return []


# --------------------------------------------------------------------------
# building
# --------------------------------------------------------------------------
def test_ids_are_unique_negative_and_ordered():
    poll, intro, age, gender = build_poll()
    ids = [intro.id, age.id, gender.id] + [a.id for q in (age, gender) for a in q.answers]
    assert all(i < 0 for i in ids)
    assert len(set(ids)) == len(ids)
    assert (intro.order, age.order, gender.order) == (1, 1, 2)
    assert [a.order for a in age.answers] == [1, 2, 3]
    assert age.block_id == intro.id
    assert all(a.question_id == age.id for a in age.answers)


def test_poll_order_and_lookup_work_on_draft():
    poll, intro, age, gender = build_poll()
    assert (age.poll_order, gender.poll_order) == (1, 2)
    assert poll.get_question_by_id(gender.id) is gender
    assert poll.get_block_by_id(intro.id) is intro
    assert age.get_answer_by_id(age.answers[0].id) is age.answers[0]


def test_add_display_stores_rule_and_is_visible_via_question():
    poll, _, age, gender = build_poll()
    rule = gender.add_display(age, Comparator.IS_SELECTED, reference_answer_order=1)
    assert gender.displays == [rule] and poll.displays == [rule]
    assert rule.question_id == gender.id
    assert rule.reference_question_id == age.id
    assert rule.reference_answer_id == [age.answers[0].id]
    assert age.display_answers == []  # that is answer-display logic, a different thing
    assert "1" in rule.human_condition()


def test_add_display_accepts_several_answers_and_none():
    _, _, age, gender = build_poll()
    several = gender.add_display(age, Comparator.IS_SELECTED, [1, 3])
    assert several.reference_answer_id == [age.answers[0].id, age.answers[2].id]
    none = gender.add_display(age, Comparator.IS_ANSWERED)
    assert none.reference_answer_id == []


def test_unknown_answer_order_is_rejected_with_hint():
    _, _, age, gender = build_poll()
    with pytest.raises(ValueError, match="available: \\[1, 2, 3\\]"):
        gender.add_display(age, Comparator.IS_SELECTED, reference_answer_order=9)


def test_add_jump_defaults_reference_to_self():
    poll, _, age, gender = build_poll()
    jump = age.add_jump(gender, Comparator.IS_SELECTED, 2)
    assert age.jumps == [jump]
    assert jump.reference_question_id == age.id
    assert jump.target_question_id == gender.id


def test_add_jump_rejects_bad_target():
    _, _, age, _ = build_poll()
    with pytest.raises(TypeError):
        age.add_jump(42, Comparator.IS_ANSWERED)


def test_answer_display():
    poll, _, age, gender = build_poll()
    rule = gender.answers[1].add_display(age, Comparator.IS_SELECTED, 3)
    assert poll.display_answers == [rule]
    assert gender.answers[1].display_answers == [rule]
    assert rule.answer_id == gender.answers[1].id


def test_add_answer_and_matrix_rows_later():
    poll, intro, _, _ = build_poll()
    matrix = intro.add_question(Question(title="m", type_id=AnswerTypes.single_answer_per_row))
    matrix.add_child(ChildQuestion(title="row 1", type_id=AnswerTypes.single_answer))
    matrix.add_child(ChildQuestion(title="row 2", type_id=AnswerTypes.single_answer))
    matrix.add_answer(Answer(title="yes"))
    assert [c.order for c in matrix.children] == [1, 2]
    assert all(c.parent_id == matrix.id for c in matrix.children)
    assert poll.get_question_by_id(matrix.children[1].id) is matrix.children[1]
    assert matrix.answers[0].order == 1


def test_structure_errors_are_explicit():
    with pytest.raises(ValueError, match="poll.add_block"):
        Block(name="loose").add_question(Question(title="q", type_id=AnswerTypes.open_question))
    poll, intro, age, _ = build_poll()
    with pytest.raises(ValueError, match="already belongs"):
        intro.add_question(age)
    with pytest.raises(ValueError, match="already belongs"):
        poll.add_block(intro)
    with pytest.raises(ValueError, match="block"):
        Question(title="q", type_id=AnswerTypes.open_question).add_display(age, Comparator.IS_ANSWERED)


def test_validate_draft_catches_foreign_references():
    poll, _, age, gender = build_poll()
    rule = gender.add_display(age, Comparator.IS_SELECTED, 1)
    poll.validate_draft()  # consistent draft passes
    rule.reference_question_id = -999  # a draft id that belongs to no item of this poll
    with pytest.raises(ValueError, match="reference_question_id=-999"):
        poll.validate_draft()


def test_parsing_api_answers_still_works():
    """Regression: order_answers used to crash on raw dicts coming from the API."""
    q = Question(id=1, title="t", type_id=1, answers=[{"id": 5, "title": "a"}, {"id": 6, "title": "b", "order": 2}])
    assert [a.order for a in q.answers] == [1, 2]


# --------------------------------------------------------------------------
# uploading
# --------------------------------------------------------------------------
async def test_upload_creates_in_dependency_order_with_real_ids(client, monkeypatch):
    poll, intro, age, gender = build_poll()
    gender.add_display(age, Comparator.IS_SELECTED, 1)
    age.add_jump(gender, Comparator.IS_SELECTED, 2)
    gender.answers[1].add_display(age, Comparator.IS_SELECTED, 3)

    server = FakeServer()
    attach(client, monkeypatch, server)
    result = await client.poll.upload_poll(poll)

    endpoints = [e for e, _ in server.calls]
    # assert endpoints == [
    #     "/api/poll/create",
    #     "/api/block/create",
    #     "/api/question/create", "/api/question/answer/create", "/api/question/answer/create", "/api/question/answer/create",
    #     "/api/question/create", "/api/question/answer/create", "/api/question/answer/create",
    #     "/api/logic/display/addpack", "/api/logic/jump/addpack", "/api/logic/display-answer/addpack",
    # ]

    # nothing temporary ever reaches the wire
    for endpoint, payload in server.calls:
        assert negative_ints(payload) == [], endpoint

    # objects carry real ids afterwards
    assert result is poll
    assert poll.id > 0 and intro.id > 0 and age.id > 0 and gender.id > 0
    assert all(a.id > 0 for q in (age, gender) for a in q.answers)

    # and the wire payloads were wired to the *real* parents
    by_endpoint = {}
    for endpoint, payload in server.calls:
        by_endpoint.setdefault(endpoint, []).append(payload)
    assert by_endpoint["/api/block/create"][0]["poll_id"] == poll.id
    assert [p["block_id"] for p in by_endpoint["/api/question/create"]] == [intro.id, intro.id]
    answers = by_endpoint["/api/question/answer/create"]
    assert [a["question_id"] for a in answers] == [age.id] * 3 + [gender.id] * 2

    display = by_endpoint["/api/logic/display/addpack"][0][0]
    assert display["poll_id"] == poll.id
    assert display["question_id"] == gender.id
    assert display["reference_question_id"] == age.id
    assert display["reference_answer_id"] == [age.answers[0].id]

    jump = by_endpoint["/api/logic/jump/addpack"][0][0]
    assert (jump["question_id"], jump["target_question_id"]) == (age.id, gender.id)

    ans_display = by_endpoint["/api/logic/display-answer/addpack"][0][0]
    assert ans_display["answer_id"] == gender.answers[1].id
    assert ans_display["reference_answer_id"] == [age.answers[2].id]

    # model level relations keep working with real ids
    assert gender.displays and age.jumps and gender.answers[1].display_answers
    assert poll.get_question_by_id(gender.id) is gender
    assert all(r.id > 0 for r in poll.displays + poll.jumps + poll.display_answers)


async def test_upload_maps_matrix_rows(client, monkeypatch):
    poll, intro, age, _ = build_poll()
    matrix = intro.add_question(Question(
        title="matrix", type_id=AnswerTypes.single_answer_per_row,
        children=[ChildQuestion(title="r1", type_id=AnswerTypes.single_answer),
                  ChildQuestion(title="r2", type_id=AnswerTypes.single_answer)],
        answers=[Answer(title="yes"), Answer(title="no")],
    ))
    matrix.add_display(age, Comparator.IS_SELECTED, 1)
    server = FakeServer()
    attach(client, monkeypatch, server)
    await client.poll.upload_poll(poll)

    q_payload = [p for e, p in server.calls if e == "/api/question/create"][-1]
    assert [c["title"] for c in q_payload["children"]] == ["r1", "r2"]
    assert all("id" not in c for c in q_payload["children"])
    assert all(c.id > 0 and c.parent_id == matrix.id for c in matrix.children)
    assert poll.get_question_by_id(matrix.children[0].id) is matrix.children[0]


async def test_upload_rejects_already_uploaded_poll(client, monkeypatch):
    poll, *_ = build_poll()
    attach(client, monkeypatch, FakeServer())
    await client.poll.upload_poll(poll)
    with pytest.raises(ValueError, match="already exists"):
        await client.poll.upload_poll(poll)


async def test_invalid_draft_sends_nothing(client, monkeypatch):
    poll, _, age, gender = build_poll()
    rule = gender.add_display(age, Comparator.IS_SELECTED, 1)
    rule.reference_question_id = -999
    server = FakeServer()
    attach(client, monkeypatch, server)
    with pytest.raises(ValueError):
        await client.poll.upload_poll(poll)
    assert server.calls == []


async def test_failure_reports_partial_poll(client, monkeypatch):
    poll, intro, age, gender = build_poll()
    server = FakeServer(fail_on="/answer/create")
    attach(client, monkeypatch, server)
    with pytest.raises(exceptions.PollUploadError) as info:
        await client.poll.upload_poll(poll)
    print(info)
    print(info.value)
    assert info.value.poll_id == poll.id and poll.id > 0
    assert "question 'age' answer 'under 16'" in info.value.stage
    assert isinstance(info.value.__cause__, exceptions.UnknownError)