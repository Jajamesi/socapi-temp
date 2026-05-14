

class UsersResource:
    def __init__(self, client):
        self._client = client

    async def get_user(self, user_id: int):
        response = await self._client.request(
            "GET",
            f"/users/{user_id}",
        )

        return await response.json()