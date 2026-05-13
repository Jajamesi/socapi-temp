from pydantic import BaseModel


class ParserConfig(BaseModel):
    base_url: str
    username: str
    password: str

    max_concurrency: int = 10
    timeout: int = 30

    verify_ssl: bool = True