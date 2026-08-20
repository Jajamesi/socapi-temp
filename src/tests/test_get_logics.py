import pytest

import dotenv
dotenv.load_dotenv()
import os
from typing import List

import socapi
from socapi.resources import logic

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")
test_poll = int(os.getenv("TEST_POLL", ""))

@pytest.mark.asyncio
async def test_get_jumps(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.logic.get_jumps(poll_id=test_poll)
        assert all(isinstance(x, logic.Jump) for x in result)


@pytest.mark.asyncio
async def test_get_answers_display(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.logic.get_answer_display(poll_id=test_poll)
        assert all(isinstance(x, logic.DisplayAnswers) for x in result)


@pytest.mark.asyncio
async def test_get_question_display(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.logic.get_question_display(poll_id=test_poll)
        assert all(isinstance(x, logic.Display) for x in result)