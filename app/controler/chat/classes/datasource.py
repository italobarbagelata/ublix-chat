from typing import Literal
from pydantic import BaseModel, Field


class Datasource(BaseModel):
    id: str = Field(default_factory=str)
    status: str = Field(default_factory=str)
    type: Literal["faq", "general_info"] = Field(default_factory=str)
    filename: str = Field(default_factory=str)

    @classmethod
    def from_dict(cls, data: dict) -> "Datasource":
        """ Method to create an instance from a dictionary """
        return cls(
            id=data.get('datasource_id', ''),
            status=data.get('status', ''),
            type=data.get('type', ''),
            filename=data.get('filename', '')
        )
