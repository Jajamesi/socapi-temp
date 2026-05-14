# Main public API

# client.py

import asyncio

from .auth import AuthManager
from .config import ParserConfig
from .session import create_session


class ParserClient:
    def __init__(self, config: ParserConfig):
        self.config = config

        self._session = create_session(config)

        self._auth = AuthManager(
            session=self._session,
            base_url=config.base_url,
            username=config.username,
            password=config.password,
        )

        self._semaphore = asyncio.Semaphore(
            config.max_concurrency
        )

    async def close(self):
        await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def request(
        self,
        method: str,
        url: str,
        **kwargs,
    ):
        async with self._semaphore:
            token = await self._auth.get_token()

            headers = kwargs.pop("headers", {})

            headers["Authorization"] = (
                f"Bearer {token}"
            )

            response = await self._make_request(
                method,
                url,
                headers=headers,
                **kwargs,
            )

            # token expired
            if response.status == 401:
                response.release()

                await self._auth.force_refresh()

                token = await self._auth.get_token()

                headers["Authorization"] = (
                    f"Bearer {token}"
                )

                response = await self._make_request(
                    method,
                    url,
                    headers=headers,
                    **kwargs,
                )

            response.raise_for_status()

            return response

    async def _make_request(
        self,
        method,
        url,
        **kwargs,
    ):
        return await self._session.request(
            method,
            f"{self.config.base_url}{url}",
            **kwargs,
        )