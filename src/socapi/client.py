from __future__ import annotations

import asyncio
from urllib import request

import aiohttp
from dataclasses import dataclass

from pydantic import BaseModel, PrivateAttr, computed_field, model_validator, Field, ConfigDict, validate_call
import functools
from typing import List, Optional, Literal, Any, Mapping, Dict, Callable, ParamSpec, TypeVar, Awaitable, Concatenate
from datetime import datetime, timedelta
from urllib.parse import urljoin
import random
import contextlib
from uuid import UUID

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from socapi.resources.sources import Sources
from . import config, exceptions
from .utils import IdMap

from .resources import user, pages, polls, blocks, questions, logic, counters, sources, meta

TOKEN_TTL = 30 # strict token TTL
MAX_CHUNK_SIZE = 1000 # N items to return paginated resources
HttpMethod = Literal[
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
]
"""HTTP verbs accepted by the constructor API."""

P = ParamSpec("P")
T = TypeVar("T")

def retry(n_attempts: int = 3, delay: float = 1):
    """
    Retry the decorated coroutine when it fails with a transient connection
    or timeout error. API-level errors (e.g. 4xx/5xx responses that raise
    ``exceptions.*Error``) are intentionally NOT retried here, only network
    level failures.

    Uses exponential backoff with jitter: ``delay * 2 ** attempt`` plus a
    random 0-0.5s offset, to avoid a thundering herd on the API.

    :param n_attempts: total number of attempts (including the first one).
    :param delay: base delay in seconds before the backoff multiplier.
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
            return None

        return wrapper

    return decorator


def re_auth(
    func: Callable[Concatenate["BaseResource", P], Awaitable[T]],
) -> Callable[Concatenate["BaseResource", P], Awaitable[T]]:
    """
    Wrap a ``BaseResource`` method so it transparently (re)authenticates.

    On first call this makes sure the owning :class:`ParserClient` has run
    its initial authorization. If the wrapped call fails because the token
    is missing or invalid, the client re-authorizes once and the call is
    retried exactly one more time.
    """

    @functools.wraps(func)
    async def decorator(self: "BaseResource", *args: P.args, **kwargs: P.kwargs) -> T:
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

    return decorator


class Request(BaseModel):
    """
    Validation/normalization wrapper for every request sent to the API.

    NOTE: ``host`` and ``endpoint`` are combined with ``urllib.parse.urljoin``
    in :attr:`path`. ``urljoin`` treats the last path segment of ``host`` as
    a "file" and drops it if ``host`` doesn't end in ``/`` (e.g.
    ``urljoin("https://x.com/api", "foo") == "https://x.com/foo"``, not
    ``.../api/foo``). Make sure ``host`` values coming from
    ``config.Constructor`` always end with a trailing slash.
    """

    method: HttpMethod
    host: str
    endpoint: config.Endpoint
    access_token: Optional[str] = None
    data: Mapping[str, Any] | None = None
    # Mutated in-place for pagination (see BaseResource._fetch_by_chunks),
    # hence Dict rather than the read-only Mapping used by data/params.
    json_: Dict[str, Any] | List[Dict[str, Any]] |None = None
    params: Mapping[str, Any] | None = None

    @computed_field
    @property
    def path(self) -> str:
        """Full request URL built from ``host`` and ``endpoint``."""
        return urljoin(self.host, str(self.endpoint).lstrip("/"))

    @computed_field
    @property
    def headers(self) -> Dict[str, str]:
        """Request headers, including bearer auth when a token is set."""
        h = {"user-agent":  "socapi"} # for explicit marker on server side
        if self.access_token:
            h["authorization"] = self.access_token
        return h


class Response(BaseModel):
    """Parsed JSON envelope returned by the constructor API."""
    status: int
    error: Optional[str]
    result: Dict[str, Any]  | List[Any] | bool | None = Field(default_factory=list)


@dataclass
class ClientContext:
    """
    Bundle of the common per-request web params (session, token, semaphore).

    Not currently implemented anywhere - resources reach these
    values through ``self._client`` instead. Kept in case a future refactor
    wants to pass a lightweight context object into resources instead of the
    whole client.
    """

    session: aiohttp.ClientSession
    auth_token: str
    semaphore: asyncio.Semaphore


class ParserClient(BaseModel):
    """
    Main entry point for the constructor REST API.

    Can be initialized either with a ready-made ``access_token`` or with a
    ``login``/``password`` pair (in which case authorization happens lazily
    on the first request with required authentication). Individual API areas are exposed as
    resource namespaces, e.g. ``client.poll.get_poll_structure(...)``.

    Usage::

        async with ParserClient(host=..., login=..., password=...) as client:
            poll = await client.poll.get_poll_structure(poll_id=123)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    host: config.ConstructorHost
    login: Optional[str] = None
    password: Optional[str] = None
    access_token: Optional[str] = None
    max_concurrency: int = Field(default=10, description="N of concurrent requests")
    download_timeout: int = Field(default=600, description="Single poll export timeout")

    # resource namespaces
    user: UserResource = None
    page: PageResource = None
    poll: PollResource = None
    block: BlockResource = None
    question: QuestionResource = None
    logic: LogicResource = None
    counter: CounterResource = None
    source: SourceResource = None
    meta: MetaResource = None

    _session: Optional[aiohttp.ClientSession] = PrivateAttr(default=None)
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    _semaphore: asyncio.Semaphore = PrivateAttr()
    _constructor: config.Constructor = PrivateAttr()

    _token_expires_on: Optional[datetime] = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        """Wire up the concurrency primitives and resource namespaces."""
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._constructor = config.Constructor(name=self.host)
        # resource namespaces
        self.user = UserResource(self)
        self.page = PageResource(self)
        self.poll = PollResource(self)
        self.block = BlockResource(self)
        self.question = QuestionResource(self)
        self.logic = LogicResource(self)
        self.counter = CounterResource(self)
        self.source =  SourceResource(self)
        self.meta = MetaResource(self)


    def _login_password_valid(self) -> bool:
        """True if both ``login`` and ``password`` were provided."""
        return self.login is not None and self.password is not None


    @model_validator(mode="after")
    def validate_credentials(self) -> "ParserClient":
        """Require either an access token or a login/password pair."""
        if not self._login_password_valid() and self.access_token is None:
            raise ValueError("Invalid auth credentials")
        return self


    async def __aenter__(self) -> "ParserClient":
        self._session = aiohttp.ClientSession()
        return self


    async def __aexit__(self, *exc) -> None:
        await self._session.close()


    @retry()
    async def _request(self, request: Request) -> Response | str | bytes | None:
        """
        Perform the actual HTTP call for ``request``, bounded by the
        client's concurrency semaphore.

        Returns a parsed :class:`Response` for JSON payloads, raw ``bytes``
        for CSV payloads (e.g. poll exports), or ``None`` for any other
        successful response with no body to parse.

        :raises exceptions.*Error: for JSON responses with ``status >= 400``.
        """

        # kwargs = {
        #     "data": request.data,
        #     "json": request.json_,
        #     "params": request.params,
        #     "headers": request.headers
        # }
        #
        # kwargs = {key: value for key, value in kwargs.items() if value is not None}

        if self._session is None:
            raise RuntimeError("ParserClient must be used as an async context manager")

        async with self._semaphore:
            async with self._session.request(
                    request.method,
                    request.path,
                    data=request.data,
                    json=request.json_,
                    params=request.params,
                    headers=request.headers,
            ) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if content_type.startswith("application/json"):
                    parsed = Response(**await resp.json())

                    if resp.status >= 400:
                        raise exceptions.get_error(parsed)

                    return  parsed

                elif any([
                    content_type.startswith("text/csv"),
                    content_type.startswith("application/x-spss-sav"),
                    content_type.startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    ]
                ):
                    return await resp.read()

                resp.raise_for_status()
                return None


    async def _authorize(self) -> None:
        """Log in with ``login``/``password`` and store the session token."""
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

        assert isinstance(response, Response)
        assert isinstance(response.result, dict)

        self.access_token = response.result.get("session_token")
        self._token_expires_on = datetime.now() + timedelta(minutes=TOKEN_TTL)


    async def _initial_authorizing(self) -> None:
        """
        Authorize once if no token is set yet.

        Runs under a lock so concurrent callers don't race to check-and-set
        the token, which would otherwise trigger duplicate login requests.
        """
        async with self._lock:
            if self.access_token is None:
                await self._authorize()


class BaseResource:
    """Parent class for specific resources. Handles the common request/auth plumbing."""

    def __init__(self, client: ParserClient):
        self._client = client

    @re_auth
    async def _request(self, request: Request) -> Response | str | bytes | None:
        """Attach the current access token and delegate to the client."""
        request.access_token = self._client.access_token
        return await self._client._request(request=request)


    async def _fetch_by_chunks(
            self,
            limit: int,
            process_chunk: Callable[..., T],
            request: Request,
            return_max: Optional[int] = MAX_CHUNK_SIZE,
    ) -> List[T]:
        """
        Page through a paginated endpoint until it runs out of items,
        parsing each raw item with ``process_chunk``.

        :param limit: page size sent as ``limit`` in the request body.
        :param process_chunk: called as ``process_chunk(**item)`` for every
            raw item in a page; typically a model constructor.
        :param request: base request to page through. Its ``json_`` dict is
            mutated in place to set ``limit``/``offset`` on every iteration.
        :param return_max: stop once at least this many items have been
            fetched. ``None`` means no cap - keep going until the API
            returns a short (final) page.
        """

        all_items: List[T] = []
        offset = 0

        while True:
            request.json_["limit"] = limit
            request.json_["offset"] = offset
            chunk_data = await self._request(request=request)

            items: List[Any] = chunk_data.result # has to be list

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
    """API area for the operator/user directory."""

    async def profile(self) -> user.User:
        """Fetch the profile of the currently authenticated user."""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.profile,
        )
        response = await self._request(request=request)
        return user.User(**response.result)


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
        """
        List users matching the given filters, paginating automatically.

        :param limit: page size for the underlying paginated requests.
        :param return_max: stop after roughly this many users; ``None``
            fetches every matching user.
        """
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

        return await self._fetch_by_chunks(
            request=request, limit=limit, process_chunk=parse_user, return_max=return_max
        )

    async def get_one(
            self,
            created_at: Optional[user.CreatedAtFilter] = None,
            disabled: bool | None = None,
            name: str | None = None,
            patronymic: str | None = None,
            role_id: int | None = None,
            login: str | None = None,
            phone: int | None = None,
            email: str | None = None,
            meta: list[Any] | None = None,
    ) -> user.User | None:
        """
        Return exactly one user.

        """
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

        result = await self._fetch_by_chunks(
            request=request, limit=1, process_chunk=parse_user, return_max=1
        )

        if len(result)==1:
            return result[0]
        elif len(result)==0:
            return None
        return None


class PageResource(BaseResource):
    """API area for survey pages - start / finish / disqualified."""

    async def get_pages(self, poll_id: int) -> List[pages.Page]:
        """List all pages belonging to ``poll_id``."""
        payload = pages.GetPagesPayload(poll_id=poll_id)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.page_get,
            json_=payload.model_dump()
        )
        response = await self._request(request=request)
        return [pages.Page(**p) for p in response.result]

    async def create_page(self, page: pages.Page) -> pages.Page:
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.create_page,
            json_=page.dump_create_payload()
        )
        response = await self._request(request=request)
        return pages.Page(**response.result)


class PollResource(BaseResource):
    """API area for poll (survey) metadata, structure and export."""

    async def get_poll_head(self, poll_id: int) -> polls.Poll:
        """Fetch just the poll header (no nested blocks/questions/logic)."""
        payload = polls.GetPollHeaderPayload(id=poll_id)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.poll_header_get,
            json_=payload.model_dump()
        )
        response = await self._request(request=request)
        return polls.Poll(**response.result)


    async def get_poll_structure(self, poll_id: int) -> polls.Poll:
        """
        Assemble the full poll: header, blocks, questions, logic, counters
        and pages, fetched concurrently and stitched together.
        """
        poll, poll_blocks = await asyncio.gather(
            self.get_poll_head(poll_id=poll_id),
            self._client.block.get_blocks(poll_id=poll_id)
        )

        # get questions for each block
        question_tasks = [
            self._client.question.get_block_question(block_id=block.id) for block in poll_blocks
        ]
        questions_lists = await asyncio.gather(*question_tasks)

        for block, block_questions in zip(poll_blocks, questions_lists):
            block.questions = block_questions

        poll.blocks = poll_blocks

        # get logics, counters and bind to questions
        (poll.jumps,
         poll.displays,
         poll.display_answers,
         poll.counters,
         poll.pages,
         ) = await asyncio.gather(
            self._client.logic.get_jumps(poll_id=poll_id),
            self._client.logic.get_question_display(poll_id=poll_id),
            self._client.logic.get_answer_display(poll_id=poll_id),
            self._client.counter.get_counters(poll_id=poll_id),
            self._client.page.get_pages(poll_id=poll_id),
        )

        # bind parent poll to every nested item to have access to logics
        poll = polls.Poll.model_validate(poll)

        return poll

    async def _export_poll(
            self,
            poll_id: int,
            export_format: polls.ExportFormat | polls.EXPORT_FORMATS = polls.ExportFormat.CSV,
            filter_: polls.ExportFilter = polls.ExportFilter()
    ) -> None:
        """Kick off an async export job for ``poll_id`` on the server side."""
        payload = polls.ExportPayload(
            poll_id=poll_id,
            format_id=export_format,
            filter=filter_
        )

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.export_poll,
            json_=payload.model_dump()
        )
        await self._request(request=request)

    async def _download_poll(self, uuid: UUID) -> bytes:
        """Download the finished export identified by ``uuid`` as raw CSV bytes / Excel workbook / SPSS binary."""
        payload = polls.DownloadPayload(uuid=uuid)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.download_poll,
            json_=payload.model_dump(mode='json')
        )
        return await self._request(request=request)

    async def _done_poll(self, uuid: UUID) -> None:
        """Acknowledge the export ``uuid`` as consumed/finished on the server."""
        payload = polls.DownloadPayload(uuid=uuid)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.done_poll,
            json_=payload.model_dump(mode='json')
        )
        await self._request(request=request)

    async def _progress(self) -> List[polls.ProgressStatus]:
        """Fetch the current status of all in-progress export jobs."""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.progress,
        )
        response = await self._request(request=request)
        return [polls.ProgressStatus(**status) for status in response.result]

    @validate_call
    async def download_polls(
            self,
            poll_ids: List[int] | int,
            export_format: polls.ExportFormat | polls.EXPORT_FORMATS = polls.ExportFormat.CSV,
            poll_interval: float | int = 5.0,
            max_concurrent: int = 5,
    ) -> Dict[int, bytes]:
        """
        Export and download several polls concurrently.

        For each poll: triggers an export job, waits until a shared poller
        task observes it as ``DONE`` via :meth:`_progress`, then downloads
        the file and marks the export as consumed.

        :param poll_ids: one poll id or a list of them. Duplicates are
            dropped (order-preserving) since two in-flight exports for the
            same poll id would overwrite each other's "ready" event.
        :param poll_interval: seconds between progress polls.
        :param max_concurrent: max number of exports triggered at once.
        :return: mapping of poll id to the downloaded CSV bytes. If any exception occurs, it will be returned instead.
        """

        if isinstance(poll_ids, int):
            poll_ids = [poll_ids]
        else:
            poll_ids = list(dict.fromkeys(poll_ids))  # de-dupe, preserve order

        semaphore = asyncio.Semaphore(max_concurrent)
        in_flight: set[int] = set()
        ready_events: dict[int, asyncio.Event] = {}
        ready_uuids: dict[int, UUID] = {}  # from progress
        results: dict[int, bytes] = {}

        async def worker(poll_id: int) -> None:
            """Export one poll, wait for it to be ready, then download and acknowledge it."""
            async with semaphore:
                last_exc: Exception | None = None
                for attempt in range(1, 4):  # up to 3 tries
                    event = asyncio.Event()
                    ready_events[poll_id] = event
                    try:
                        async with asyncio.timeout(self._client.download_timeout):
                            await self._export_poll(poll_id, export_format=export_format)
                            in_flight.add(poll_id)
                            await event.wait()
                            uuid = ready_uuids.pop(poll_id)
                            results[poll_id] = await self._download_poll(uuid)
                            await self._done_poll(uuid)
                        return  # success
                    except TimeoutError as exc:
                        # TBD if orphaned export will stale server side.
                        # Consider _done_poll() call on staled export
                        last_exc = exc
                        in_flight.discard(poll_id)  # stop poller from reacting on not awaited export
                        ready_events.pop(poll_id, None)
                        ready_uuids.pop(poll_id, None)
                        continue
                raise last_exc

        async def poller() -> None:
            """Periodically check export status and unblock finished workers."""
            remaining = set(poll_ids)
            while remaining:
                if in_flight:
                    statuses = await self._progress()
                    for status in statuses:
                        if (poll_id := status.params.poll_id) in in_flight and status.status == polls.ExportStatus.DONE:
                            in_flight.discard(poll_id)
                            remaining.discard(poll_id)
                            ready_uuids[poll_id] = status.uuid
                            ready_events[poll_id].set()

                if remaining:
                    await asyncio.sleep(poll_interval)

        worker_tasks = [asyncio.create_task(worker(poll_id)) for poll_id in poll_ids]
        poller_task = asyncio.create_task(poller())

        await asyncio.gather(*worker_tasks, return_exceptions=True)
        poller_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poller_task

        return results

    async def download_repeat_passages(self, poll_id: int) -> None:
        """Download csv with duplicated sessions"""
        payload = polls.ExportRepeatPassagesPayload(poll_id=poll_id)
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.repeat_passages,
            json_=payload.model_dump(mode='json')
        )
        return await self._request(request=request)


    async def update_meta(self, poll_id: int, meta: List[int]) -> polls.Poll:
        """Modify poll access level."""
        payload = polls.UpdateMeta(id=poll_id, meta=meta)
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.update_meta,
            json_=payload.model_dump(mode='json')
        )
        response = await self._request(request=request)
        return polls.Poll(**response.result)

    async def duplicate(self, poll_id: int, with_counters: bool = True, update_meta: bool = True) -> polls.Poll:
        """Duplicate poll using internall API. Returns Poll instance. Uses follow-up meta update request."""
        payload = polls.DuplicatePollPayload(id=poll_id, with_counters=with_counters)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.duplicate_poll,
            json_=payload.model_dump()
        )
        # get parent poll data and duplicate concurrent
        parent_poll, dup_response = await asyncio.gather(
            self.get_poll_head(poll_id=poll_id),
            self._request(request=request)
        )

        child_poll = polls.Poll(**dup_response.result)

        if update_meta:
            upd_poll = await self.update_meta(poll_id=child_poll.id, meta=parent_poll.meta)
            return upd_poll

        return child_poll

    async def create_personal_links(self, poll_id: int, link_count: int = Field(..., ge=1, le=5000)) -> None:
        """Create additional invitation links."""
        payload = polls.CreatePersonalLinks(link_count=link_count, poll_id=poll_id)
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.create_personal_links,
            json_=payload.model_dump()
        )
        await self._request(request=request)

    async def _update_poll(
            self,
            poll_id: int,
            background: Optional[polls.BackgroundColor] = None,
            can_cameback: Optional[bool] = None,
            description: Optional[str] = None,
            domain_id: Optional[int] = None,
            field_date: Optional[datetime] = None,
            is_multiple: Optional[bool] = None,
            language_id: Optional[int] = None,
            meta: Optional[list[int]] = None,
            name: Optional[str] = None,
            notify_flag: Optional[bool] = None,
            poll_responsible: Optional[int] = None,
            source_id: Optional[str] = None,
            state_id: Optional[int] = None,
            status_id: Optional[polls.PollStatus] = None,
            title: Optional[str] = None,
            type_id: Optional[polls.PollType] = None,
    ) -> polls.Poll:
        """
        Update the specified fields of a poll.

        Only arguments explicitly provided with a non-None value are included
        in the update payload. The ``poll_id`` identifies the poll to update.
        """

        payload = polls.UpdatePollPayload(
            id=poll_id,
            background=background,
            can_cameback=can_cameback,
            description=description,
            domain_id=domain_id,
            field_date=field_date,
            is_multiple=is_multiple,
            language_id=language_id,
            meta=meta,
            name=name,
            notify_flag=notify_flag,
            poll_responsible=poll_responsible,
            source_id=source_id,
            state_id=state_id,
            status_id=status_id,
            title=title,
            type_id=type_id,
        )

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.update_poll,
            json_=payload.model_dump(exclude_none=True),
        )

        result = await self._request(request=request)
        return polls.Poll(**result.result)


    async def change_poll_status(
            self,
            poll_id: int,
            status: polls.PollStatus | Literal["active", "closed", "published", "deleted"]
    ) -> polls.Poll:
        """Change Poll publication status."""
        if isinstance(status, str):
            status = polls.PollStatus[status.upper()]
        return await self._update_poll(poll_id=poll_id, status_id=status)


    async def create_poll(self, poll: polls.Poll) -> polls.Poll:
        """Change Poll template"""
        request = Request(
                    method="POST",
                    host=self._client._constructor.admin_url,
                    endpoint=config.Endpoint.create_poll,
                    json_=poll.dump_create_payload()
                )
        result = await self._request(request=request)
        return polls.Poll(**result.result)

    async def _upload_question(self, question, ids: IdMap) -> None:
        """Create one question, its matrix rows (sent with it); register their real ids."""
        draft_id = question.id
        created = await self._client.question.create_question(question)
        question.id, question.created_at = created.id, created.created_at
        ids.register(draft_id, question.id)

        # update related answers
        for answer in question.answers:
            answer.question_id = question.id

        # matrix rows come back inside the create-question response, in order
        created_rows = sorted(created.children or [], key=lambda c: c.order)
        draft_rows = sorted(question.children or [], key=lambda c: c.order)
        if len(created_rows) != len(draft_rows):
            raise exceptions.UnknownError(
                status=0,
                error=f"question {question.title!r}: sent {len(draft_rows)} rows, server returned {len(created_rows)}",
            )
        for draft_row, created_row in zip(draft_rows, created_rows):
            ids.register(draft_row.id, created_row.id)
            draft_row.id, draft_row.parent_id, draft_row.block_id = created_row.id, question.id, question.block_id

    async def _upload_logic(self, poll: polls.Poll, ids: IdMap, progress_callback: Callable, exc_handler: Callable) -> None:
        """Create jumps, question displays and answer displays with every reference translated to real ids."""
        for i, rule in enumerate(poll.displays, start=1):
            self._remap_logic(rule, poll, ids)
            try:
                rule.id = (await self._client.logic.create_question_display(rule)).id
            except Exception as e:
                exc_handler(f"Display logic with id={rule.id} creation", e)
            progress_callback(f"display {i} created")
        for i, rule in enumerate(poll.jumps, start=1):
            self._remap_logic(rule, poll, ids)
            try:
                rule.id = (await self._client.logic.create_jump(rule)).id
            except Exception as e:
                exc_handler(f"Jump logic with id={rule.id} creation", e)
            progress_callback(f"jump {i} created")
        for i, rule in enumerate(poll.display_answers, start=1):
            self._remap_logic(rule, poll, ids)
            try:
                rule.id = (await self._client.logic.create_answer_display(rule)).id
            except Exception as e:
                exc_handler(f"Display answer logic with id={rule.id} creation", e)
            progress_callback(f"display answer {i} created")

    @staticmethod
    def _remap_logic(rule, poll: polls.Poll, ids: IdMap) -> None:
        """Replace every draft id inside ``rule`` with the real one (real ids pass through)."""
        rule.poll_id = poll.id
        rule.reference_question_id = ids[rule.reference_question_id]
        rule.reference_answer_id = [ids[i] for i in rule.reference_answer_id]
        for attr in ("question_id", "answer_id", "target_question_id", "target_page_id"):
            value = getattr(rule, attr, None)
            if value is not None:
                setattr(rule, attr, ids[value])

    async def upload_poll(self, poll: polls.Poll, *, verbose: bool = False) -> polls.Poll:
        """
        Create a poll built from scratch (see ``Poll.add_block`` /
        ``Block.add_question`` / ``Question.add_display`` ...) on the server.

        The constructor generates ids, so everything that refers to another
        item is created strictly one request after another, in dependency order::

            poll -> blocks -> questions (+ matrix rows) -> answers -> logic

        Temporary draft ids are translated to the real ids returned by the
        server as we go, and written back onto the objects you passed in -
        so after a successful upload ``poll``, its blocks, questions,
        answers and logic rules carry real ids and ``question.jumps`` /
        ``question.displays`` keep working.

        Not transactional: if a request fails, :class:`exceptions.PollUploadError`
        is raised and the partially created poll stays on the server
        (``error.poll_id``; remove it with ``change_poll_status(..., "deleted")``).
        The draft is then half-converted and should be rebuilt before a retry.

        Counters, pages and sources are not uploaded.

        :raises ValueError: the poll was already uploaded, or its logic references
            items that are not part of it (checked before any request is sent).
        :raises exceptions.PollUploadError: a request failed.
        """
        if not poll.is_draft:
            raise ValueError(f"Poll already exists on the server (id={poll.id}); only drafts can be uploaded.")
        poll.validate_draft()

        # number of items to create for progress bar
        total = (
                1  # poll
                + len(poll.pages)
                + len(poll.blocks)
                + sum(len(block.questions) for block in poll.blocks)
                + sum(len(question.answers) if question.answers else 0 for question in poll.questions)
                + len(poll.jumps)
                + len(poll.displays)
                + len(poll.display_answers)
                + len(poll.counters)
        )

        # map of draft ids to created ones by constructor API
        ids = IdMap()

        progress = None
        task = None

        if verbose:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
            )
            progress.start()
            task = progress.add_task("Creating poll...", total=total)

        def update(description: str) -> None:
            """
            Called in each item creation function to indicate overall process
            """
            if progress is not None and task is not None:
                progress.update(
                    task,
                    description=description,
                    advance=1,
                )

        def raise_upload_exception(stage: str, exc: Exception) -> None:
            """
            Manage API call fails by specifing failed element id and traceback
            """
            raise exceptions.PollUploadError(
                f"Poll upload failed at {stage}: {exc}", poll_id=poll.id, stage=stage
            ) from exc

        def upload_step(
                stage: str | Callable[..., str],
                success: str | Callable[..., str],
        ):
            """
            Decorator handles exception for element creation and pushing progress bar
            """
            def decorator(
                    func: Callable[P, Awaitable[T]],
            ) -> Callable[P, Awaitable[T]]:
                @functools.wraps(func)
                async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                    try:
                        result = await func(*args, **kwargs)
                    except Exception as exc:
                        actual_stage = (
                            stage(*args, **kwargs)
                            if callable(stage)
                            else stage
                        )
                        raise_upload_exception(actual_stage, exc)

                    description = (
                        success(*args, **kwargs)
                        if callable(success)
                        else success
                    )
                    update(description)

                    return result

                return wrapper

            return decorator

        @upload_step(
            stage="poll",
            success="Poll created",
        )
        async def create_poll_with_progress(poll_: polls.Poll) -> None:
            """
            Create new Poll instance in constructor and set actual fields from response to poll instance.
            """
            new_poll = await self.create_poll(poll=poll_)

            poll_.id, poll_.uuid = new_poll.id, new_poll.uuid
            poll_.created_at, poll_.updated_at = new_poll.created_at, new_poll.updated_at

        @upload_step(
            stage=lambda page: f"page {page.name!r}",
            success=lambda page: f"Page {page.name!r} created",
        )
        async def create_page_with_progress(page: pages.Page) -> None:
            """
            Create new Page instance in constructor and set actual fields from response to poll instance.
            """
            draft_id = page.id
            page.poll_id = page._poll.id
            new_page = await self._client.page.create_page(page)
            page.id = new_page.id
            ids.register(draft_id, new_page.id)

        @upload_step(
            stage=lambda block: f"block {block.name!r}",
            success=lambda block: f"Block {block.name!r} created",
        )
        async def create_block_with_progress(block: blocks.Block) -> None:
            """
            Create new Block instance in constructor and set actual fields from response to poll instance.
            Map draft IDs to newly created actual constructor's IDs
            """
            draft_id = block.id
            block.poll_id = poll.id

            created_block = await self._client.block.create_block(block)

            block.id = created_block.id
            block.created_at = created_block.created_at

            # update block id of related questions
            for question in block.questions:
                question.block_id = block.id

            ids.register(draft_id=draft_id, real_id=block.id)


        @upload_step(
            stage=lambda question: f"question {question.title!r}",
            success=lambda question: f"Question {question.title!r} created",
        )
        async def create_question_with_progress(question: questions.Question) -> None:
            """
            Create new Question and it's children instances in constructor.
            Map draft IDs to newly created actual constructor's IDs
            """
            await self._upload_question(question, ids=ids)

        @upload_step(
            stage=lambda answer, question: f"question {question.title!r} answer {answer.title!r}",
            success=lambda answer, question: f"Question {question.title!r} Answer {answer.title!r} created",
        )
        async def create_answer_with_progress(answer: questions.Answer, question: questions.Question) -> None:
            """
            Create new Answer instance in constructor.
            Map draft IDs to newly created actual constructor's IDs
            """
            draft_answer_id = answer.id
            created_answer = await self._client.question.create_answer(answer)
            answer.id = created_answer.id
            ids.register(draft_id=draft_answer_id, real_id=answer.id)


        @upload_step(
            stage=lambda counter: f"counter {counter.name!r}",
            success=lambda counter: f"Counter {counter.name!r} created",
        )
        async def create_counters_with_progress(counter: counters.Counter) -> None:
            """
            Create new Counter instance in constructor.
            """
            counter.poll_id = poll.id
            created_counter = await self._client.counter.create_counter(counter)
            counter.id = created_counter.id


        # Create instance of poll
        await create_poll_with_progress(poll_=poll)

        # Create pages. Could be executed asynchronous since no race overlap
        await asyncio.gather(
            *(create_page_with_progress(page) for page in poll.pages)
        )

        # Create blocks asynchronous since they are independent
        await asyncio.gather(
            *(create_block_with_progress(block) for block in poll.blocks)
        )

        # Create questions asynchronous since they are independent.
        # Children are created in same waitable after parent question, so no race problems
        await asyncio.gather(
            *(create_question_with_progress(question) for question in poll.questions)
        )

        # Answers are safe to build asynchronous since all questions are created
        await asyncio.gather(
            *(create_answer_with_progress(answer, question) for question in poll.questions for answer in question.answers)
        )
        for question in poll.questions:
            question.index_answers()

        # Logics should be uploaded exclusively synchronous since race condition may lead to
        # undefined behavior due to join conditions.
        await self._upload_logic(poll=poll, ids=ids, progress_callback=update, exc_handler=raise_upload_exception)

        # Create counters asynchronous.
        await asyncio.gather(
            *(create_counters_with_progress(counter) for counter in poll.counters)
        )

        # refetch all internal pointers
        poll._refresh()

        # stop progress bar
        if verbose:
            progress.stop()

        return poll


class BlockResource(BaseResource):
    """API area for survey blocks (groups of questions)."""

    async def get_blocks(
            self,
            poll_id: int,
            includes: List[blocks.BlockInclude] = blocks.ALL_BLOCK_INCLUDES
    ) -> List[blocks.Block]:
        """List all blocks of ``poll_id``, sorted by their display order."""
        payload = blocks.GetBlocksPayload(poll_id=poll_id, includes=includes)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.blocks_by_poll_get,
            json_=payload.model_dump()
        )
        response = await self._request(request=request)
        return sorted([blocks.Block(**b) for b in response.result], key=lambda x: x.order)

    async def create_block(
            self,
            block: blocks.Block
    ) -> blocks.Block:
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.create_block,
            json_=block.dump_create_payload()
        )
        response = await self._request(request=request)
        return blocks.Block(**response.result)


class QuestionResource(BaseResource):
    """API area for survey questions."""

    async def get_block_question(
            self,
            block_id: int,
            includes: List[questions.QuestionInclude] = questions.ALL_QUESTION_INCLUDES
    ) -> List[questions.Question]:
        """List all questions belonging to ``block_id``, sorted by order."""
        payload = questions.GetBlockQuestionPayload(block_id=block_id, includes=includes)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.questions_by_block_get,
            json_=payload.model_dump()
        )
        response = await self._request(request=request)
        return sorted([questions.Question(**q) for q in response.result], key=lambda x: x.order)

    async def get_poll_questions(
            self,
            poll_id: int,
            includes: List[questions.QuestionInclude] = questions.ALL_QUESTION_INCLUDES
    ) -> List[questions.Question]:
        """
        List every question in ``poll_id`` across all blocks, in the order
        returned by the backend (assumed already poll-ordered).
        """
        payload = questions.GetPollQuestionPayload(poll_id=poll_id, includes=includes)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.questions_by_poll_get,
            json_=payload.model_dump()
        )
        response = await self._request(request=request)

        result = []
        for i, q in enumerate(response.result, start=1):  # assume it is sorted by backend
            question = questions.Question(**q)
            question._poll_order = i
            result.append(question)
        return result

    async def create_question(self, question: questions.Question) -> questions.Question:
        """Create question in block or in poll"""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.create_question,
            json_=question.dump_create_payload()
        )
        response = await self._request(request=request)
        return questions.Question(**response.result)

    async def create_answer(self, answer: questions.Answer) -> questions.Answer:
        """Create answer for question"""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.create_answer,
            json_=answer.dump_create_payload()
        )
        response = await self._request(request=request)
        return questions.Answer(**response.result)


class CounterResource(BaseResource):
    """API area for poll counters (quota-style tallies)."""

    async def get_counters(self, poll_id: int) -> List[counters.Counter]:
        """List all counters configured for ``poll_id``."""
        payload = counters.GetCounterPayload(poll_id=poll_id)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.counters_get,
            json_=payload.model_dump()
        )
        response = await self._request(request=request)
        return [counters.Counter(**c) for c in response.result]

    async def create_counter(self, counter: counters.Counter) -> counters.Counter:
        """Create counter and it's logics"""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.counter_create,
            json_=counter.dump_create_payload()
        )
        response = await self._request(request=request)
        return counters.Counter(**response.result)



class LogicResource(BaseResource):
    """API area for poll branching/display logic."""

    async def get_jumps(self, poll_id: int) -> List[logic.Jump]:
        """List the jump (skip-logic) rules configured for ``poll_id``."""
        payload = logic.GetLogicPayload(poll_id=poll_id)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.jump_logic_get,
            json_=payload.model_dump()
        )
        response = await self._request(request=request)
        return [logic.Jump(**jump) for jump in response.result]

    async def get_question_display(self, poll_id: int) -> List[logic.Display]:
        """List the question display/visibility rules for ``poll_id``."""
        payload = logic.GetLogicPayload(poll_id=poll_id)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.display_logic_get,
            json_=payload.model_dump()
        )
        response = await self._request(request=request)
        return [logic.Display(**display) for display in response.result]

    async def get_answer_display(self, poll_id: int) -> List[logic.DisplayAnswers]:
        """List the answer display/visibility rules for ``poll_id``."""
        payload = logic.GetLogicPayload(poll_id=poll_id)

        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.display_answer_logic_get,
            json_=payload.model_dump()
        )
        response = await self._request(request=request)
        return [logic.DisplayAnswers(**display) for display in response.result]

    async def create_jump(self, jump: logic.Jump) -> logic.Jump:
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.jump_logic_create,
            json_=jump.dump_create_payload()
        )
        response = await self._request(request=request)
        return logic.Jump(**response.result[0])

    async def create_question_display(self, question_display: logic.Display) -> logic.Display:
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.display_logic_create,
            json_=question_display.dump_create_payload()
        )
        response = await self._request(request=request)
        return logic.Display(**response.result[0])

    async def create_answer_display(self, answer_display: logic.DisplayAnswers) -> logic.DisplayAnswers:
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.display_answer_logic_create,
            json_=answer_display.dump_create_payload()
        )
        response = await self._request(request=request)
        return logic.DisplayAnswers(**response.result[0])


class SourceResource(BaseResource):
    """API area for respondent traffic sources."""

    async def get_sources(self) -> sources.Sources:
        """List all configured traffic sources."""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.sources_get,
        )
        response = await self._request(request=request)
        return sources.Sources(
            sources = [sources.Source(**s) for s in response.result]
        )

    async def create_source(self, source: sources.Source) -> sources.Source:
        """Create traffic source"""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            json_=source.model_dump(include={'name', 'utm'}),
            endpoint=config.Endpoint.create_source,
        )
        response = await self._request(request=request)
        return sources.Source(**response.result)

    async def update_source(self, source: sources.Source) -> sources.Source:
        """Update traffic source"""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            json_=source.model_dump(exclude_none=True),
            endpoint=config.Endpoint.update_source,
        )
        response = await self._request(request=request)
        return sources.Source(**response.result)

    async def activate_source(self, source_id: int) -> None:
        """Activate traffic source"""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            json_={
                "id": source_id,
                "is_active": True
            },
            endpoint=config.Endpoint.activate_source,
        )
        response = await self._request(request=request)
        return None

    async def deactivate_source(self, source_id: int) -> None:
        """Deactivate traffic source"""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            json_={
                "id": source_id,
                "is_active": False
            },
            endpoint=config.Endpoint.activate_source,
        )
        response = await self._request(request=request)
        return None

    async def delete_source(self, source_id: int) -> None:
        """Delete traffic source"""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            json_={
                "id": source_id,
            },
            endpoint=config.Endpoint.delete_source,
        )
        response = await self._request(request=request)
        return None

class MetaResource(BaseResource):
    """API area for access levels."""

    async def get_mate(self) -> meta.Meta:
        """List all configured traffic sources."""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.get_meta,
        )
        response = await self._request(request=request)
        return meta.Meta(meta=response.result)

# ParserClient's resource-namespace fields reference these classes by name
# before they're defined further down this module. `from __future__ import
# annotations` (top of file) makes that legal at class-definition time, but
# pydantic still needs the names to exist before it can finish building the
# model - hence resolving them explicitly here, once everything is defined.
ParserClient.model_rebuild()
