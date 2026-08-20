import pytest

import dotenv
dotenv.load_dotenv()
import os
from typing import List

import socapi
from socapi.resources import counters

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")
test_poll = int(os.getenv("TEST_POLL", ""))

@pytest.mark.asyncio
async def test_get_counters(mocker):
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        result = await client.counter.get_counters(poll_id=test_poll)
        assert all(isinstance(x, counters.Counter) for x in result)