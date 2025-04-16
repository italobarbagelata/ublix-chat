from pydantic import BaseModel, Field
from typing import Optional, List

class WhatsAppConfig(BaseModel):
    """
    Model for WhatsApp configuration.
    """
    project_id: str = Field(..., description="Project ID associated with this WhatsApp configuration")
    phone_number_id: str = Field(..., description="WhatsApp Phone Number ID from Facebook Business")
    access_token: str = Field(..., description="Access token for WhatsApp API")
    business_account_id: Optional[str] = Field(None, description="WhatsApp Business Account ID")
    webhook_verify_token: Optional[str] = Field(None, description="Token for webhook verification")
    webhook_url: Optional[str] = Field(None, description="URL where webhooks are received")
    active: bool = Field(True, description="Whether this WhatsApp integration is active")

class WhatsAppTemplate(BaseModel):
    """
    Model for WhatsApp message templates.
    """
    name: str = Field(..., description="Template name")
    language_code: str = Field("es", description="Language code for the template")
    components: Optional[List[dict]] = Field(None, description="Template components (buttons, variables)")

class WhatsAppMessage(BaseModel):
    """
    Model for WhatsApp messages.
    """
    to: str = Field(..., description="Recipient phone number")
    message_type: str = Field("text", description="Message type (text, template, etc.)")
    text: Optional[str] = Field(None, description="Text message content")
    template: Optional[WhatsAppTemplate] = Field(None, description="Template message content")
    
    class Config:
        schema_extra = {
            "example": {
                "to": "5215512345678",
                "message_type": "text",
                "text": "Hello from WhatsApp API"
            }
        } 