import pytest
from pydantic import ValidationError
from uuid import UUID

import os
from dotenv import load_dotenv
load_dotenv()

import socapi.config as sc
import socapi.client as cl

@pytest.mark.asyncio
async def test_success():
    config = sc.ParserConfig(
        constructor=os.environ["CONSTRUCTOR_NAME"],
        username=os.environ["USERNAME"],
        password=os.environ["PASSWORD"]
    )

    client = cl.ParserClient(config=config)

    async with client:
        questions_block = await client.questions.get_questions(parent_id=52910, mode="block")
        questions_poll = await client.questions.get_questions(parent_id=13924, mode="poll")

    print(questions_block)
    assert questions_block != questions_poll
