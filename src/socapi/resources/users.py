from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from socapi.client import ParserClient

from socapi.models.endpoints import Endpoints, EndpointType
from socapi.models.users import User

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



    # async def get_user(self, user_id: int):
    #     response = await self._client.request(
    #         "GET",
    #         f"/users/{user_id}",
    #     )
    #
    #     return await response.json()