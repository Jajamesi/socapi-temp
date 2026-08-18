import aiohttp
import pytest

import dotenv
dotenv.load_dotenv()
import os
import asyncio
import aiohttp

from socapi.client import retry

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")


@pytest.mark.parametrize(
    "exception",
    [
        aiohttp.ClientConnectionError,
        aiohttp.ServerTimeoutError,
        asyncio.TimeoutError,
        aiohttp.ServerConnectionError,
    ],
)
async def test_retry_backoff(mocker, exception):
    n_attempts = 3

    func = mocker.AsyncMock(side_effect=exception())
    sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    mocker.patch("random.uniform", return_value=0.25)

    decorated = retry(n_attempts=n_attempts)(func)

    with pytest.raises(exception):
        await decorated()

    assert func.await_count == n_attempts

    assert sleep.await_args_list == [
        mocker.call(1.25),
        mocker.call(2.25),
    ]

