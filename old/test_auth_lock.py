import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
import aiohttp

import os
from dotenv import load_dotenv
load_dotenv()

import socapi.config as sc
import socapi.session as ses

import socapi.client as cl
from socapi.auth import AuthManager
from socapi.tracer import Tracer


@pytest.mark.asyncio
async def test_auth_lock_allows_single_login():

    auth = AuthManager(
        session=None,
        api_url="http://test",
        username="user",
        password="pass",
        tracer=Tracer(enable=True)
    )

    login_calls = 0

    async def fake_login():
        nonlocal login_calls

        login_calls += 1

        # simulate slow network
        await asyncio.sleep(0.1)

        auth._token = "TOKEN"
        auth._expires_at = (
            datetime.now() + timedelta(minutes=30)
        )

    auth._login = AsyncMock(side_effect=fake_login)

    async def worker():
        return await auth.get_token()

    results = await asyncio.gather(
        *[worker() for _ in range(20)]
    )

    assert login_calls == 1
    assert all(r == "TOKEN" for r in results)