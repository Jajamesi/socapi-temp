from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from socapi.client import ParserClient

from socapi.models.endpoints import Endpoints, EndpointType, FuncEndpoints
from socapi.models.users import User, UserGetPayload

class UsersResource:
    def __init__(self, client: "ParserClient"):
        self._client = client


    async def get_current_user(self):
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=Endpoints.profile
        )

        js = await response.json()

        user_data = js.get("result", {})

        return User(**user_data)


    async def get_users(self, limit: int = 11, offset: int = 0):
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=f"{Endpoints.user}{FuncEndpoints.get}",
            json=UserGetPayload(limit=limit, offset=offset).model_dump()
        )

        js = await response.json()

        users_data = js.get("result", {})

        return [User(**user_data) for user_data in users_data]
