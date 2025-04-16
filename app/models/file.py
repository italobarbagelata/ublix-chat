from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class File(BaseModel):
    """
    File model representing a file in the system
    """
    id: str
    project_id: str
    name: str
    path: str
    size: int
    mime_type: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True  # For SQLAlchemy compatibility
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "project_id": "123e4567-e89b-12d3-a456-426614174001",
                "name": "document.pdf",
                "path": "/projects/123/documents/",
                "size": 1024,
                "mime_type": "application/pdf",
                "created_at": "2024-03-20T10:00:00",
                "updated_at": "2024-03-20T10:00:00",
                "deleted_at": None
            }
        } 