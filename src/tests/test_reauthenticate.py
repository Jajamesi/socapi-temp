import asyncio

import pytest

import dotenv
dotenv.load_dotenv()
import os

import socapi

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")


# @pytest.mark.asyncio
# async def test_profile(mocker):
#     async with socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client:
#         auth_spy = mocker.spy(client, "_request")
#
#         await client.authorize()
#         result = await client.user.profile()
#
#         print(result)
#
#         # assert isinstance(client.access_token, str)
#         # assert auth_spy.await_count == 1

@pytest.mark.parametrize(
    "login,password,auth_count,request_count",
    [
        pytest.param(
            login,
            password,
            1,
            1,
            id="init-authentication",
        ),

    ],
)
async def test_authorization_retry(mocker, login, password, auth_count, request_count):


    async with socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client:
        client_auth_spy = mocker.spy(client, "_authorize")
        user_request_spy = mocker.spy(client.user, "_request")


        await client.user.profile()

        assert client_auth_spy.await_count == auth_count
        assert user_request_spy.await_count == request_count



@pytest.mark.asyncio
async def test_auth_exceptions(mocker):


    async with socapi.ParserClient(login=login, password="wrong password", host="online-sociology.ru") as client:
        client_auth_spy = mocker.spy(client, "_authorize")
        user_request_spy = mocker.spy(client.user, "_request")

        try:
            await client.user.profile()
        except Exception as e:
            pass

        assert client_auth_spy.await_count == 1
        assert user_request_spy.await_count == 1



@pytest.mark.asyncio
async def test_async_authorization(mocker):

    async with socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client:
        client_auth_spy = mocker.spy(client, "_authorize")
        user_request_spy = mocker.spy(client.user, "_request")

        users = await asyncio.gather(
            client.user.profile(),
            client.user.profile()
        )

        assert client_auth_spy.await_count == 1
        assert user_request_spy.await_count == 2


