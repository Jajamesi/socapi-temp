from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from socapi.client import ParserClient

from socapi.models.endpoints import Endpoints, EndpointType, FuncEndpoints
from socapi.models.roles import Role
from socapi.resources.resource import Resource

class RolesResource(Resource):
    async def get_role_list(self):
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=f"{Endpoints.role}{FuncEndpoints.list}"
        )

        js = await response.json()

        response_result = js.get("result", {})

        return [Role(**i) for i in response_result]