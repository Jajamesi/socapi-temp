# Main public API

# client.py

import asyncio

from .auth import AuthManager
from .config import ParserConfig
from .session import create_session
from .models.endpoints import EndpointType, Endpoints

class ParserClient:
    def __init__(self, config: ParserConfig):
        self.config = config

        self._session = create_session(config)

        self._auth = AuthManager(
            session=self._session,
            api_url=config.constructor.api_url,
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
        endpoint_type: EndpointType,
        url: str,
        **kwargs,
    ):
        async with self._semaphore:

            response = await self._request_with_auth(
                method,
                endpoint_type,
                url,
                ** kwargs,
            )

            # token expired
            if response.status == 401:
                response.release()

                await self._auth.force_refresh()

                response = await self._request_with_auth(
                    method,
                    endpoint_type,
                    url,
                    **kwargs,
                )

            response.raise_for_status()

            return response


    async def _request_with_auth(
            self,
            method,
            endpoint_type: EndpointType,
            url,
            **kwargs,
    ):
        token = await self._auth.get_token()

        headers = kwargs.pop("headers", {})

        headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": "socapi",
        })
        kwargs["headers"] = headers

        response = await self._make_request(
            method,
            endpoint_type,
            url,
            ** kwargs,
        )

        return response


    async def _make_request(
        self,
        method,
        endpoint_type: EndpointType,
        url: str,
        **kwargs,
    ):
        base_url = self.config.constructor.base_urls[endpoint_type]

        return await self._session.request(
            method,
            f"{base_url}{url}",
            **kwargs,
        )