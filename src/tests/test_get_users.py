import pytest
from pydantic import ValidationError
import aiohttp

import os
from dotenv import load_dotenv
load_dotenv()

import socapi.config as sc
import socapi.client as cl

@pytest.mark.asyncio
async def test_get_10_users_success():
    config = sc.ParserConfig(
        constructor=os.environ["CONSTRUCTOR_NAME"],
        username=os.environ["USERNAME"],
        password=os.environ["PASSWORD"]
    )

    client = cl.ParserClient(config=config)

    async with client:
        users_10 = await client.users.get_users()

    assert users_10 is not None


@pytest.mark.asyncio
async def test_get_100_users_success():
    config = sc.ParserConfig(
        constructor=os.environ["CONSTRUCTOR_NAME"],
        username=os.environ["USERNAME"],
        password=os.environ["PASSWORD"]
    )

    client = cl.ParserClient(config=config)

    async with client:
        users_100 = await client.users.get_users(limit=100)

    assert users_100 is not None