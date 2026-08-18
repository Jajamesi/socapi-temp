from typing import TYPE_CHECKING
if TYPE_CHECKING:
    pass
from urllib.parse import urljoin

from old.models.endpoints import Endpoint, EndpointType, Actions
from old.models.roles import Role
from old.resources.resource import Resource

class RolesResource(Resource):
    async def get_role_list(self):
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=urljoin(Endpoint.role, Actions.list)
        )

        js = await response.json()

        response_result = js.get("result", {})

        return [Role(**i) for i in response_result]