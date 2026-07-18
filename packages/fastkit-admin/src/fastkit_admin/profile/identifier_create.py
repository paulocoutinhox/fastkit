from pydantic import BaseModel


class IdentifierCreate(BaseModel):
    type: str
    value: str
