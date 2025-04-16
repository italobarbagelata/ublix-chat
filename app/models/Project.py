from pydantic import BaseModel
from datetime import datetime

class Project(BaseModel):
    project_id: str
    user_id: str
    name: str
    file_id: str = ""
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True