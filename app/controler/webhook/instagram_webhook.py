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
from app.controler.webhook.instagram_adapter import InstagramAdapter

INSTAGRAM_API_VERSION = "v23.0"
INSTAGRAM_API_BASE_URL = f"https://graph.instagram.com/{INSTAGRAM_API_VERSION}"

# Configurar logging con más detalle
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("instagram_webhook")
load_dotenv()

INSTAGRAM_COLLECTION = "integration_instagram"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Cache para deduplicación de mensajes
message_cache = {}
CACHE_EXPIRY_MINUTES = 30


########################################################
# Verificación de webhook de Instagram
########################################################
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


########################################################
# Funciones auxiliares
########################################################
def is_message_duplicate(message_id: str, timestamp: int) -> bool:
    """
    Verifica si un mensaje ya fue procesado usando message_id y timestamp.
    
    Args:
        message_id: ID único del mensaje de Instagram
        timestamp: Timestamp del mensaje
        
    Returns:
        True si el mensaje ya fue procesado, False si es nuevo
    """
    try:
        # Crear clave única combinando message_id y timestamp
        cache_key = f"{message_id}_{timestamp}"
        
        # Obtener tiempo actual
        current_time = datetime.now()
        
        # Limpiar cache de mensajes expirados
        expired_keys = []
        for key, cached_time in message_cache.items():
            if current_time - cached_time > timedelta(minutes=CACHE_EXPIRY_MINUTES):
                expired_keys.append(key)
        
        # Remover claves expiradas
        for key in expired_keys:
            del message_cache[key]
            
        # Verificar si el mensaje ya existe en cache
        if cache_key in message_cache:
            logger.info(f"Mensaje duplicado detectado: {message_id} con timestamp {timestamp}")
            return True
            
        # Agregar mensaje al cache
        message_cache[cache_key] = current_time
        logger.debug(f"Mensaje agregado al cache: {cache_key}")
        return False
        
    except Exception as e:
        logger.error(f"Error verificando duplicación de mensaje: {e}")
        # En caso de error, no bloquear el mensaje
        return False
async def save_webhook_to_file(webhook_data: Dict[str, Any]):
    """Guarda un webhook en un archivo para referencia futura."""
    try:
        import os
        from datetime import datetime
        
        imports_dir = os.path.join(os.getcwd(), "imports")
        if not os.path.exists(imports_dir):
            os.makedirs(imports_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(imports_dir, f"instagram_webhook_{timestamp}.json")
        
        with open(file_path, 'w') as f:
            json.dump(webhook_data, f, indent=2)
            
    except Exception as e:
        logger.warning(f"Error guardando webhook en archivo: {e}")

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
                    # Ignorar mensajes que son ecos
                    if message_obj.get("is_echo", False):
                        logger.debug("Ignorando mensaje eco")
                        continue
                        
                    sender_id = event.get("sender", {}).get("id")
                    recipient_id = event.get("recipient", {}).get("id")
                    timestamp = event.get("timestamp")
                    message_id = message_obj.get("mid")
                    
                    logger.debug(f"Mensaje encontrado - Sender: {sender_id}, Recipient: {recipient_id}, Message ID: {message_id}")
                    
                    # Verificar duplicación antes de procesar
                    if is_message_duplicate(message_id, timestamp):
                        logger.info(f"Mensaje duplicado ignorado: {message_id} con timestamp {timestamp}")
                        continue
                    
                    # Procesar mensajes de texto
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
                    
                    # Procesar mensajes con archivos adjuntos (imágenes, videos, audio)
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
                                
                                # Si hay texto junto con el archivo adjunto
                                if "text" in message_obj:
                                    message_data["text"] = message_obj.get("text", "")
                                
                                logger.debug(f"Agregando mensaje con {attachment_type}: {json.dumps(message_data, indent=2)}")
                                messages.append(message_data)
                    
                    # Procesar stickers
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

async def get_instagram_user_info(instagram_id: str, access_token: str) -> Dict[str, Any]:
    """
    Obtiene la información de un usuario de Instagram usando su ID.
    
    Args:
        instagram_id: El ID de Instagram del usuario.
        access_token: Token de acceso para la API de Instagram.
        
    Returns:
        Dict con la información del usuario o información de error.
    """
    if not access_token:
        error_msg = "No hay token de acceso configurado"
        logger.error(error_msg)
        return {"error": {"message": error_msg, "code": 400}}
        
    try:
        async with httpx.AsyncClient() as client:
            url = f"{INSTAGRAM_API_BASE_URL}/{instagram_id}"
            params = {
                "access_token": access_token,
                "fields": "id"
            }
            
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                error_msg = f"Error al obtener información del usuario: {response.status_code}"
                logger.error(f"{error_msg} - {response.text}")
                return {"error": {"message": error_msg, "code": response.status_code}}
            
            user_data = response.json()
            logger.info(f"Información obtenida del usuario Instagram {instagram_id}: {user_data}")
            return user_data
            
    except httpx.HTTPError as e:
        error_msg = f"Error HTTP al obtener información del usuario: {str(e)}"
        logger.error(error_msg)
        return {"error": {"message": error_msg, "code": 500}}
    except Exception as e:
        error_msg = f"Error inesperado al obtener información del usuario: {str(e)}"
        logger.error(error_msg)
        return {"error": {"message": error_msg, "code": 500}}


########################################################
# Procesamiento de mensaje de Instagram
########################################################
async def process_instagram_message_background(message: Dict[str, Any]):
    """
    Procesa un mensaje de Instagram en background sin bloquear la respuesta del webhook.
    Esta función se ejecuta de forma completamente asíncrona.
    """
    try:
        message_id = message.get('message_id', 'unknown')
        recipient_id = message.get("recipient_id")
        sender_id = message.get("sender_id")
        
        logger.info(f"🔄 Iniciando procesamiento en background para mensaje {message_id} - Sender: {sender_id}, Recipient: {recipient_id}")
        
        if not recipient_id or not sender_id:
            logger.warning(f"❌ Mensaje IG omitido en background - Recipient: {recipient_id}, Sender: {sender_id}")
            return
        
        # Buscar project_id
        project_id = await get_project_id_for_instagram(recipient_id, sender_id)
        if not project_id:
            logger.error(f"❌ No se encontró project_id válido para IG Recipient ID: {recipient_id}")
            return

        # Verificar estado de conversación
        db = SupabaseDatabase()
        conversation_state = db.find_one("instagram_conversation_states", {
            "project_id": project_id,
            "instagram_page_id": recipient_id,
            "instagram_user_id": sender_id
        })
        
        if not conversation_state:
            # Crear nuevo estado de conversación
            conversation_state = {
                "project_id": project_id,
                "instagram_page_id": recipient_id,
                "instagram_user_id": sender_id,
                "bot_active": True
            }
            db.insert("instagram_conversation_states", conversation_state)
            logger.info(f"✅ Nuevo estado de conversación de Instagram creado para usuario {sender_id}")
        elif not conversation_state.get("bot_active", True):
            logger.info(f"🚫 Bot desactivado para usuario {sender_id} - omitiendo procesamiento")
            return

        # Procesar el mensaje completo
        await process_instagram_message_content(message, project_id)
        
        logger.info(f"✅ Procesamiento en background completado para mensaje {message_id}")
        
    except Exception as e:
        logger.error(f"❌ Error en procesamiento background de mensaje IG: {e}", exc_info=True)


async def process_instagram_message_content(message: Dict[str, Any], project_id: str):
    """
    Procesa el contenido del mensaje de Instagram y envía la respuesta.
    Separado para mejor organización del código.
    """
    try:
        recipient_id = message.get("recipient_id")
        sender_id = message.get("sender_id")
        message_type = message.get("type")
        
        # Inicializar el adaptador de Instagram
        instagram_adapter = InstagramAdapter(project_id, recipient_id)
        
        logger.info(f"📝 Procesando contenido del mensaje - Tipo: {message_type}, Usuario: {sender_id}")
        
        username = "Instagram User"
        user_id = sender_id
        source_id = message.get("recipient_id")
        
        # Preparar el mensaje y la imagen
        text_message = message.get("text", "")
        image_url = None
        
        # Procesar imágenes si las hay
        if message_type == "image" and message.get("attachment_url"):
            try:
                logger.info(f"🖼️ Procesando imagen de Instagram: {message.get('attachment_url')}")
                
                # Descargar la imagen desde Instagram
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(message.get("attachment_url"))
                    if response.status_code == 200:
                        # Crear directorio temporal si no existe
                        import os
                        from datetime import datetime
                        
                        temp_dir = os.path.join(os.getcwd(), "temp_images")
                        if not os.path.exists(temp_dir):
                            os.makedirs(temp_dir)
                        
                        # Generar nombre único para la imagen
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        temp_filename = f"instagram_{sender_id}_{timestamp}.jpg"
                        temp_filepath = os.path.join(temp_dir, temp_filename)
                        
                        # Guardar la imagen
                        with open(temp_filepath, "wb") as f:
                            f.write(response.content)
                        
                        logger.info(f"💾 Imagen guardada temporalmente: {temp_filepath} ({len(response.content)} bytes)")
                        
                        # Crear UploadFile simulado
                        from fastapi import UploadFile
                        from io import BytesIO
                        
                        with open(temp_filepath, "rb") as f:
                            image_content = f.read()
                        
                        image_file = UploadFile(
                            filename=temp_filename,
                            file=BytesIO(image_content)
                        )
                        
                        # Guardar imagen en Supabase
                        from app.controler.chat.store.file_storage import FileStorage
                        file_storage = FileStorage()
                        image_url = await file_storage.save_image(project_id, image_file, content_type="image/jpeg")
                        
                        logger.info(f"☁️ Imagen guardada en Supabase: {image_url}")
                        
                        # Limpiar archivo temporal
                        try:
                            os.remove(temp_filepath)
                            logger.debug(f"🗑️ Archivo temporal eliminado: {temp_filepath}")
                        except Exception as cleanup_error:
                            logger.warning(f"⚠️ Error eliminando archivo temporal: {cleanup_error}")
                        
                    else:
                        logger.error(f"❌ Error descargando imagen de Instagram: {response.status_code} - {response.text}")
                        
            except Exception as e:
                logger.error(f"❌ Error procesando imagen de Instagram: {e}", exc_info=True)
        
        # Registrar otros tipos de contenido multimedia
        elif message_type in ["video", "audio"] and message.get("attachment_url"):
            logger.info(f"🎬 Contenido multimedia recibido - Tipo: {message_type}, URL: {message.get('attachment_url')}")
        
        # Construir el mensaje final
        final_message = text_message
        if image_url:
            if text_message:
                final_message = f"{text_message}\n\n![Imagen]({image_url})"
            else:
                final_message = f"![Imagen]({image_url})"
        
        # Crear mensaje descriptivo si no hay texto ni imagen
        if not final_message:
            if message_type == "image":
                final_message = "![Imagen recibida]"
            elif message_type == "video":
                final_message = "📹 Video recibido"
            elif message_type == "audio":
                final_message = "🎵 Audio recibido"
            elif message_type == "sticker":
                final_message = "😊 Sticker recibido"
            else:
                final_message = f"📎 Archivo {message_type} recibido"
        
        # Crear el objeto ChatRequest
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
        
        logger.info(f"🤖 Enviando mensaje al chatbot: {final_message[:100]}...")
        
        # Obtener la respuesta del chatbot
        response = await chatbot(chat_request)
        
        if response.status_code != 200:
            logger.error(f"❌ Error en la respuesta del chat: {response.body}")
            return
            
        response_data = json.loads(response.body)
        
        # Enviar respuesta usando InstagramAdapter
        logger.info(f"📤 Enviando respuesta a través de InstagramAdapter")
        api_response = await instagram_adapter.send_message(sender_id, response_data["response"])
        
        if isinstance(api_response, dict) and "error" in api_response:
            logger.error(f"❌ Error API IG al enviar mensaje: {api_response['error']}")
        else:
            logger.info(f"✅ Respuesta enviada exitosamente a Instagram para usuario {sender_id}")
            logger.debug(f"📋 Respuesta de Instagram API: {json.dumps(api_response, indent=2)}")

    except Exception as e:
        logger.error(f"❌ Error procesando contenido de mensaje IG: {e}", exc_info=True)


########################################################
# Procesamiento de webhook de Instagram
########################################################
async def process_webhook_instagram(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Procesa los mensajes de webhook entrantes de Instagram."""
    try:
        logger.info("Iniciando procesamiento de webhook de Instagram")
        body = await request.json()
        logger.info(f"Webhook recibido: {json.dumps(body, indent=2)}")
        
        # RESPUESTA INMEDIATA: Extraer mensajes básicos para validación rápida
        extracted_msgs = extract_instagram_messages(body)
        total_messages = len(extracted_msgs)
        
        logger.info(f"Se extrajeron {total_messages} mensajes del webhook")
        
        if total_messages == 0:
            logger.info("No hay mensajes para procesar (posiblemente un mensaje de eco)")
            # Respuesta inmediata para Instagram
            return {"status": "ok", "processed": 0, "total": 0, "message": "No messages to process"}
        
        # PROGRAMAR PROCESAMIENTO ASÍNCRONO: Agregar todas las tareas a background_tasks
        for msg in extracted_msgs:
            logger.debug(f"Programando procesamiento asíncrono para mensaje: {msg.get('message_id', 'unknown')}")
            background_tasks.add_task(process_instagram_message_background, msg)
        
        # Guardar webhook para referencia (también en background)
        background_tasks.add_task(save_webhook_to_file, body)
        
        # RESPUESTA INMEDIATA A INSTAGRAM: Evitar reenvíos
        logger.info(f"✅ Webhook procesado exitosamente. {total_messages} mensajes programados para procesamiento asíncrono")
        return {
            "status": "ok", 
            "total": total_messages,
            "message": f"Webhook received. {total_messages} messages scheduled for async processing",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        # Incluso si hay error, responder 200 para evitar reenvíos de Instagram
        logger.error(f"Error procesando webhook de Instagram: {e}", exc_info=True)
        return {
            "status": "error", 
            "detail": "Internal server error processing webhook",
            "message": "Webhook received but encountered processing error",
            "timestamp": datetime.now().isoformat()
        }
