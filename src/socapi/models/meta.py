from pydantic import BaseModel, RootModel
from datetime import datetime
from typing import Optional, List


class MetaBase(BaseModel):
    id: int
    title: str
    disabled: bool
    order: int
    created_at: datetime
    updated_at: Optional[datetime] = None

class ChildMeta(MetaBase):
    meta_object_id: int

class Meta(MetaBase):
    discription: str
    meta_values: Optional[List[ChildMeta]]= None