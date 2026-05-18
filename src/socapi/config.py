from email.policy import default
from operator import gt

from pydantic import BaseModel, model_validator, computed_field, field_validator, ValidationError, Field
from typing import Optional, Literal, Union, List, LiteralString, Dict
from .models.endpoints import EndpointType


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
        return f"https://{self.name}"


    @computed_field
    @property
    def admin_url(self) -> str:
        return f"https://admin.{self.name}"


    @computed_field
    @property
    def api_url(self) -> str:
        return f"{self.admin_url}/api"


    @computed_field
    @property
    def base_urls(self) -> Dict[EndpointType, str]:
        return {
            EndpointType.BASE: self.base_url,
            EndpointType.API: self.api_url,
            EndpointType.ADMIN: self.admin_url,
        }




class ParserConfig(BaseModel):
    """
        Core config for sequential requests
        Shared config properties and internal Constructor class

    """
    constructor: Union[ConstructorName, Constructor]
    username: str
    password: str

    max_concurrency: int = Field(default=10, gt=0, le=10, description="general max concurency")
    download_concurrency: int = Field(default=3, gt=0, le=5, description="to avoid backend overload")
    timeout: int = Field(default=30, gt=0, le=600)
    request_cooldown: float = Field(default=0.01, gt=0, le=20, description="request between cooldowns to avoid backend overload")

    verify_ssl: bool = True

    @field_validator('constructor', mode='before')
    @classmethod
    def validate_constructor(cls, value) -> Constructor:
        if isinstance(value, Constructor):
            return value
        elif isinstance(value, str):
            try:
                return Constructor(name=value)
            except:
                raise
        raise ValidationError("constructor must be string or Constructor")