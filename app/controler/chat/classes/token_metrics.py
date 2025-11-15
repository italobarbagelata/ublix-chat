from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TokenMetrics(BaseModel):
    project_id: str
    user_id: str  # ID del usuario que envió el mensaje (puede ser phone_number, UUID, etc)
    conversation_id: str
    message_id: str
    timestamp: datetime
    tokens: dict = {
        "system_prompt": 0,
        "input": 0,
        "output": 0,
        "context": 0,
        "tools": 0,
        "total": 0
    }
    cost: Optional[float] = None  # Podemos calcular el costo basado en los tokens
    source: str
    project_owner_id: Optional[str] = None  # ID del dueño del proyecto (para facturación) 