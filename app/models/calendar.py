from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
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


# Modelos para eventos locales (nueva tabla calendar_events)
class CalendarEventLocalBase(BaseModel):
    """Modelo base para eventos almacenados localmente"""
    title: str
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    attendee_email: Optional[str] = None
    attendee_name: Optional[str] = None
    attendee_phone: Optional[str] = None
    location: Optional[str] = None
    google_meet_url: Optional[str] = None
    event_url: Optional[str] = None
    status: str = 'confirmed'
    conversation_summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CalendarEventLocalCreate(CalendarEventLocalBase):
    """Modelo para crear eventos locales"""
    project_id: UUID
    google_event_id: Optional[str] = None
    created_by_user_id: Optional[str] = None


class CalendarEventLocalUpdate(BaseModel):
    """Modelo para actualizar eventos locales"""
    title: Optional[str] = None
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    attendee_email: Optional[str] = None
    attendee_name: Optional[str] = None
    attendee_phone: Optional[str] = None
    location: Optional[str] = None
    google_meet_url: Optional[str] = None
    event_url: Optional[str] = None
    status: Optional[str] = None
    conversation_summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CalendarEventLocalResponse(CalendarEventLocalBase):
    """Modelo de respuesta para eventos locales"""
    id: UUID
    project_id: UUID
    google_event_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CalendarEventListResponse(BaseModel):
    """Respuesta para lista de eventos con paginación"""
    events: List[CalendarEventLocalResponse]
    total_count: int
    page: int = 1
    page_size: int = 50 