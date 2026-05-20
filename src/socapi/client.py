# Main public API

# client.py
from typing import List, Optional

from urllib.parse import urljoin

import asyncio

from .auth import AuthManager
from .config import ParserConfig

from .session import create_session
from .models.endpoints import EndpointType, Endpoint

from .resources.users import UsersResource
from .resources.roles import RolesResource, Role
from .resources.polls import PollResource, PollStatus
from .resources.meta import MetaResource
from .resources.questions import QuestionResource
from .tracer import Tracer

class ParserClient:
    def __init__(self, config: ParserConfig):

        self.config = config

        self._session = create_session(config)

        self.tracer = Tracer(enable=config.enable_tracer)

        self._auth = AuthManager(
            session=self._session,
            api_url=config.constructor.api_url,
            username=config.username,
            password=config.password,
            tracer=self.tracer,
        )

        self._semaphore = asyncio.Semaphore(
            config.max_concurrency
        )

        self.poll_statuses: Optional[List[PollStatus]] = None
        self.role_data: Optional[List[Role]] = None
        self.meta_data = None

        # resources
        self.users = UsersResource(self)
        self.roles = RolesResource(self)
        self.polls = PollResource(self)
        self.meta = MetaResource(self)
        self.questions = QuestionResource(self)


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
        self.tracer.add(name="_request_with_auth", method= method, url= url)
        token = await self._auth.get_token()

        headers = kwargs.pop("headers", {})

        headers.update({
            "authorization": f"{token}",
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
            urljoin(base_url, url),
            **kwargs,
        )

    async def meta_requests(self):

        self.role_data, self.poll_statuses, self.meta_data = await asyncio.gather(
            self.roles.get_role_list(),
            self.polls.get_poll_statuses(),
            self.meta.get_meta()
        )


