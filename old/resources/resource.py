from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from socapi.client import ParserClient


class Resource:
    def __init__(self, client: "ParserClient"):
        self._client = client