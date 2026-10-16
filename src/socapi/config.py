from pydantic import BaseModel, model_validator, computed_field, field_validator, ValidationError, Field
from typing import Optional, Literal, Union, List, LiteralString, Dict
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
    create_page = "/api/page/add"

    poll_header_get = "/api/poll/get"

    blocks_by_poll_get = "/api/block/getbypoll"
    create_block = "/api/block/create"

    questions_by_block_get = "/api/question/getbyblock"
    questions_by_poll_get = "/api/question/getbypoll"
    create_question = "/api/question/create"
    create_answer = "/api/question/answer/create"

    export_poll = "	/api/poll/stat/export"
    progress = "/api/poll/stat/export/progress"
    download_poll = "/api/poll/stat/export/progress/download"
    done_poll = "/api/poll/stat/export/progress/done"

    display_answer_logic_get = "/api/logic/display-answer/getbypoll"
    jump_logic_get = "/api/logic/jump/getbypoll"
    display_logic_get = "/api/logic/display/getbypoll"

    display_answer_logic_create = "/api/logic/display-answer/addpack"
    jump_logic_create = "/api/logic/jump/addpack"
    display_logic_create = "/api/logic/display/addpack"


    counters_get = "/api/counter/list"
    counter_create = "/api/counter/create"

    sources_get = "/api/source/list"
    create_source = "/api/source/create"
    activate_source = "/api/source/activate"
    update_source = "/api/source/update"
    delete_source = "/api/source/delete"

    duplicate_poll = "api/poll/duplicate"

    get_meta = "/api/meta/full"
    update_meta = "/api/poll/update/meta"

    update_poll = "/api/poll/update"
    create_poll = "/api/poll/create"

    create_personal_links = "/api/poll/source/links"

    repeat_passages ="/api/poll/stat/repeats/export"


ConstructorHost = Literal[
    "online-sociology.ru",
    "opinion-world.com",
    "sociology-form.com"
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