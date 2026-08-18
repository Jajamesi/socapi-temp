import pytest

import dotenv
dotenv.load_dotenv()
import os

import socapi
from socapi.resources import pages

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")
test_poll = int(os.getenv("TEST_POLL", ""))

@pytest.mark.asyncio
async def test_get_pages(mocker):
    async with socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client:
        result = await client.page.get_pages(poll_id=test_poll)
        assert isinstance(result, list)
        assert all(isinstance(item, pages.Page) for item in result)

