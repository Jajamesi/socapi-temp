import pytest

import dotenv
dotenv.load_dotenv()
import os

import socapi
from socapi.resources import user

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")



@pytest.mark.parametrize(
    "limit,name,meta,return_max",
    [
        pytest.param(
            30,
            None,
            None,
            30,
            id="get-all-users"
        ),
        pytest.param(
            30,
            None,
            91,
            30,
            id="get-by-meta"
        ),
        pytest.param(
            30,
            "Александр",
            91,
            30,
            id="get-by-name"
        ),
    ]
)
async def test_get_users(mocker, limit, name, meta, return_max):
    async with socapi.ParserClient(
        login=login,
        password=password,
        host="online-sociology.ru",
    ) as client:
        result = await client.user.get_all(
            limit=limit,
            name=name,
            meta=meta,
            return_max=return_max
        )

        assert isinstance(result, list)
        assert all(isinstance(item, user.User) for item in result)
        assert len(result) <= return_max