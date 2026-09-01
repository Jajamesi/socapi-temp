from email.policy import default
from operator import gt


from pydantic import BaseModel, model_validator, computed_field, field_validator, ValidationError, Field
from typing import Optional, Literal, Union, List, LiteralString, Dict
from urllib.parse import urljoin
from enum import StrEnum


class EndpointType(StrEnum):
    BASE = "base"
    API = "api"
    ADMIN = "admin"

class Endpoint(StrEnum):
    login = "/api/login"
    profile = "api/profile"
    user_get = "/api/user/get"
    page_get = "/api/page/getall"
    poll_header_get = "/api/poll/get"
    blocks_by_poll_get = "/api/block/getbypoll"
    questions_by_block_get = "/api/question/getbyblock"
    questions_by_poll_get = "/api/question/getbypoll"
    export_poll = "	/api/poll/stat/export"
    progress = "/api/poll/stat/export/progress"
    download_poll = "/api/poll/stat/export/progress/download"
    done_poll = "/api/poll/stat/export/progress/done"

    display_answer_logic_get = "/api/logic/display-answer/getbypoll"
    jump_logic_get = "/api/logic/jump/getbypoll"
    display_logic_get = "/api/logic/display/getbypoll"
    counters_get = "/api/counter/list"
    sources_get = "/api/source/list"




    user = 'user/'
    role = 'role/'
    poll = 'poll/'
    meta = 'meta/'
    question = 'question/'
    status = "status/"
    block = "block/"
    page = "page/"
    counter = "counter/"


ConstructorHost = Literal[
    "online-sociology.ru",
    "opinion-world.com",
]


class Constructor(BaseModel):
    """
        Class represent instance of poll constructor, based on domain name.
        Provides base URLs

    """
    name: ConstructorHost


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
    def base_urls(self) -> Dict[EndpointType, str]:
        return {
            EndpointType.BASE: self.base_url,
            EndpointType.ADMIN: self.admin_url,
        }