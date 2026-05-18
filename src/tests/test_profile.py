import pytest
from pydantic import ValidationError
import aiohttp

import os
from dotenv import load_dotenv
load_dotenv()

import socapi.config as sc
import socapi.session as ses

import socapi.client as cl

@pytest.mark.asyncio
async def test_login_success():
    config = sc.ParserConfig(
        constructor=os.environ["CONSTRUCTOR_NAME"],
        username=os.environ["USERNAME"],
        password=os.environ["PASSWORD"]
    )

    client = cl.ParserClient(config=config)

    async with client:
        await client._auth._login()

    assert client._auth._token is not None


@pytest.mark.asyncio
async def test_login_wrong_username():
    with pytest.raises(aiohttp.ClientResponseError) as exc:

        config = sc.ParserConfig(
            constructor=os.environ["CONSTRUCTOR_NAME"],
            username="wrong username",
            password=os.environ["PASSWORD"]
        )

        client = cl.ParserClient(config=config)

        async with client:
            await client._auth._login()


@pytest.mark.asyncio
async def test_login_wrong_username_and_password():
    with pytest.raises(aiohttp.ClientResponseError) as exc:

        config = sc.ParserConfig(
            constructor=os.environ["CONSTRUCTOR_NAME"],
            username="wrong username",
            password="wrong password"
        )

        client = cl.ParserClient(config=config)

        async with client:
            await client._auth._login()