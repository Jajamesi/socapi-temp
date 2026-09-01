import pytest

import dotenv
dotenv.load_dotenv()
import os
from typing import List

import socapi
from socapi.resources import polls, blocks, questions, logic

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")
test_poll = int(os.getenv("TEST_POLL", ""))

@pytest.mark.asyncio
async def test_get_poll_head(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.poll.get_poll_head(poll_id=test_poll)
        assert isinstance(result, polls.Poll)


@pytest.mark.asyncio
async def test_get_all_questions(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.poll.get_poll_structure(poll_id=test_poll)

        questions_ = result.questions

        assert isinstance(questions_, list)
        assert all(isinstance(q, questions.Question) for q in questions_)



@pytest.mark.asyncio
async def test_get_poll_structure(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.poll.get_poll_structure(poll_id=test_poll)
        assert isinstance(result, polls.Poll)
        assert isinstance(result.blocks, list)
        assert all(isinstance(b, blocks.Block) for b in result.blocks)
        assert isinstance(result.blocks[0].questions, list)
        assert all(isinstance(q, questions.Question) for q in result.blocks[0].questions)

        # test logic parser
        jump_question_id = result.jumps[0].question_id if len(result.jumps) > 0 else None
        if jump_question_id is not None:
            question = [
                q for b in result.blocks for q in b.questions if q.id == jump_question_id ][0]
            assert isinstance(question.jumps[0], logic.Jump)

        displays_question_id = result.displays[0].question_id if len(result.displays) > 0 else None
        if displays_question_id is not None:
            question = [
                q for b in result.blocks for q in b.questions if q.id == displays_question_id][0]
            assert isinstance(question.displays[0], logic.Display)

        display_answer_question_id = result.display_answers[0].reference_question_id if len(result.display_answers) > 0 else None
        if display_answer_question_id is not None:
            question = [
                q for b in result.blocks for q in b.questions if q.id == display_answer_question_id][0]
            assert isinstance(question.display_answers[0], logic.DisplayAnswers)


@pytest.mark.parametrize(
    "export_format,filter_",
    [
        pytest.param(
            "csv",
            None,
            id="csv-no-filters",
        ),
        pytest.param(
            "sav",
            None,
            id="sav-no-filters",
        ),
        pytest.param(
            "xlsx",
            None,
            id="xlsx-no-filters",
        ),
        pytest.param(
            "csv",
            {
                'is_disqualified': True,
                'from': '2026-07-24T00:00:00+03:00'
            },
            id="csv-filters",
        ),
        pytest.param(
            "sav",
            {'utm_source': [76,77]},
            id="sav-filters",
        ),
        pytest.param(
            "xlsx",
            {'is_only_plan': True},
            id="xlsx-filters",
        ),
    ]
)
async def test_download_poll(mocker, export_format,filter_):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.poll.download_polls(poll_ids=test_poll)
        assert test_poll in result.keys()


@pytest.mark.asyncio
async def test_validate_download_poll(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.poll.download_polls(poll_ids=str(test_poll))
        assert test_poll in result.keys()


@pytest.mark.asyncio
async def test_json_io(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.poll.get_poll_structure(poll_id=test_poll)
        result.to_json_file(f"./export_{test_poll}.json")
        poll = socapi.Poll.from_json_file(f"./export_{test_poll}.json")

        os.remove(f"./export_{test_poll}.json")

        assert isinstance(poll, socapi.Poll)


@pytest.mark.asyncio
async def test_export_docx(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        poll = await client.poll.get_poll_structure(poll_id=12634) # rkz poll with complex logics
    poll.to_docx(f"./export_{12634}.docx")
