from typing import Optional, List, Any
from datetime import datetime
from enum import StrEnum, IntEnum
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

class PageType(IntEnum):
    greeting = 1
    finish=2
    disqualification=3


class PageData(BaseModel):
    description: str
    title: str


class Page(BaseModel):
    id: int
    name: str
    data: PageData
    type_id: PageType
    poll_id: int