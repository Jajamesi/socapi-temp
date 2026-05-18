import pytest
from pydantic import ValidationError

import os
from dotenv import load_dotenv
load_dotenv()

import socapi.config as sc
import socapi.session as ses


@pytest.mark.asyncio
async def test_session_init_success():
    config = sc.ParserConfig(
        constructor=os.environ["CONSTRUCTOR_NAME"],
        username=os.environ["USERNAME"],
        password=os.environ["PASSWORD"]
    )

    session = ses.create_session(config)
    assert session is not None