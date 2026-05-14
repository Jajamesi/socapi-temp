from email.policy import default
from operator import gt

from pydantic import BaseModel, model_validator, computed_field, field_validator, ValidationError, Field
from typing import Optional, Literal, Union, List

ConstructorName = Literal[
    "online-sociology.ru",
    "opinion-world.com",
]


class Constructor(BaseModel):
    """
        Class represent instance of poll constructor, based on domain name.
        Provides base URLs

    """
    name: ConstructorName


    @computed_field
    @property
    def base_url(self) -> str:
        return f"https://{self.name}/"


    @computed_field
    @property
    def admin_url(self) -> str:
        return f"https://admin.{self.name}/"

    @computed_field
    @property
    def api_url(self) -> str:
        return f"{self.admin_url}api/"




class ParserConfig(BaseModel):
    """
        Core config for sequential requests

    """
    constructor: ConstructorName
    _constructor: Constructor
    username: str
    password: str

    max_concurrency: int = Field(default=10, gt=0, le=10, description="general max concurency")
    download_concurrency: int = Field(default=3, gt=0, le=5, description="to avoid backend overload")
    timeout: int = Field(default=30, gt=0, le=600)
    request_cooldown: float = Field(default=0.01, gt=0, le=20, description="request between cooldowns to avoid backend overload")

    verify_ssl: bool = True


    @computed_field
    @property
    def _constructor(self) -> Constructor:
        try:
            return Constructor(name=self.constructor)
        except:
            raise

