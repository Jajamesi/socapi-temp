from __future__ import annotations

import asyncio
import aiohttp
from dataclasses import dataclass
from pydantic import BaseModel, PrivateAttr, computed_field, model_validator, Field, HttpUrl, ConfigDict, validate_call
import functools
from typing import List, Optional, Literal, Union, Any, Mapping, Dict, Callable, ParamSpec, TypeVar, Awaitable
from datetime import datetime, timedelta
from urllib.parse import urljoin
import random
import contextlib
from uuid import UUID

from . import config, exceptions

from .resources import user, pages, polls, blocks, questions, logic, counters, sources

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

        return wrapper

    return decorator


def re_auth(
    func: Callable[P, Awaitable[T]],
) -> Callable[P, Awaitable[T]]:
    """
    Wrap a ``BaseResource`` method so it transparently (re)authenticates.

    On first call this makes sure the owning :class:`ParserClient` has run
    its initial authorization. If the wrapped call fails because the token
    is missing or invalid, the client re-authorizes once and the call is
    retried exactly one more time.
    """

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
    json_: Dict[str, Any] | None = None
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

    # resource namespaces
    user: UserResource | None = None
    page: PageResource | None = None
    poll: PollResource | None = None
    block: BlockResource | None = None
    question: QuestionResource | None = None
    logic: LogicResource | None = None
    counter: CounterResource | None = None
    source: SourceResource | None = None

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
                    parsed = Response(**await resp.json())

                    if resp.status >= 400:
                        raise exceptions.get_error(parsed)

                    return  parsed

                elif content_type.startswith("text/csv"):
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

        response: Response = await self._request(request=request)

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
        :return: mapping of poll id to the downloaded CSV bytes.
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
                await self._export_poll(poll_id, export_format=export_format)

                event = asyncio.Event()
                ready_events[poll_id] = event
                in_flight.add(poll_id)

                await event.wait()

                uuid = ready_uuids.pop(poll_id)

                results[poll_id] = await self._download_poll(uuid)
                await self._done_poll(uuid)

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

        await asyncio.gather(*worker_tasks)
        poller_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poller_task

        return results


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


class SourceResource(BaseResource):
    """API area for respondent traffic sources."""

    async def get_sources(self) -> List[sources.Source]:
        """List all configured traffic sources."""
        request = Request(
            method="POST",
            host=self._client._constructor.admin_url,
            endpoint=config.Endpoint.sources_get,
        )
        response = await self._request(request=request)
        return [sources.Source(**s) for s in response.result]


# ParserClient's resource-namespace fields reference these classes by name
# before they're defined further down this module. `from __future__ import
# annotations` (top of file) makes that legal at class-definition time, but
# pydantic still needs the names to exist before it can finish building the
# model - hence resolving them explicitly here, once everything is defined.
ParserClient.model_rebuild()
