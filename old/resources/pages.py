from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    pass

from urllib.parse import urljoin

from old.models.endpoints import Endpoint, EndpointType, Actions
from old.models.pages import Page
from old.resources.resource import Resource
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