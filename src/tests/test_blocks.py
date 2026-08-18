import pytest

import dotenv
dotenv.load_dotenv()
import os

import socapi
from socapi.resources import blocks, polls

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")
test_poll = int(os.getenv("TEST_POLL", ""))

@pytest.mark.asyncio
async def test_get_blocks(mocker):
    async with socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client:
        result = await client.block.get_blocks(poll_id=test_poll)
        assert isinstance(result, list)
        assert all(isinstance(item, blocks.Block) for item in result)