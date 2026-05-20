from enum import StrEnum


class EndpointType(StrEnum):
    BASE = "base"
    API = "api"
    ADMIN = "admin"

class Endpoint(StrEnum):
    user = 'user/'
    role = 'role/'
    poll = 'poll/'
    meta = 'meta/'
    question = 'question/'
    status = "status/"

class Actions(StrEnum):
    profile = 'profile'
    login = 'login'
    get = "get"
    delete = "api"
    list = "list"
    full = "full"
    get_by_poll = "getbypoll"
    get_by_block = "getbyblock"