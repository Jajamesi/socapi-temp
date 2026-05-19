import pytest
from pydantic import ValidationError
import aiohttp

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

    assert client.role_data is not None
    assert client.poll_statuses is not None
    assert client.meta_data is not None
