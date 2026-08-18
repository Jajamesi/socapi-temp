from typing import TYPE_CHECKING
if TYPE_CHECKING:
    pass
from urllib.parse import urljoin

from old.models.endpoints import Endpoint, EndpointType, Actions
from old.models.meta import Meta
from old.resources.resource import Resource

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