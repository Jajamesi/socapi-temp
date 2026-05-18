import asyncio
from datetime import datetime, timedelta

from .models.endpoints import Endpoints
from .models import auth

class AuthManager:
    def __init__(
        self,
        session,
        api_url,
        username,
        password,
    ):
        self._session = session
        self._api_url = api_url

        self._username = username
        self._password = password

        self._token = None
        self._expires_at = datetime.min

        self._lock = asyncio.Lock()

    def _is_valid(self):
        return (
            self._token is not None
            and datetime.now() < self._expires_at
        )

    async def get_token(self):
        if self._is_valid():
            return self._token

        async with self._lock:
            # double-check
            if self._is_valid():
                return self._token

            await self._login()

        return self._token

    async def force_refresh(self):
        async with self._lock:
            await self._login()

    async def _login(self):
        async with self._session.post(
            f"{self._api_url}{Endpoints.login}",
            json = auth.LoginPayload(
                login=self._username,
                password=self._password
            ).model_dump()
        ) as response:

            response.raise_for_status()

            data = await response.json()

        token = data.get("result", {}).get("session_token")
        if token is None:
            raise ValueError("Session token is None")
        self._token = token

        self._expires_at = (
            datetime.now() + timedelta(minutes=30)
        )