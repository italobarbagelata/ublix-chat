import logging
import httpx
from typing import Dict, Any, Optional
from app.resources.constants import INSTAGRAM_COLLECTION 
from app.controler.chat.store.persistence import SupabaseDatabase

INSTAGRAM_API_VERSION = "v23.0"
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
                logger.info(f"Configuración cargada - IG Account ID: {self.instagram_business_account_id}, Token disponible: {'Sí' if self.user_access_token else 'No'}")
                return True
            logger.warning(f"No se encontró configuración activa para project_id: {self.project_id}, instagram_page_id: {self.instagram_page_id}")
            return False
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            return False

    def is_configured(self) -> bool:
        """Verifica si el adaptador tiene la configuración necesaria."""
        return bool(self.user_access_token and self.instagram_business_account_id)


    async def send_message(self, recipient_igid: str, text: str, message_type: str = "text", attachment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Envía un mensaje a un usuario de Instagram."""
        logger.info(f"Intentando enviar mensaje de tipo '{message_type}' a recipient: {recipient_igid}")
        
        if not await self._load_config():
            error_msg = "Instagram no está configurado"
            logger.error(error_msg)
            return {"error": {"message": error_msg, "code": 400}}

        if not self.user_access_token:
            error_msg = "Token de acceso de Instagram no disponible"
            logger.error(error_msg)
            return {"error": {"message": error_msg, "code": 400}}

        # Construir payload según documentación oficial de Instagram API v23.0
        payload = {
            "recipient": {"id": recipient_igid}
        }

        if message_type == "text":
            payload["message"] = {"text": text}
        elif message_type in ["image", "audio", "video"]:
            if not attachment or "url" not in attachment:
                error_msg = f"URL requerida para {message_type}"
                logger.error(error_msg)
                return {"error": {"message": error_msg, "code": 400}}
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
                error_msg = "ID de post requerido"
                logger.error(error_msg)
                return {"error": {"message": error_msg, "code": 400}}
            payload["message"] = {
                "attachment": {
                    "type": "MEDIA_SHARE",
                    "payload": {"id": attachment["id"]}
                }
            }
        else:
            error_msg = f"Tipo de mensaje no soportado: {message_type}"
            logger.error(error_msg)
            return {"error": {"message": error_msg, "code": 400}}

        logger.debug(f"Payload construido: {payload}")

        try:
            async with httpx.AsyncClient() as client:
                # Usar Authorization header según documentación oficial
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.user_access_token}"
                }
                
                # Intentar primero con /me/messages
                url = f"{INSTAGRAM_API_BASE_URL}/me/messages"
                logger.info(f"Enviando mensaje a: {url}")
                
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers
                )
                
                logger.info(f"Respuesta inicial: {response.status_code}")
                
                # Si falla con /me/messages, intentar con /<IG_ID>/messages
                if response.status_code >= 400:
                    logger.warning(f"Fallo con /me/messages (status: {response.status_code}), intentando con /{self.instagram_business_account_id}/messages")
                    url = f"{INSTAGRAM_API_BASE_URL}/{self.instagram_business_account_id}/messages"
                    logger.info(f"URL alternativa: {url}")
                    
                    response = await client.post(
                        url,
                        json=payload,
                        headers=headers
                    )
                    
                    logger.info(f"Respuesta con URL alternativa: {response.status_code}")
                
                # Log del response body para debugging
                try:
                    response_data = response.json()
                    logger.debug(f"Response body: {response_data}")
                except:
                    logger.debug(f"Response text: {response.text}")
                
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            error_msg = f"Client error '{e.response.status_code} {e.response.reason_phrase}' for url '{e.request.url}'"
            logger.error(f"Error HTTP: {error_msg}")
            
            # Agregar información adicional del error para debugging
            try:
                error_details = e.response.json()
                logger.error(f"Detalles del error de Instagram API: {error_details}")
                
                # Manejar errores específicos de Instagram
                if e.response.status_code == 403:
                    error_msg = "Token inválido o sin permisos suficientes para Instagram"
                elif e.response.status_code == 400:
                    if "error" in error_details:
                        error_msg = f"Error 400: {error_details.get('error', {}).get('message', error_msg)}"
                
            except:
                logger.error(f"No se pudo parsear el error response: {e.response.text}")
                
            return {"error": {"message": error_msg, "code": e.response.status_code}}
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            logger.error(error_msg)
            return {"error": {"message": error_msg, "code": 500}}