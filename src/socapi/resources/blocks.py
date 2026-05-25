from typing import TYPE_CHECKING, List, Optional, Dict, Literal

if TYPE_CHECKING:
    from socapi.client import ParserClient

from operator import attrgetter
from datetime import datetime
from urllib.parse import urljoin
from enum import StrEnum, IntEnum

from socapi.models.endpoints import Endpoint, EndpointType, Actions
from socapi.models.blocks import Block
from socapi.resources.resource import Resource
from socapi.utils import get_json_result


class BlockIncludePayload(StrEnum):
    ID = "id"
    NAME = "name"
    TITLE = "title"
    DESCRIPTION = "description"
    POLL_ID = "poll_id"
    ORDER = "order"
    QUESTIONS = "questions"


DEFAULT_BLOCK_INCLUDE_PAYLOAD = [
    item.value
    for item in BlockIncludePayload
]


class BlockResource(Resource):

    async def get_blocks(self, poll_id: int) -> List[Block]:
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=urljoin(Endpoint.block, Actions.get_by_poll),
            json={
                "poll_id": poll_id,
                "includes": DEFAULT_BLOCK_INCLUDE_PAYLOAD
            }
        )

        response_result = await get_json_result(response)

        return [Block(**i) for i in response_result]