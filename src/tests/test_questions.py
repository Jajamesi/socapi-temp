import pytest

import dotenv
dotenv.load_dotenv()
import os

import socapi
from socapi.resources import questions

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")
test_poll = int(os.getenv("TEST_POLL", ""))
test_block = int(os.getenv("TEST_BLOCK", ""))

@pytest.mark.asyncio
async def test_get_questions_by_block(mocker):
    async with socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client:
        result = await client.question.get_block_question(block_id=test_block)

        assert isinstance(result, list)
        assert all(isinstance(item, questions.Question) for item in result)