from enum import IntEnum
from datetime import datetime
from typing import List, Dict, Collection, Literal
import re

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr

LookupMode = Literal["exact", "regex"]

class Source(BaseModel):
    """
    returned by /api/source/list
    """
    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., ge=1)
    name: str
    utm: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    name_sort_weight: int
    visible: bool
    is_active: bool
    activate: bool


class Sources(BaseModel):
    sources: list[Source]

    _name_to_source: dict[str, Source] = PrivateAttr(default_factory=dict)
    _utm_to_source: dict[str, Source] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context) -> None:
        self._name_to_source = {s.name: s for s in self.sources}
        self._utm_to_source = {s.utm: s for s in self.sources}

    def __getitem__(self, item: str) -> Source | None:
        return self._name_to_source.get(item) or self._utm_to_source.get(item)

    def _get_by(
        self,
        item: int | str | Collection[int | str],
        mapping: dict[str, Source],
        attribute: str,
        *,
        mode: LookupMode = "exact",
    ) -> Source | list[Source] | None:
        # Collection lookup
        if isinstance(item, Collection) and not isinstance(item, (str, bytes)):
            items = [str(value) for value in item]

            if mode == "exact":
                result = [
                    mapping[value]
                    for value in items
                    if value in mapping
                ]
            else:
                patterns = [re.compile(value) for value in items]

                result = [
                    source
                    for source in self.sources
                    if any(
                        pattern.search(getattr(source, attribute))
                        for pattern in patterns
                    )
                ]

            return result

        # Single lookup
        value = str(item)

        if mode == "exact":
            return mapping.get(value)

        pattern = re.compile(value)

        return [
            source
            for source in self.sources
            if pattern.search(getattr(source, attribute))
        ]

    def get_by_name(
        self,
        item: int | str | Collection[int | str],
        *,
        mode: LookupMode = "exact",
    ) -> Source | list[Source] | None:
        return self._get_by(
            item,
            self._name_to_source,
            "name",
            mode=mode,
        )

    def get_by_utm(
        self,
        item: int | str | Collection[int | str],
        *,
        mode: LookupMode = "exact",
    ) -> Source | list[Source] | None:
        return self._get_by(
            item,
            self._utm_to_source,
            "utm",
            mode=mode,
        )