from pydantic import BaseModel

class LoginPayload(BaseModel):
    login: str
    password: str