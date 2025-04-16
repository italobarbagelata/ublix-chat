from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class CalendarBase(BaseModel):
    """Base model for calendar operations"""
    name: str
    color: Optional[str] = None
    
    
class CalendarCreate(CalendarBase):
    """Model for creating a new calendar"""
    project_id: UUID


class CalendarResponse(CalendarBase):
    """Response model for calendar operations"""
    id: UUID
    project_id: UUID
    created_at: datetime


class CalendarEventBase(BaseModel):
    """Base model for calendar event operations"""
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime


class CalendarEventCreate(CalendarEventBase):
    """Model for creating a new calendar event"""
    calendar_id: UUID
    user_id: str

class CalendarEventResponse(CalendarEventBase):
    """Response model for calendar event operations"""
    id: UUID
    calendar_id: UUID
    created_at: datetime


class CalendarWithEvents(CalendarResponse):
    """Calendar with its associated events"""
    events: List[CalendarEventResponse] = [] 