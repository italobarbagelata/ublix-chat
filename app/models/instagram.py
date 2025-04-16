from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
import uuid
from datetime import datetime

class InstagramConfig(BaseModel):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    instagram_page_id: str = Field(..., max_length=255, description="ID de la página de Instagram Business o Creator.")
    access_token: str = Field(..., description="Page Access Token de larga duración.")
    user_access_token: Optional[str] = Field(None, description="Token de acceso de usuario para OAuth.")
    instagram_app_id: Optional[str] = Field(None, max_length=255, description="ID de la App de Facebook/Meta asociada.")
    webhook_verify_token: Optional[str] = Field(None, max_length=255, description="Token de verificación para el webhook.")
    webhook_url: Optional[HttpUrl] = Field(None, description="URL del webhook (si se configura).")
    instagram_business_account_id: Optional[str] = Field(None, max_length=255, description="ID de la cuenta de Instagram Business.")
    instagram_username: Optional[str] = Field(None, max_length=255, description="Nombre de usuario de Instagram.")
    instagram_name: Optional[str] = Field(None, max_length=255, description="Nombre completo de Instagram.")
    instagram_profile_picture: Optional[str] = Field(None, description="URL de la imagen de perfil de Instagram.")
    active: bool = True
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True # Compatible con ORM si se usa
        anystr_strip_whitespace = True
        validate_assignment = True
        schema_extra = {
            "example": {
                "project_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "instagram_page_id": "17841405822304914", # Ejemplo de Page ID
                "access_token": "EAA...", 
                "user_access_token": "EAA...",
                "instagram_app_id": "987654321098765", # Ejemplo de App ID
                "webhook_verify_token": "un_token_secreto_muy_seguro",
                "webhook_url": "https://tu-app.com/api/instagram/webhook",
                "instagram_business_account_id": "17895694532145876",
                "instagram_username": "mi_negocio",
                "instagram_name": "Mi Negocio Oficial",
                "instagram_profile_picture": "https://scontent.xx.fbcdn.net/v/t1.0-1/...",
                "active": True
            }
        }

class InstagramSendMessage(BaseModel):
    project_id: uuid.UUID
    recipient_id: str = Field(..., description="IGSID del destinatario")
    message: str = Field(..., description="Mensaje a enviar")

class OAuthState(BaseModel):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4)
    state: str = Field(..., description="Valor aleatorio para verificación CSRF")
    project_id: str = Field(..., description="ID del proyecto asociado a esta autorización")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(..., description="Tiempo de expiración del state")

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "state": "abc123xyz",
                "project_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "created_at": "2023-07-15T14:30:00",
                "expires_at": "2023-07-15T15:00:00"
            }
        } 