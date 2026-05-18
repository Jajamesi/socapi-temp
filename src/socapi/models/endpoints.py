from enum import StrEnum


class EndpointType(StrEnum):
    BASE = "base"
    API = "api"
    ADMIN = "admin"

class Endpoints(StrEnum):
    login = '/login'
    profile = '/profile'
    user = '/user'

class FuncEndpoints(StrEnum):
    get = "/get"
    delete = "/api"
    ADMIN = "/admin"