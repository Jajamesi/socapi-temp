from pydantic import BaseModel, RootModel
from datetime import datetime
from typing import Optional


class Role(BaseModel):
    id: int
    name: str
    title: str
    description: str
    created_at: datetime
    updated_at: Optional[datetime] = None