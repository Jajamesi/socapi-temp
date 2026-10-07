from typing import Dict, Any

def increment():
    i = 0
    while True:
        i += 1
        yield i


def is_draft_id(value: int | None) -> bool:
    """Temporary ids of not-yet-uploaded items are negative; real server ids are >= 1."""
    return value is not None and value < 0


class IdMap:
    """
    Temporary (draft) id -> real (server) id translation, filled while a
    draft poll is being uploaded.

    ``ids[x]`` returns the real id for a draft id, passes real ids through
    unchanged (a jump may target an already existing page), and raises
    ``KeyError`` for a draft id that was never created - i.e. a dangling
    reference.
    """

    def __init__(self) -> None:
        self._map: Dict[int, int] = {}

    def register(self, draft_id: int, real_id: int) -> None:
        self._map[draft_id] = real_id

    def __getitem__(self, value: int) -> int:
        if not is_draft_id(value):
            return value
        try:
            return self._map[value]
        except KeyError:
            raise KeyError(f"draft id {value} was not created on the server (dangling reference)") from None

    def __len__(self) -> int:
        return len(self._map)


def _coerce_enum(enum_cls: type, value: Any, what: str) -> Any:
    """
    Accept an enum member, its name (any case, e.g. ``"is_selected"``) or its raw value.

    :raises ValueError: listing the allowed names.
    """
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        key = value.strip().casefold()
        for member in enum_cls:
            if member.name.casefold() == key:
                return member
    else:
        try:
            return enum_cls(value)
        except ValueError:
            pass
    allowed = ", ".join(repr(m.name.lower()) for m in enum_cls)
    raise ValueError(f"Unknown {what} {value!r}; allowed: {allowed}")