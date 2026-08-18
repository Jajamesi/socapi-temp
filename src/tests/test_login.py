
import pytest

import dotenv
dotenv.load_dotenv()
import os

import socapi

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")


@pytest.mark.parametrize(
    "login,password,expected_exception",
    [
        pytest.param(
            login,
            password,
            None,
            id="valid-login-password",
        ),
        pytest.param(
            None,
            None,
            ValueError,
            id="no-credentials",
        ),
        pytest.param(
            "user",
            None,
            ValueError,
            id="login-without-password",
        ),
        pytest.param(
            None,
            "password",
            ValueError,
            id="password-without-login",
        ),
        pytest.param(
            login,
            "password",
            socapi.exceptions.InvalidCredentialsError,
            id="wrong-password",
        ),
        pytest.param(
            "login",
            password,
            socapi.exceptions.InvalidCredentialsError,
            id="wrong-login",
        ),
    ],
)
async def test_credentials_authorize(mocker, login, password, expected_exception):

    async def run_auth():
        async with socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client:
            auth_spy = mocker.spy(client, "_request")

            await client._authorize()

            assert isinstance(client.access_token, str)
            assert auth_spy.await_count == 1


    if expected_exception:
        with pytest.raises(expected_exception):
            await run_auth()

    else:
        await run_auth()