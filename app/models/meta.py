from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MetaConfig(BaseModel):
    id: str
    project_id: str
    access_token: str
    business_id: str
    created_at: datetime
    updated_at: datetime

class MetaAuthResponse(BaseModel):
    auth_url: str

class MetaBusiness(BaseModel):
    id: str
    name: str

class WhatsAppBusinessAccount(BaseModel):
    id: str
    name: str

class WhatsAppPhoneNumber(BaseModel):
    id: str
    display_phone_number: str 