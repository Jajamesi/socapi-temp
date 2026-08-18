import pytest
import asyncio

import os
from dotenv import load_dotenv
load_dotenv()

import socapi.config as sc
import socapi.client as cl
from old.models.endpoints import Actions


@pytest.mark.asyncio
async def test_async_load():
    config = sc.ParserConfig(
        constructor=os.environ["CONSTRUCTOR_NAME"],
        username=os.environ["USERNAME"],
        password=os.environ["PASSWORD"]
    )

    client = cl.ParserClient(config=config)

    async def worker():
        return await client.users.get_current_user()

    async with client:
        result = await asyncio.gather(
            *[worker() for _ in range(5)],
        )

    login_counts = 0
    for trace in client.tracer.traces:
        if trace.url == Actions.login:
            login_counts += 1
    assert login_counts == 1
