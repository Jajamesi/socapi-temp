from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator, Field


class Event(BaseModel):
    name: str
    method: str
    url: str
    timestamp: datetime = Field(default_factory=datetime.now)


class Tracer:
    def __init__(self, enable: bool = True):
        self.traces = []
        self.enable = enable

    def add(self, **kwargs):
        if self.enable:
            self.traces.append(Event(**kwargs))