from typing import TYPE_CHECKING, List, Optional, Dict

if TYPE_CHECKING:
    from socapi.client import ParserClient

from datetime import datetime
from urllib.parse import urljoin
from enum import StrEnum, IntEnum

from socapi.models.endpoints import Endpoint, EndpointType, Actions
from socapi.models.questions import Question
from socapi.resources.resource import Resource
from socapi.utils import get_json_result


class QuestionIncludePayload(StrEnum):
    TYPE_ID = "type_id"
    ANSWERS = "answers"
    ID = "id"
    TITLE = "title"
    BLOCK_ID = "block_id"
    ORDER = "order"
    OPTIONAL = "optional"
    MAX_ANSWER = "max_answer"
    MIN_ANSWER = "min_answer"
    HAS_INPUT = "has_input"
    CHILDREN = "children"
    CHILDREN_TYPE_ID = "children.type_id"
    CHILDREN_ANSWERS = "children.answers"


DEFAULT_QUESTION_INCLUDE_PAYLOAD = [
    item.value
    for item in QuestionIncludePayload
]


class QuestionResource(Resource):

    async def get_questions(self):
        pass

    async def _get_questions_by_poll(self, poll_id: int) -> List[Question]:
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=urljoin(Endpoint.question, Actions.get_by_poll),
            json={
                "poll_id": poll_id,
                "includes": DEFAULT_QUESTION_INCLUDE_PAYLOAD
            }
        )

        response_result = await get_json_result(response)

        return [Question(**i) for i in response_result]

    async def _get_questions_by_block(self, block_id: int) -> List[Question]:
        response = await self._client.request(
            method="POST",
            endpoint_type=EndpointType.API,
            url=urljoin(Endpoint.question, Actions.get_by_block),
            json={
                "block_id": block_id,
                "includes": DEFAULT_QUESTION_INCLUDE_PAYLOAD
            }
        )

        response_result = await get_json_result(response)

        return [Question(**i) for i in response_result]

    async def update_question(self, question: Question) -> Question:
        pass

    async def create_question(self, question: Question) -> Question:
        pass

    async def delete_question(self, question_id: int) -> Question:
        pass

    # async def get_polls(
    #         self,
    #         limit: int = 11,
    #         offset: int = 0,
    #         is_in_track: bool = False,
    #         meta: List[int] = None,
    #         sociologist_id: int = None,
    #         status_id: int = None,
    #         targetologist_id: int = None,
    #         from_date: Optional[datetime] = None,
    #         to_date: Optional[datetime] = None,
    # ) -> List[Poll]:
    #     pass