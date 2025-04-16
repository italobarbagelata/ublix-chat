from pydantic import BaseModel, Field

from app.controler.chat.core.prompt_templates import DEFAULT_PROMPT


class Personality(BaseModel):
    """ Class to represent a personality """
    id: str = Field(default_factory=str)
    type: str = Field(default_factory=str)
    audience: str = Field(default_factory=str)
    purpose: str = Field(default_factory=str)
    work: str = Field(default_factory=str)
    mission: str = Field(default_factory=str)
    details: str = Field(default_factory=str)
    prompt: str = Field(default_factory=str)
    instructions: str = Field(default_factory=str)

    @classmethod
    def from_dict(cls, data: dict) -> "Personality":
        """ Method to create an instance from a dictionary """
        return cls(
            id=data.get('personality_id', ''),
            type=data.get('type', ''),
            audience=data.get('audience', ''),
            purpose=data.get('purpose', ''),
            work=data.get('work', ''),
            mission=data.get('mission', ''),
            details=data.get('details', ''),
            prompt=data.get('personality', DEFAULT_PROMPT),
            instructions=data.get('instructions', '')
        )
