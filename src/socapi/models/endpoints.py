from enum import StrEnum


class EndpointType(StrEnum):
    BASE = "base"
    API = "api"
    ADMIN = "admin"

class Endpoints(StrEnum):
    login = '/login'
    profile = '/profile'