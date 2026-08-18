
import pytest

import dotenv
dotenv.load_dotenv()
import os

import socapi
from socapi.resources import user

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")


@pytest.mark.asyncio
async def test_profile(mocker):
    async with socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client:
        result = await client.user.profile()
        assert isinstance(result, user.User)