from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Type

if TYPE_CHECKING:
    from .client import Response


@dataclass
class APIError(Exception):
    """Base exception for errors reported by the constructor API."""
    status: int
    error: str

    def __str__(self) -> str:
        return f"{self.status}: {self.error}"


class InvalidCredentialsError(APIError):
    """Raised when a login/password pair is rejected during authorization."""
    pass


class InvalidTokenError(APIError):
    """Raised when the ``authorization`` header was sent but rejected as malformed/expired."""
    pass


class MissingTokenError(APIError):
    """Raised when a request required an ``authorization`` header and none was sent."""
    pass


class UnknownError(APIError):
    """Fallback for any API error message not present in :data:`API_ERRORS`."""
    pass


# Maps the constructor API's error message strings to the specific
# APIError subclass that best describes them.
API_ERRORS: Dict[str, Type[APIError]] = {
    "get user: login or password is invalid": InvalidCredentialsError,
    "authorization header is invalid": InvalidTokenError,
    "authorization header is empty": MissingTokenError,

    "unknown error": UnknownError,
}


def get_error(response: Response) -> APIError:
    """
    Build the specific :class:`APIError` subclass matching ``response``'s
    error message, falling back to :class:`UnknownError` when the message
    isn't recognized (or the response carries no error message at all).
    """
    if response.error:
        error_cls = API_ERRORS.get(response.error, UnknownError)
        return error_cls(**response.model_dump(include={"status", "error"}))
    return UnknownError(status=response.status, error="no error provided")