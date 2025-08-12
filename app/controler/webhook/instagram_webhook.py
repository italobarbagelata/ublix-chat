import logging
import json
import os
import httpx
from typing import Dict, Any, List, Optional
from fastapi import Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
from datetime import datetime, timedelta
from app.controler.chat.store.persistence import SupabaseDatabase
from app.models import ChatRequest
from app.chatbot import chatbot
INSTAGRAM_API_VERSION = "v23.0"
INSTAGRAM_API_BASE_URL = f"https://graph.instagram.com/{INSTAGRAM_API_VERSION}"
INSTAGRAM_COLLECTION = "integration_instagram"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("instagram_webhook")
load_dotenv()


async def verify_webhook_instagram(request: Request):
    """Verifica el webhook de Instagram cuando Facebook/Meta lo configura inicialmente."""
    logger.info("Iniciando verificación de webhook de Instagram")
    params = request.query_params
    verify_token = os.getenv("INSTAGRAM_VERIFY_TOKEN")
    
    logger.debug(f"Parámetros recibidos: {params}")
    logger.debug(f"Verify token configurado: {'Sí' if verify_token else 'No'}")
    
    if not verify_token:
        logger.error("INSTAGRAM_VERIFY_TOKEN no está configurado")
        raise HTTPException(status_code=500, detail="Error interno: Verify token no configurado")
    
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    logger.debug(f"Mode: {mode}, Token: {token}, Challenge: {challenge}")
    
    if not all([mode, token, challenge]):
        logger.warning("Faltan parámetros en la verificación del webhook")
        raise HTTPException(status_code=400, detail="Faltan parámetros")
    
    if mode == "subscribe" and token == verify_token:
        logger.info("Webhook de Instagram verificado exitosamente")
        return PlainTextResponse(content=str(challenge), status_code=200)
    else:
        logger.warning(f"Fallo en verificación de webhook de Instagram. Mode: {mode}, Token recibido: {token}")
        raise HTTPException(status_code=403, detail="Verificación fallida")


async def process_webhook_instagram(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Procesa los mensajes de webhook entrantes de Instagram."""
    try:
        logger.info("Iniciando procesamiento de webhook de Instagram")
        body = await request.json()
        logger.info(f"Webhook recibido: {json.dumps(body, indent=2)}")
        
        extracted_messages = extract_instagram_messages(body)
        total_messages = len(extracted_messages)
        
        logger.info(f"Se extrajeron {total_messages} mensajes del webhook")
        
        if total_messages == 0:
            logger.info("No hay mensajes para procesar (posiblemente un mensaje de eco)")
            return {"status": "ok", "processed": 0, "total": 0, "message": "No messages to process"}
        
        for message in extracted_messages:
            logger.debug(f"Programando procesamiento asíncrono para mensaje: {message.get('message_id', 'unknown')}")
            background_tasks.add_task(process_message_async, message)
        
        
        logger.info(f"Webhook procesado exitosamente. {total_messages} mensajes programados para procesamiento asíncrono")
        return {
            "status": "ok", 
            "total": total_messages,
            "message": f"Webhook received. {total_messages} messages scheduled for async processing",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error procesando webhook de Instagram: {e}", exc_info=True)
        return {
            "status": "error", 
            "detail": "Internal server error processing webhook",
            "message": "Webhook received but encountered processing error",
            "timestamp": datetime.now().isoformat()
        }


def extract_instagram_messages(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extrae los mensajes del webhook de Instagram."""
    messages = []
    try:
        logger.debug("Iniciando extracción de mensajes del webhook")
        for entry in body.get("entry", []):
            entry_id = entry.get("id")
            logger.info(f"Procesando entry ID: {entry_id}")
            
            for event in entry.get("messaging", []):
                if "message" in event:
                    message_obj = event["message"]
                    
                    if message_obj.get("is_echo", False):
                        logger.debug("Ignorando mensaje eco")
                        continue
                        
                    sender_id = event.get("sender", {}).get("id")
                    recipient_id = event.get("recipient", {}).get("id")
                    timestamp = event.get("timestamp")
                    message_id = message_obj.get("mid")
                    
                    logger.debug(f"Mensaje encontrado - Sender: {sender_id}, Recipient: {recipient_id}, Message ID: {message_id}")
                    
                    if "text" in message_obj:
                        message_data = {
                            "recipient_id": recipient_id,
                            "sender_id": sender_id,
                            "type": "text",
                            "text": message_obj.get("text", ""),
                            "timestamp": timestamp,
                            "message_id": message_id,
                            "entry_id": entry_id
                        }
                        logger.debug(f"Agregando mensaje de texto: {json.dumps(message_data, indent=2)}")
                        messages.append(message_data)
                    
                    elif "attachments" in message_obj:
                        attachments = message_obj.get("attachments", [])
                        for attachment in attachments:
                            attachment_type = attachment.get("type")
                            payload = attachment.get("payload", {})
                            
                            if attachment_type in ["image", "video", "audio"]:
                                message_data = {
                                    "recipient_id": recipient_id,
                                    "sender_id": sender_id,
                                    "type": attachment_type,
                                    "attachment_url": payload.get("url"),
                                    "attachment_id": payload.get("attachment_id"),
                                    "timestamp": timestamp,
                                    "message_id": message_id,
                                    "entry_id": entry_id
                                }
                                
                                if "text" in message_obj:
                                    message_data["text"] = message_obj.get("text", "")
                                
                                logger.debug(f"Agregando mensaje con {attachment_type}: {json.dumps(message_data, indent=2)}")
                                messages.append(message_data)
                    
                    elif "sticker_id" in message_obj:
                        message_data = {
                            "recipient_id": recipient_id,
                            "sender_id": sender_id,
                            "type": "sticker",
                            "sticker_id": message_obj.get("sticker_id"),
                            "timestamp": timestamp,
                            "message_id": message_id,
                            "entry_id": entry_id
                        }
                        logger.debug(f"Agregando sticker: {json.dumps(message_data, indent=2)}")
                        messages.append(message_data)
                        
    except Exception as e:
        logger.error(f"Error extrayendo mensajes IG: {e}", exc_info=True)
    return messages



async def get_project_id_for_instagram(recipient_id: str, sender_id: Optional[str] = None) -> Optional[str]:
    """Encuentra el project_id asociado con un webhook de Instagram."""
    logger.info(f"Buscando project_id para recipient_id: {recipient_id}, sender_id: {sender_id}")
    if not recipient_id:
        logger.warning("No se proporcionó recipient_id")
        return None
    try:
        db = SupabaseDatabase()
        logger.debug(f"Buscando configuración por instagram_page_id: {recipient_id}")
        instagram_config = db.find_one(INSTAGRAM_COLLECTION, {"instagram_page_id": recipient_id, "active": True})
        if instagram_config:
            logger.info(f"Configuración encontrada por instagram_page_id. Project ID: {instagram_config.get('project_id')}")
            return instagram_config.get("project_id")
         
        logger.warning(f"No se encontró configuración activa de Instagram para recipient_id: {recipient_id}")
        return None
    except Exception as e:
        logger.error(f"Error buscando project_id para Instagram: {e}", exc_info=True)
        return None



async def process_message_async(message: Dict[str, Any]):
    """Procesa un mensaje de Instagram en background sin bloquear la respuesta del webhook."""
    try:
        message_id = message.get('message_id', 'unknown')
        recipient_id = message.get("recipient_id")
        sender_id = message.get("sender_id")
        
        logger.info(f"Iniciando procesamiento en background para mensaje {message_id} - Sender: {sender_id}, Recipient: {recipient_id}")
        
        if not recipient_id or not sender_id:
            logger.warning(f"Mensaje IG omitido en background - Recipient: {recipient_id}, Sender: {sender_id}")
            return
        
        project_id = await get_project_id_for_instagram(recipient_id, sender_id)
        if not project_id:
            logger.error(f"No se encontró project_id válido para IG Recipient ID: {recipient_id}")
            return

        db = SupabaseDatabase()
        conversation_state = db.find_one("instagram_conversation_states", {
            "project_id": project_id,
            "instagram_page_id": recipient_id,
            "instagram_user_id": sender_id
        })
        
        if not conversation_state:
            conversation_state = {
                "project_id": project_id,
                "instagram_page_id": recipient_id,
                "instagram_user_id": sender_id,
                "bot_active": True
            }
            db.insert("instagram_conversation_states", conversation_state)
            logger.info(f"Nuevo estado de conversación de Instagram creado para usuario {sender_id}")
        elif not conversation_state.get("bot_active", True):
            logger.info(f"Bot desactivado para usuario {sender_id} - omitiendo procesamiento")
            return

        await process_message_content(message, project_id)
        
        logger.info(f"Procesamiento en background completado para mensaje {message_id}")
        
    except Exception as e:
        logger.error(f"Error en procesamiento background de mensaje IG: {e}", exc_info=True)


async def process_message_content(message: Dict[str, Any], project_id: str):
    """Procesa el contenido del mensaje de Instagram y envía la respuesta."""
    try:
        recipient_id = message.get("recipient_id")
        sender_id = message.get("sender_id")
        message_type = message.get("type")
        
        logger.info(f"Procesando contenido del mensaje - Tipo: {message_type}, Usuario: {sender_id}")
        
        # Obtener información del usuario de Instagram
        user_info = await get_instagram_user_info(sender_id, project_id, recipient_id)
        username = user_info.get("name", user_info.get("username", "Instagram User"))
        user_id = sender_id
        source_id = message.get("recipient_id")
        
        # Crear o actualizar el contacto
        await create_or_update_contact(
            project_id=project_id,
            platform="instagram",
            platform_user_id=sender_id,
            username=user_info.get("username"),
            full_name=user_info.get("name"),
            profile_data=user_info
        )
        
        text_message = message.get("text", "")
        image_url = None
        
        if message_type == "image" and message.get("attachment_url"):
            image_url = await process_image_attachment(message.get("attachment_url"), sender_id, project_id)
        
        elif message_type in ["video", "audio"] and message.get("attachment_url"):
            logger.info(f"Contenido multimedia recibido - Tipo: {message_type}, URL: {message.get('attachment_url')}")
        
        final_message = build_final_message(text_message, image_url, message_type)
        
        chat_request = ChatRequest(
            message=final_message,
            project_id=project_id,
            user_id=user_id,
            name=username,
            source="instagram",
            source_id=source_id,
            number_phone_agent="no number",
            debug=False
        )
        
        logger.info(f"Enviando mensaje al chatbot: {final_message[:100]}...")
        
        response = await chatbot(chat_request)
        
        if response.status_code != 200:
            logger.error(f"Error en la respuesta del chat: {response.body}")
            return
            
        response_data = json.loads(response.body)
        
        from app.controler.chat.core.utils import clean_response_from_image_patterns
        clean_response = clean_response_from_image_patterns(response_data["response"])
        
        logger.info(f"Enviando respuesta a Instagram")
        api_response = await send_instagram_message(sender_id, clean_response, project_id, recipient_id)
        
        if isinstance(api_response, dict) and "error" in api_response:
            logger.error(f"Error API IG al enviar mensaje: {api_response['error']}")
        else:
            logger.info(f"Respuesta enviada exitosamente a Instagram para usuario {sender_id}")
            logger.debug(f"Respuesta de Instagram API: {json.dumps(api_response, indent=2)}")

    except Exception as e:
        logger.error(f"Error procesando contenido de mensaje IG: {e}", exc_info=True)


async def process_image_attachment(attachment_url: str, sender_id: str, project_id: str) -> Optional[str]:
    """Procesa una imagen adjunta descargándola y guardándola en Supabase."""
    try:
        logger.info(f"Procesando imagen de Instagram: {attachment_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(attachment_url)
            if response.status_code == 200:
                import os
                from datetime import datetime
                from fastapi import UploadFile
                from io import BytesIO
                
                temp_dir = os.path.join(os.getcwd(), "temp_images")
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_filename = f"instagram_{sender_id}_{timestamp}.jpg"
                temp_filepath = os.path.join(temp_dir, temp_filename)
                
                with open(temp_filepath, "wb") as f:
                    f.write(response.content)
                
                logger.info(f"Imagen guardada temporalmente: {temp_filepath} ({len(response.content)} bytes)")
                
                with open(temp_filepath, "rb") as f:
                    image_content = f.read()
                
                image_file = UploadFile(
                    filename=temp_filename,
                    file=BytesIO(image_content)
                )
                
                from app.controler.chat.store.file_storage import FileStorage
                file_storage = FileStorage()
                image_url = await file_storage.save_image(project_id, image_file, content_type="image/jpeg")
                
                logger.info(f"Imagen guardada en Supabase: {image_url}")
                
                try:
                    os.remove(temp_filepath)
                    logger.debug(f"Archivo temporal eliminado: {temp_filepath}")
                except Exception as cleanup_error:
                    logger.warning(f"Error eliminando archivo temporal: {cleanup_error}")
                
                return image_url
                
            else:
                logger.error(f"Error descargando imagen de Instagram: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        logger.error(f"Error procesando imagen de Instagram: {e}", exc_info=True)
        return None


def build_final_message(text_message: str, image_url: Optional[str], message_type: str) -> str:
    """Construye el mensaje final combinando texto e imagen si están disponibles."""
    final_message = text_message
    
    if image_url:
        if text_message:
            final_message = f"{text_message}\n\n![Imagen]({image_url})"
        else:
            final_message = f"![Imagen]({image_url})"
    
    if not final_message:
        message_type_descriptions = {
            "image": "![Imagen recibida]",
            "video": "Video recibido",
            "audio": "Audio recibido",
            "sticker": "Sticker recibido"
        }
        final_message = message_type_descriptions.get(message_type, f"Archivo {message_type} recibido")
    
    return final_message


async def load_instagram_config(project_id: str, instagram_page_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Carga la configuración de Instagram desde la base de datos."""
    try:
        db = SupabaseDatabase()
        query = {"active": True}
        
        if instagram_page_id:
            query["instagram_page_id"] = instagram_page_id
        else:
            query["project_id"] = project_id

        config = db.find_one(INSTAGRAM_COLLECTION, query)
        if config:
            logger.info(f"Configuración cargada - IG Account ID: {config.get('instagram_business_account_id')}, Token disponible: {'Sí' if config.get('user_access_token') else 'No'}")
            return config
        logger.warning(f"No se encontró configuración activa para project_id: {project_id}, instagram_page_id: {instagram_page_id}")
        return None
    except Exception as e:
        logger.error(f"Error cargando configuración: {e}")
        return None


async def send_instagram_message(recipient_igid: str, text: str, project_id: str, instagram_page_id: Optional[str] = None, message_type: str = "text", attachment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Envía un mensaje a un usuario de Instagram."""
    logger.info(f"Intentando enviar mensaje de tipo '{message_type}' a recipient: {recipient_igid}")
    
    config = await load_instagram_config(project_id, instagram_page_id)
    if not config:
        error_msg = "Instagram no está configurado"
        logger.error(error_msg)
        return {"error": {"message": error_msg, "code": 400}}

    user_access_token = config.get("user_access_token")
    instagram_business_account_id = config.get("instagram_business_account_id")

    if not user_access_token:
        error_msg = "Token de acceso de Instagram no disponible"
        logger.error(error_msg)
        return {"error": {"message": error_msg, "code": 400}}

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
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {user_access_token}"
            }
            
            url = f"{INSTAGRAM_API_BASE_URL}/me/messages"
            logger.info(f"Enviando mensaje a: {url}")
            
            response = await client.post(
                url,
                json=payload,
                headers=headers
            )
            
            logger.info(f"Respuesta inicial: {response.status_code}")
            
            if response.status_code >= 400:
                logger.warning(f"Fallo con /me/messages (status: {response.status_code}), intentando con /{instagram_business_account_id}/messages")
                url = f"{INSTAGRAM_API_BASE_URL}/{instagram_business_account_id}/messages"
                logger.info(f"URL alternativa: {url}")
                
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers
                )
                
                logger.info(f"Respuesta con URL alternativa: {response.status_code}")
            
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
        
        try:
            error_details = e.response.json()
            logger.error(f"Detalles del error de Instagram API: {error_details}")
            
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


async def get_instagram_user_info(user_id: str, project_id: str, instagram_page_id: Optional[str] = None) -> Dict[str, Any]:
    """Obtiene información del usuario de Instagram usando la API Graph."""
    try:
        logger.info(f"Obteniendo información del usuario de Instagram: {user_id}")
        
        # Cargar configuración de Instagram
        config = await load_instagram_config(project_id, instagram_page_id)
        if not config:
            logger.warning("No se encontró configuración de Instagram")
            return {"id": user_id, "name": "Usuario de Instagram"}
        
        user_access_token = config.get("user_access_token")
        if not user_access_token:
            logger.warning("Token de acceso no disponible")
            return {"id": user_id, "name": "Usuario de Instagram"}
        
        # Hacer llamada directa a la API de Instagram para obtener información del usuario
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Campos disponibles: id, username, name
            fields = "id,username,name"
            url = f"{INSTAGRAM_API_BASE_URL}/{user_id}?fields={fields}&access_token={user_access_token}"
            
            logger.info(f"Llamando a Instagram API para usuario {user_id}")
            response = await client.get(url)
            
            logger.info(f"Respuesta de Instagram API: Status {response.status_code}")
            
            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"✅ Información del usuario obtenida exitosamente:")
                logger.info(f"  - ID: {user_data.get('id', 'N/A')}")
                logger.info(f"  - Nombre: {user_data.get('name', 'N/A')}")
                logger.info(f"  - Username: @{user_data.get('username', 'N/A')}")
                
                return user_data
            else:
                logger.warning(f"❌ Error obteniendo información del usuario: {response.status_code}")
                logger.warning(f"Respuesta: {response.text}")
                
                # Retornar información básica de fallback
                return {
                    "id": user_id, 
                    "name": f"Usuario {user_id[-4:]}", 
                    "username": f"user_{user_id[-4:]}"
                }
                
    except httpx.TimeoutException:
        logger.error(f"⏱️ Timeout al obtener información del usuario de Instagram")
        return {"id": user_id, "name": "Usuario de Instagram"}
    except Exception as e:
        logger.error(f"❌ Error obteniendo información del usuario de Instagram: {e}", exc_info=True)
        return {"id": user_id, "name": "Usuario de Instagram"}


async def create_or_update_contact(project_id: str, platform: str, platform_user_id: str, username: str = None, full_name: str = None, profile_data: dict = None):
    """Crea o actualiza un contacto en la tabla contacts."""
    try:
        from datetime import datetime
        db = SupabaseDatabase()
        
        # Buscar contacto existente
        existing_contact = db.find_one("contacts", {
            "project_id": project_id,
            "platform": platform,
            "platform_user_id": platform_user_id
        })
        
        contact_data = {
            "project_id": project_id,
            "platform": platform,
            "platform_user_id": platform_user_id,
            "username": username,
            "name": full_name or username or f"Usuario {platform}",
            "profile_data": profile_data or {},
            "last_interaction_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        if existing_contact:
            # Actualizar contacto existente
            contact_data["total_messages"] = existing_contact.get("total_messages", 0) + 1
            db.update("contacts", {"id": existing_contact["id"]}, contact_data)
            logger.info(f"Contacto actualizado: {platform_user_id}")
        else:
            # Crear nuevo contacto
            contact_data["total_messages"] = 1
            contact_data["lead_status"] = "new"
            contact_data["tags"] = []
            contact_data["created_at"] = datetime.now().isoformat()
            db.insert("contacts", contact_data)
            logger.info(f"Nuevo contacto creado: {platform_user_id}")
            
    except Exception as e:
        logger.error(f"Error creando/actualizando contacto: {e}", exc_info=True)


