import logging
import httpx
from typing import Dict, Any, Optional
from app.resources.constants import INSTAGRAM_COLLECTION 
from app.controler.chat.store.persistence import SupabaseDatabase

INSTAGRAM_API_VERSION = "v22.0"
INSTAGRAM_API_BASE_URL = f"https://graph.instagram.com/{INSTAGRAM_API_VERSION}"

logger = logging.getLogger("root")

class InstagramAdapter:
    """
    Adaptador para interactuar con la API de Mensajería de Instagram
    utilizando Instagram Business Login.
    """
    def __init__(self, project_id: str, instagram_page_id: Optional[str] = None):
        self.project_id = project_id
        self.instagram_page_id = instagram_page_id
        self.user_access_token = None
        self.instagram_business_account_id = None

    async def _load_config(self):
        """Carga la configuración de Instagram desde la base de datos."""
        try:
            db = SupabaseDatabase()
            query = {"active": True}
            
            if self.instagram_page_id:
                query["instagram_page_id"] = self.instagram_page_id
            else:
                query["project_id"] = self.project_id

            config = db.find_one(INSTAGRAM_COLLECTION, query)
            if config:
                self.user_access_token = config.get("user_access_token")
                self.instagram_business_account_id = config.get("instagram_business_account_id")
                return True
            return False
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            return False

    def is_configured(self) -> bool:
        """Verifica si el adaptador tiene la configuración necesaria."""
        return bool(self.user_access_token and self.instagram_business_account_id)


    async def send_message(self, recipient_igid: str, text: str, message_type: str = "text", attachment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Envía un mensaje a un usuario de Instagram."""
        if not await self._load_config():
            return {"error": {"message": "Instagram no está configurado", "code": 400}}

        payload = {
            "recipient": {"id": recipient_igid},
            "messaging_type": "RESPONSE"
        }

        if message_type == "text":
            payload["message"] = {"text": text}
        elif message_type in ["image", "audio", "video"]:
            if not attachment or "url" not in attachment:
                return {"error": {"message": f"URL requerida para {message_type}", "code": 400}}
            payload["message"] = {
                "attachment": {
                    "type": message_type,
                    "payload": {"url": attachment["url"]}
                }
            }
        elif message_type == "sticker":
            payload["message"] = {"attachment": {"type": "like_heart"}}
        elif message_type == "media_share":
            if not attachment or "id" not in attachment:
                return {"error": {"message": "ID de post requerido", "code": 400}}
            payload["message"] = {
                "attachment": {
                    "type": "MEDIA_SHARE",
                    "payload": {"id": attachment["id"]}
                }
            }
        else:
            return {"error": {"message": f"Tipo de mensaje no soportado: {message_type}", "code": 400}}

        try:
            async with httpx.AsyncClient() as client:
                url = f"{INSTAGRAM_API_BASE_URL}/me/messages"
                response = await client.post(
                    url,
                    json=payload,
                    params={"access_token": self.user_access_token}
                )
                
                if response.status_code >= 400:
                    url = f"{INSTAGRAM_API_BASE_URL}/{self.instagram_business_account_id}/messages"
                    response = await client.post(
                        url,
                        json=payload,
                        params={"access_token": self.user_access_token}
                    )
                
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            error_msg = str(e)
            if e.response.status_code == 403:
                error_msg = "Token inválido o sin permisos suficientes"
            return {"error": {"message": error_msg, "code": e.response.status_code}}
        except Exception as e:
            return {"error": {"message": str(e), "code": 500}}