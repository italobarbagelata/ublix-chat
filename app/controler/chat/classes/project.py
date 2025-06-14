from typing import List, Dict

from pydantic import BaseModel, Field

from app.controler.chat.classes.datasource import Datasource
from app.controler.chat.classes.integrations import Integrations
from app.resources.constants import MODEL_CHATBOT

class Project(BaseModel):
    id: str = Field(default="")
    name: str = Field(default="")
    description: str = Field(default="")
    vstore_index: str = Field(default="")
    personality: str = Field(default="")
    datasources: List[Datasource] = Field(default_factory=list)
    integrations: Integrations
    prompt: str = Field(default="")
    instructions: str = Field(default="")
    prompt_memory: str = Field(default="")
    model: str = Field(default=MODEL_CHATBOT)
    enabled_tools: List[str] = Field(default_factory=list)
    retriever_patterns: Dict = Field(default_factory=lambda: {
        "enabled_patterns": [],
        "disabled_patterns": [],
        "custom_patterns": []
    })

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        """Class method to create an instance from a dictionary"""
        return cls(
            id=data.get('project_id', ''),
            name=data.get('project_name', ''),
            description=data.get('project_description', ''),
            vstore_index=data.get('vstore_index', ''),
            personality=data.get('personality', ''),
            datasources=data.get('datasources', []),
            integrations=Integrations.from_dict(data.get('integrations', {})),
            prompt=data.get('prompt', ''),
            instructions=data.get('instructions', 'hola'),
            prompt_memory=data.get('prompt_memory', ''),
            model=data.get('model', MODEL_CHATBOT),
            enabled_tools=data.get('enabled_tools', []),
            retriever_patterns=data.get('retriever_patterns', {
                "enabled_patterns": [],
                "disabled_patterns": [],
                "custom_patterns": []
            })
        )
