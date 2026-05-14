import pytest
from pydantic import ValidationError

import os
from dotenv import load_dotenv
load_dotenv()

import socapi.config as sc


@pytest.mark.asyncio
async def test_parser_config_success():
    config = sc.ParserConfig(
        constructor=os.environ["CONSTRUCTOR_NAME"],
        username=os.environ["USERNAME"],
        password=os.environ["PASSWORD"]
    )

    assert config.username == os.environ["USERNAME"]
    assert config.password == os.environ["PASSWORD"]
    assert config._constructor == sc.Constructor(name=os.environ["CONSTRUCTOR_NAME"])


@pytest.mark.asyncio
async def test_parser_config_wrong_constructor():
    with pytest.raises(ValidationError) as exc_info:
        config = sc.ParserConfig(
            constructor='wrong constructor',
            username=os.environ["USERNAME"],
            password=os.environ["PASSWORD"]
        )

    errors = exc_info.value.errors()

    assert errors[0]["loc"] == ("constructor",)
    assert "Input should be" in errors[0]["msg"]