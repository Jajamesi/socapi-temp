from dataclasses import dataclass
from pydantic import BaseModel

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Response


@dataclass
class APIError(Exception):
    status: int
    error: str

    def __str__(self) -> str:
        return f"{self.code}: {self.error}"


class InvalidCredentialsError(APIError):
    pass

class InvalidTokenError(APIError):
    pass

class MissingTokenError(APIError):
    pass

class UnknownError(APIError):
    pass


API_ERRORS = {
    "get user: login or password is invalid": InvalidCredentialsError,
    "authorization header is invalid": InvalidTokenError,
    "authorization header is empty": InvalidTokenError,

    "unknown error": UnknownError
}

def get_error(response: "Response") -> APIError:
    """
    get specific error based on constructor error description
    """
    if response.error:
        return API_ERRORS.get(response.error, UnknownError)(**response.model_dump(include={"status", "error"}))
    return UnknownError(status=response.status, error="no error provided")