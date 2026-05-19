from typing import TYPE_CHECKING, List, Optional, Dict

if TYPE_CHECKING:
    from socapi.client import ParserClient

from datetime import datetime

from socapi.models.endpoints import Endpoints, EndpointType, FuncEndpoints
from socapi.models.polls import Poll, PollStatus
from socapi.resources.resource import Resource

class PollResource(Resource):

    async def get_poll_statuses(self) -> Dict[int, PollStatus]:
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=f"{Endpoints.poll}{FuncEndpoints.status}{FuncEndpoints.get}"
        )

        js = await response.json()

        response_result = js.get("result", {})

        return {i["id"]: PollStatus(**i) for i in response_result}


    async def get_polls(
            self,
            limit: int = 11,
            offset: int = 0,
            is_in_track: bool = False,
            meta: List[int] = None,
            sociologist_id: int = None,
            status_id: int = None,
            targetologist_id: int = None,
            from_date: Optional[datetime] = None,
            to_date: Optional[datetime] = None,
    ) -> List[Poll]:
        pass


    async def get_poll(self, poll_id: int) -> Poll:
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=f"{Endpoints.poll}{FuncEndpoints.full}",
            json={"id": poll_id}
        )

        js = await response.json()

        response_result = js.get("result", {})

        return Poll(**response_result)