
import asyncio
from urllib import response

import aiohttp
from dataclasses import dataclass
from pydantic import BaseModel, PrivateAttr, computed_field, model_validator, Field, HttpUrl, ConfigDict
import functools
from typing import List, Optional, Literal, Union, Any, Mapping, Dict, Callable, ParamSpec, TypeVar, Awaitable
from datetime import datetime, timedelta
from urllib.parse import urljoin
import random
from enum import StrEnum
import contextlib
from uuid import UUID

from . import config, exceptions

from .resources import user, pages, polls, blocks, questions

HttpMethod = Literal[
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
]


def retry(n_attempts=3, delay=1):
    """
    Retry decorated function in case of non-auth related errors
    :param n_attempts:
    :param delay:
    :return:
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(n_attempts):
                try:
                    return await func(*args, **kwargs)
                except (
                        aiohttp.ClientConnectionError,
                        aiohttp.ServerTimeoutError,
                        asyncio.TimeoutError,
                        aiohttp.ServerConnectionError,
                ) as e:
                    if attempt < n_attempts - 1:
                        await asyncio.sleep(delay * 2 ** attempt + random.uniform(0, 0.5))
                    else:
                        raise

        return wrapper

    return decorator


P = ParamSpec("P")
T = TypeVar("T")


def re_auth(
    func: Callable[P, Awaitable[T]],
) -> Callable[P, Awaitable[T]]:
    @functools.wraps(func)
    async def wrapper(self: "BaseResource", *args: P.args, **kwargs: P.kwargs) -> T:

        # run initial authentication if needed
        await self._client._initial_authorizing()

        try:
            return await func(self, *args, **kwargs)
        except (
            exceptions.InvalidTokenError,
            exceptions.MissingTokenError,
        ):
            await self._client._authorize()
            return await func(self, *args, **kwargs)

    return wrapper


class Request(BaseModel):
    """
    Validation class fot all requests to API
    """
    method: HttpMethod
    host: str
    endpoint: config.Endpoint
    access_token: Optional[str] = None
    data: Mapping[str, Any] | None = None
    json_: Mapping[str, Any] | None = None
    params: Mapping[str, Any] | None = None

    @computed_field
    @property
    def path(self) -> str:
        return urljoin(self.host, str(self.endpoint).lstrip("/"))

    @computed_field
    @property
    def headers(self) -> Dict[str, str]:
        h = {"user-agent":  "socapi"}
        if self.access_token:
            h["authorization"] = self.access_token
        return h


class Response(BaseModel):
    """
    API response structure
    """
    status: int
    error: Optional[str]
    result: Dict[str, Any]  | List[Any] | bool = Field(default_factory=list)


@dataclass
class ClientContext:
    """
    Store the common web params
    """
    session: aiohttp.ClientSession
    auth_token: str
    semaphore: asyncio.Semaphore




class ParserClient(BaseModel):
    """
    Main class that realizes underlying REST API requests
    Could be initialized directly with acces token or login password pair
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    host: config.ConstructorHost
    login: Optional[str] = None
    password: Optional[str] = None
    access_token: Optional[str] = None
    max_concurrency: int = Field(default=10, description="N of concurrent requests")

    # resource namespaces
    user: UserResource | None = None
    page: PageResource | None = None
    poll: PollResource | None = None
    block: BlockResource | None = None
    question: QuestionResource | None = None

    _session: Optional[aiohttp.ClientSession] = PrivateAttr(default=None)
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    _semaphore: asyncio.Semaphore = PrivateAttr()
    _constructor: config.Constructor = PrivateAttr()

    _token_expires_on: Optional[datetime] = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._constructor = config.Constructor(name=self.host)
        # resource namespaces
        self.user = UserResource(self)
        self.page = PageResource(self)
        self.poll = PollResource(self)
        self.block = BlockResource(self)
        self.question = QuestionResource(self)


    def _login_password_valid(self):
        return self.login is not None and self.password is not None


    @model_validator(mode="after")
    def validate_credentials(self):
        if not self._login_password_valid() and self.access_token is None:
            raise ValueError("Invalid auth credentials")


    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self


    async def __aexit__(self, *exc):
        await self._session.close()


    @retry()
    async def _request(self, request: Request) -> Response | str | bytes | None:
        kwargs = {
            "data": request.data,
            "json": request.json_,
            "params": request.params,
            "headers": request.headers
        }

        kwargs = {key: value for key, value in kwargs.items() if value is not None}

        async with self._semaphore:
            async with self._session.request(
                    request.method,
                    request.path,
                    **kwargs,
            ) as resp:



                content_type = resp.headers.get("Content-Type", "")
                if content_type.startswith("application/json"):
                    resp_json = Response(**await resp.json())

                    if resp.status >= 400:
                        raise exceptions.get_error(resp_json)

                    return  resp_json

                elif content_type.startswith("text/csv"):
                    return await resp.read()




                resp.raise_for_status()

                return None


    async def _authorize(self):
        request = Request(
            method="POST",
            host=self._constructor.admin_url,
            endpoint=config.Endpoint.login,
            json_={
                "login":self.login,
                "password":self.password,
            }
        )

        response = await self._request(request=request)

        self.access_token = response.result.get("session_token")
        self._token_expires_on = datetime.now() + timedelta(minutes=30)


    async def _initial_authorizing(self):
        """
        run with lock to prevent concurrent token check and reclaim
        """
        async with self._lock:
            if self.access_token is None:
                await self._authorize()



class BaseResource:
    """
    Parent class for specific resources to use. Handle common API structure
    """
    def __init__(self, client: ParserClient):
        self._client = client

    @re_auth
    async def _request(self, request: Request) -> Response:
        request.access_token = self._client.access_token
        return await self._client._request(request=request)



    async def _fetch_by_chunks(
            self,
            limit: int,
            process_chunk: Callable[..., T],
            request: Request,
            return_max: Optional[int] = 1000,
    ) -> List[T]:
        """
        Read paginated data one by one untill the end
        :param limit:
        :param process_chunk:
        :param kwargs:
        :return:
        """
        all_items = []
        offset = 0

        while True:
            request.json_["limit"] = limit
            request.json_["offset"] = offset
            chunk_data = await self._request(request=request)

            items: List[Any] = chunk_data.result # to be list

            all_items.extend(
                process_chunk(**item)
                for item in items
            )

            if (items_n:=len(items)) < limit:
                break

            offset += items_n

            if offset >= return_max:
                # Overflow handler
                break

        return all_items



class UserResource(BaseResource):
    async def profile(self) -> user.User:

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.profile,
        )
        r = await self._request(request=request)
        return user.User(**r.result)

    async def get_all(
            self,
            limit: int = 50,
            created_at: Optional[user.CreatedAtFilter] = None,
            disabled: bool | None = None,
            name: str | None = None,
            patronymic: str | None = None,
            role_id: int | None = None,
            login: str | None = None,
            phone: int | None = None,
            email: str | None = None,
            meta: list[Any] | None = None,
            return_max: Optional[int] = None,
    ) -> List[user.User]:
        payload = user.UserGetPayload(
            created_at=created_at,
            disabled=disabled,
            name=name,
            patronymic=patronymic,
            role_id=role_id,
            login=login,
            phone=phone,
            email=email,
            meta=meta,
        )

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.user_get,
            json_=payload.model_dump()
        )

        def parse_user(**data) -> user.User:
            return user.User(**data)

        r = await self._fetch_by_chunks(request=request, limit=limit, process_chunk=parse_user, return_max=return_max)
        return r


class PageResource(BaseResource):
    async def get_pages(self, poll_id: int) -> List[pages.Page]:
        payload = pages.GetPagesPayload(poll_id=poll_id)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.page_get,
            json_=payload.model_dump()
        )
        r = await self._request(request=request)
        return [pages.Page(**p) for p in r.result]


class PollResource(BaseResource):
    async def get_poll_head(self, poll_id: int) -> polls.Poll:
        payload = polls.GetPollHeaderPayload(id=poll_id)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.poll_header_get,
            json_=payload.model_dump()
        )
        r = await self._request(request=request)
        return polls.Poll(**r.result)


    async def get_poll_structure(self, poll_id: int) -> polls.Poll:

        poll, blocks_ = await asyncio.gather(
            self.get_poll_head(poll_id=poll_id),
            self._client.block.get_blocks(poll_id=poll_id)
        )

        # get questions for each block
        question_tasks = [
            self._client.question.get_block_question(block_id=block.id) for block in blocks_
        ]

        questions_ = await asyncio.gather(*question_tasks)

        for block, questions_ in zip(blocks_, questions_):
            block.questions = questions_

        poll.blocks = blocks_

        return poll


    async def _export_poll(self, poll_id: int) -> None:
        print("exporting", poll_id)
        payload = polls.ExportPayload(poll_id=poll_id)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.export_poll,
            json_=payload.model_dump()
        )
        await self._request(request=request)

    async def _download_poll(self, uuid: UUID):
        print("downloading", uuid)
        payload = polls.DownloadPayload(uuid=uuid)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.download_poll,
            json_=payload.model_dump(mode='json')
        )
        r = await self._request(request=request)
        return  r

    async def _done_poll(self, uuid: UUID):
        print("Done", uuid)
        payload = polls.DownloadPayload(uuid=uuid)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.done_poll,
            json_=payload.model_dump(mode='json')
        )
        await self._request(request=request)


    async def _progress(self) -> List[polls.ProgressStatus]:
        print("PROGRESS SENT")
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.progress,
            json_=None
        )
        r = await self._request(request=request)

        print("PROGRESS", r)

        return [polls.ProgressStatus(**s) for s in r.result]


    async def download_polls(
            self,
            poll_ids: List[int] | int,
            poll_interval: float = 5.0,
            max_concurrent: int = 5,
    ):
        semaphore = asyncio.Semaphore(max_concurrent)
        in_flight: set[int] = set()
        ready_events: dict[int, asyncio.Event] = {}
        ready_uuids: dict[int, UUID] = {} # from progress
        results: dict[int, bytes] = {}

        async def worker(poll_id: int) -> None:
            """
            Export one poll, waits for export, then download and send done
            """
            async with semaphore:
                await self._export_poll(poll_id)

                event = asyncio.Event()
                ready_events[poll_id] = event
                in_flight.add(poll_id)

                await event.wait()

                uuid = ready_uuids.pop(poll_id)

                results[poll_id] = await self._download_poll(uuid)
                await self._done_poll(uuid)

        async def poller() -> None:
            """
            Check export status and set ready_events
            """
            remaining = set(poll_ids)
            print("REMAINING", remaining)
            while remaining:
                if in_flight:
                    statuses = await self._progress()
                    print("STATUS", statuses)
                    for status in statuses:
                        if (poll_id:=status.params.poll_id) in in_flight and status.status == polls.ExportStatus.DONE:
                            in_flight.discard(poll_id)
                            remaining.discard(poll_id)
                            ready_uuids[poll_id] = status.uuid
                            ready_events[poll_id].set()

                if remaining:
                    await asyncio.sleep(poll_interval)

        worker_tasks = [asyncio.create_task(worker(poll_id)) for poll_id in poll_ids]
        poller_task = asyncio.create_task(poller())

        await asyncio.gather(*worker_tasks)
        poller_task.cancel()
        print("PROGRESS CANCELLED")
        with contextlib.suppress(asyncio.CancelledError):
            await poller_task
            print("POLLER ENDED")

        return results


class BlockResource(BaseResource):
    async def get_blocks(
            self,
            poll_id: int,
            includes: List[blocks.BlockInclude] = blocks.ALL_BLOCK_INCLUDES
    ) -> List[blocks.Block]:
        payload = blocks.GetBlocksPayload(poll_id=poll_id, includes=includes)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.blocks_by_poll_get,
            json_=payload.model_dump()
        )
        r = await self._request(request=request)
        return [blocks.Block(**b) for b in r.result]


class QuestionResource(BaseResource):
    async def get_block_question(
            self,
            block_id: int,
            includes: List[questions.QuestionInclude] = questions.ALL_QUESTION_INCLUDES):
        payload = questions.GetQuestionPayload(block_id=block_id, includes=includes)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.questions_by_block_get,
            json_=payload.model_dump()
        )
        r = await self._request(request=request)
        return [questions.Question(**q) for q in r.result]