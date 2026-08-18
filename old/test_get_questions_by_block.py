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
        questions = await client.questions._get_questions_by_block(block_id=52910)

    assert questions is not None
