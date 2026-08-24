import pytest

import dotenv
dotenv.load_dotenv()
import os

import socapi
from socapi.resources import sources

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")

@pytest.mark.asyncio
async def test_get_sources(mocker):
    async with socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client:
        result = await client.source.get_sources()
        assert isinstance(result, list)
        assert all(isinstance(item, sources.Source) for item in result)