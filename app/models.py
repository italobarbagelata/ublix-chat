from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    project_id: str
    user_id: str
    name: str = "no name"
    source: str = ""
    source_id: str = ""
    number_phone_agent: str = "no number"
    debug: bool = False 