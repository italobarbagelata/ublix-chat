from typing import List
from pydantic import BaseModel, Field

from pydantic import BaseModel


class Integration(BaseModel):
    """ Class to represent an integration """
    id: str
    name: str

    @classmethod
    def from_dict(cls, data: dict) -> "Integration":
        """ Method to create an instance from a dictionary """
        return cls(
            id=data.get('id', ''),
            name=data.get('name', '')
        )


class Integrations(BaseModel):
    """ Class to represent the integrations of a project """
    apis: List[Integration] = Field(default_factory=list)
    sql: List[Integration] = Field(default_factory=list)
    mongodb: List[Integration] = Field(default_factory=list)
    genesys: List[Integration] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, integrations: dict):
        """ Method to create an instance from a dictionary """
        return cls(
            apis=[Integration.from_dict(i) for i in integrations.get('apis', [])],
            sql=[Integration.from_dict(i) for i in integrations.get('sql', [])],
            mongodb=[Integration.from_dict(i) for i in integrations.get('mongodb', [])],
            genesys=[Integration.from_dict(i) for i in integrations.get('genesys', [])]
        )
