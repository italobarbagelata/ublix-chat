from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

class Datasource(BaseModel):
    """
    Datasource model representing a data source in the system
    """
    datasource_id: UUID = Field(default_factory=lambda: None)
    name: str
    status: Optional[str] = None
    type: str
    configuration: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    project_id: UUID
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "datasource_id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "My PostgreSQL Database",
                "status": "active",
                "type": "postgresql",
                "configuration": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "mydb"
                },
                "created_at": "2024-03-20T10:00:00",
                "updated_at": "2024-03-20T10:00:00",
                "project_id": "123e4567-e89b-12d3-a456-426614174001",
                "metadata": {
                    "version": "14.2",
                    "description": "Production database"
                }
            }
        } 