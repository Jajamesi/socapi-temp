from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from socapi.client import ParserClient
from urllib.parse import urljoin

from socapi.models.endpoints import Endpoint, EndpointType, Actions
from socapi.models.meta import Meta, ChildMeta
from socapi.resources.resource import Resource

class MetaResource(Resource):

    async def get_meta(self):
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=urljoin(Endpoint.meta, Actions.full)
        )

        js = await response.json()

        response_result = js.get("result", {})

        return [Meta(**i) for i in response_result]