import orjson
from aiohttp import ClientResponse

async def read_json(response: ClientResponse):
    return orjson.loads(await response.read())

async def get_json_result(response: ClientResponse):
    js = await read_json(response)
    return js.get("result", None)