from typing import TYPE_CHECKING, List, Optional, Dict, Literal

if TYPE_CHECKING:
    from socapi.client import ParserClient

from operator import attrgetter
from datetime import datetime
from urllib.parse import urljoin
from enum import StrEnum, IntEnum

from socapi.models.endpoints import Endpoint, EndpointType, Actions
from socapi.models.pages import Page
from socapi.resources.resource import Resource
from socapi.utils import get_json_result


class PageResource(Resource):

    async def get_pages(self, poll_id: int) -> List[Page]:
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=urljoin(Endpoint.page, Actions.get_all),
            json={
                "poll_id": poll_id,
            }
        )

        response_result = await get_json_result(response)

        return [Page(**i) for i in response_result]