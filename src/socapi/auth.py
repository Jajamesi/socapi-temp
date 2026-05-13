import asyncio
from datetime import datetime, timedelta


class AuthManager:
    def __init__(
        self,
        session,
        base_url,
        username,
        password,
    ):
        self._session = session
        self._base_url = base_url

        self._username = username
        self._password = password

        self._token = None
        self._expires_at = datetime.min

        self._lock = asyncio.Lock()

    def _is_valid(self):
        return (
            self._token is not None
            and datetime.utcnow() < self._expires_at
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
            f"{self._base_url}/login",
            json={
                "username": self._username,
                "password": self._password,
            },
        ) as response:

            response.raise_for_status()

            data = await response.json()

        self._token = data["token"]

        self._expires_at = (
            datetime.utcnow() + timedelta(minutes=30)
        )