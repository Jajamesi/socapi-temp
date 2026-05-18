from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field

class User(BaseModel):
    id: int
    telegram_id: int
    login: str
    password: Optional[str]
    surname: str
    name: str
    patronymic: str
    phone: int
    email: str
    role_id: int
    disabled: bool
    meta: List[int]
    creator_id: int
    updated_at: datetime
    created_at: datetime
    deleted_at: Optional[datetime]
