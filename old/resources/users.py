from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    pass
from urllib.parse import urljoin

from old.models.endpoints import Endpoint, EndpointType, Actions
from old.models.users import User, UserGetPayload
from old.resources.resource import Resource


class UsersResource(Resource):
    """
    Represents profile and user/get resources.
    Profile provide data on active user.
    User/get allows to send different fields in body to get list of users.
    """

    async def get_current_user(self) -> User:
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=Actions.profile
        )

        js = await response.json()

        user_data = js.get("result", {})

        return User(**user_data)


    async def get_users(self, limit: int = 11, offset: int = 0) -> List[User]:
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=urljoin(Endpoint.user, Actions.get),
            json=UserGetPayload(limit=limit, offset=offset).model_dump()
        )

        js = await response.json()

        users_data = js.get("result", {})

        return [User(**user_data) for user_data in users_data]


    async def get_user(self, **kwargs) -> Optional[User]:
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=urljoin(Endpoint.user, Actions.get),
            json={**kwargs}
        )

        js = await response.json()

        users_data = js.get("result", {})

        if users_data:
            return User(**users_data[0])
        return None
