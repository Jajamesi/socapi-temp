import pytest

import dotenv
dotenv.load_dotenv()
import os
from typing import List

import socapi
from socapi.resources import polls, blocks, questions

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")
test_poll = int(os.getenv("TEST_POLL", ""))

@pytest.mark.asyncio
async def test_get_poll_head(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.poll.get_poll_head(poll_id=test_poll)
        assert isinstance(result, polls.Poll)


@pytest.mark.asyncio
async def test_get_poll_structure(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.poll.get_poll_structure(poll_id=test_poll)
        assert isinstance(result, polls.Poll)
        assert isinstance(result.blocks, list)
        assert all(isinstance(b, blocks.Block) for b in result.blocks)
        assert isinstance(result.blocks[0].questions, list)
        assert all(isinstance(q, questions.Question) for q in result.blocks[0].questions)