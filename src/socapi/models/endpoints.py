from enum import StrEnum


class EndpointType(StrEnum):
    BASE = "base"
    API = "api"
    ADMIN = "admin"

class Endpoints(StrEnum):
    login = '/login'
    profile = '/profile'
    user = '/user'
    role = '/role'
    poll = '/poll'
    meta = '/meta'

class FuncEndpoints(StrEnum):
    get = "/get"
    delete = "/api"
    list = "/list"
    status = "/status"
    full = "/full"