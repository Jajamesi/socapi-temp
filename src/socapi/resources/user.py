from __future__ import annotations

from typing import Optional, List, Any
from datetime import datetime

from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator

class User(BaseModel):
    """An operator/user account, as returned by ``/api/profile``."""
    id: int
    telegram_id: int
    login: str
    password: Optional[str] = Field(default=None, exclude=True)
    surname: str
    name: str
    patronymic: Optional[str] = None
    phone: int
    email: str
    role_id: int
    disabled: bool
    meta: Optional[List[int]] = None
    creator_id: int
    updated_at: Optional[datetime] = None
    created_at: datetime
    deleted_at: Optional[datetime] = None


class CreatedAtFilter(BaseModel):
    """``created_at`` date-range filter for :class:`UserGetPayload`."""
    model_config = ConfigDict(extra="forbid")

    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None


class UserGetPayload(BaseModel):
    """Request body for listing/searching users."""
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    limit: int = Field(default=10, ge=1)
    offset: int = Field(default=0, ge=0)

    created_at: CreatedAtFilter | None = None
    disabled: bool | None = None
    name: str | None = None
    patronymic: str | None = None
    role_id: int | None = Field(default=None, ge=1)
    login: str | None = None
    phone: int | None = None
    email: EmailStr | None = None
    meta: list[int] | None = None

    @field_validator("meta", mode="before")
    @classmethod
    def normalize_to_list(cls, value: Any) -> Any:
        """Allow passing a single meta id (``5``) instead of requiring ``[5]``."""
        if isinstance(value, int):
            return [value]
        return value