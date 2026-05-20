from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from socapi.client import ParserClient
from urllib.parse import urljoin

from socapi.models.endpoints import Endpoint, EndpointType, Actions
from socapi.models.users import User, UserGetPayload
from socapi.resources.resource import Resource


class UsersResource(Resource):
    async def get_current_user(self):
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=Actions.profile
        )

        js = await response.json()

        user_data = js.get("result", {})

        return User(**user_data)


    async def get_users(self, limit: int = 11, offset: int = 0):
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=urljoin(Endpoint.user, Actions.get),
            json=UserGetPayload(limit=limit, offset=offset).model_dump()
        )

        js = await response.json()

        users_data = js.get("result", {})

        return [User(**user_data) for user_data in users_data]
