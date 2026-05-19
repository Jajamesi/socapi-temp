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
        await client.meta_requests()
        poll = await client.polls.get_poll(poll_id=13896)

    assert poll.uuid == UUID('3ccb90a4-483e-48cf-974b-9885ae701c26')
