from typing import TYPE_CHECKING, List, Optional, Dict, Literal

if TYPE_CHECKING:
    from socapi.client import ParserClient

from operator import attrgetter
from datetime import datetime
from urllib.parse import urljoin
from enum import StrEnum, IntEnum

from socapi.models.endpoints import Endpoint, EndpointType, Actions
from socapi.models.counters import Counter
from socapi.resources.resource import Resource
from socapi.utils import get_json_result


class PageResource(Resource):

    async def get_pages(self, poll_id: int) -> List[Counter]:
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=urljoin(Endpoint.counter, Actions.list),
            json={
                "poll_id": poll_id,
            }
        )

        response_result = await get_json_result(response)

        return [Counter(**i) for i in response_result]