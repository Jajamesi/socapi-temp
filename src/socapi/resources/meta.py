import re
from datetime import datetime
from typing import Collection, Literal, Optional, overload

from pydantic import BaseModel, Field, PrivateAttr


LookupMode = Literal["exact", "regex"]


class MetaParent(BaseModel):
    """
    returned by /api/meta/full
    """
    id: Optional[int] = None
    title: str
    order: int
    disabled: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    meta_values: list["MetaObject"] = Field(default_factory=list)


class MetaObject(MetaParent):
    """
    returned by /api/meta/full
    """
    meta_object_id: int
    meta_values: None = None


class Meta(BaseModel):
    meta: list[MetaParent]

    _title_to_parent: dict[str, MetaParent] = PrivateAttr(default_factory=dict)
    _title_to_object: dict[str, MetaObject] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context) -> None:
        self._title_to_parent = {
            parent.title: parent
            for parent in self.meta
            if not isinstance(parent, MetaObject)
        }

        self._title_to_object = {
            obj.title: obj
            for parent in self.meta
            for obj in parent.meta_values
        }

    def _get_by(
        self,
        item: int | str | Collection[int | str],
        mapping: dict[str, MetaParent | MetaObject],
        *,
        mode: LookupMode = "exact",
    ) -> MetaParent | MetaObject | list[MetaParent | MetaObject] | None:

        if isinstance(item, Collection) and not isinstance(item, (str, bytes)):
            items = [str(value) for value in item]

            if mode == "exact":
                return [
                    mapping[value]
                    for value in items
                    if value in mapping
                ]

            patterns = [re.compile(value) for value in items]

            return [
                meta
                for title, meta in mapping.items()
                if any(pattern.search(title) for pattern in patterns)
            ]

        value = str(item)

        if mode == "exact":
            return mapping.get(value)

        pattern = re.compile(value)

        return [
            meta
            for title, meta in mapping.items()
            if pattern.search(title)
        ]

    def __getitem__(
        self,
        item: str,
    ) -> MetaParent | MetaObject | None:
        return (
            self._title_to_parent.get(item)
            or self._title_to_object.get(item)
        )

    @overload
    def get_by_parent(
        self,
        item: int | str,
        *,
        mode: LookupMode = "exact",
    ) -> MetaParent | list[MetaParent] | None:
        ...

    @overload
    def get_by_parent(
        self,
        item: Collection[int | str],
        *,
        mode: LookupMode = "exact",
    ) -> list[MetaParent]:
        ...

    def get_by_parent(
        self,
        item: int | str | Collection[int | str],
        *,
        mode: LookupMode = "exact",
    ) -> MetaParent | list[MetaParent] | None:
        result = self._get_by(
            item,
            self._title_to_parent,
            mode=mode,
        )
        return result

    @overload
    def get_by_object(
        self,
        item: int | str,
        *,
        mode: LookupMode = "exact",
    ) -> MetaObject | list[MetaObject] | None:
        ...

    @overload
    def get_by_object(
        self,
        item: Collection[int | str],
        *,
        mode: LookupMode = "exact",
    ) -> list[MetaObject]:
        ...

    def get_by_object(
        self,
        item: int | str | Collection[int | str],
        *,
        mode: LookupMode = "exact",
    ) -> MetaObject | list[MetaObject] | None:
        result = self._get_by(
            item,
            self._title_to_object,
            mode=mode,
        )
        return result