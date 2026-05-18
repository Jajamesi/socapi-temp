from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field

class User(BaseModel):
    id: int
    telegram_id: int
    login: str
    password: Optional[str] = None
    surname: str
    name: str
    patronymic: Optional[str] = None
    phone: int
    email: str
    role_id: int
    disabled: bool
    meta: List[int]
    creator_id: int
    updated_at: Optional[datetime] = None
    created_at: datetime
    deleted_at: Optional[datetime] = None

class UserGetPayload(BaseModel):
    limit: int = Field(default=11, ge=0, le=1000)
    offset: int = Field(default=0, ge=0, le=1000)