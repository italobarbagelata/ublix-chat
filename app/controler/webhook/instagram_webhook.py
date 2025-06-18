import logging
import json
import os
import httpx
from typing import Dict, Any, List, Optional
from fastapi import Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
from app.controler.chat.store.persistence import SupabaseDatabase
from app.models import ChatRequest
from app.chatbot import chatbot
from app.controler.webhook.instagram_adapter import InstagramAdapter

INSTAGRAM_API_VERSION = "v22.0"
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
async def process_instagram_message(message: Dict[str, Any], background_tasks: BackgroundTasks):
    """Procesa un mensaje de Instagram y envía respuesta a través del adapter."""
    try:
        logger.info(f"Iniciando procesamiento de mensaje: {json.dumps(message, indent=2)}")
        recipient_id = message.get("recipient_id")
        sender_id = message.get("sender_id")
        message_type = message.get("type")
        
        if not recipient_id or not sender_id:
            logger.warning(f"Mensaje IG omitido - Recipient: {recipient_id}, Sender: {sender_id}")
            return
        
        logger.info(f"Buscando project_id para el mensaje")
        project_id = await get_project_id_for_instagram(recipient_id, sender_id)
        if not project_id:
            logger.error(f"No se encontró project_id válido para IG Recipient ID: {recipient_id}")
            return

        # Verificar si el bot está desactivado para este usuario
        db = SupabaseDatabase()
        conversation_state = db.find_one("instagram_conversation_states", {
            "project_id": project_id,
            "instagram_page_id": recipient_id,
            "instagram_user_id": sender_id
        })
        
        if not conversation_state:
            # Si no existe el registro, crear uno nuevo con el bot activado
            conversation_state = {
                "project_id": project_id,
                "instagram_page_id": recipient_id,
                "instagram_user_id": sender_id,
                "bot_active": True
            }
            db.insert("instagram_conversation_states", conversation_state)
            logger.info("Nuevo estado de conversación de Instagram creado con bot activado")
        elif not conversation_state.get("bot_active", True):
            logger.info("Bot desactivado para este usuario de Instagram - omitiendo procesamiento")
            return

        # Inicializar el adaptador de Instagram para obtener información del usuario
        instagram_adapter = InstagramAdapter(project_id, recipient_id)
        
        # Obtener información detallada del usuario de Instagram
        logger.info(f"Obteniendo información detallada del usuario: {sender_id}")
        
        username = "Instagram User"
        user_id = sender_id
        source_id = message.get("recipient_id")
        
        # Preparar el mensaje y la imagen
        text_message = message.get("text", "")
        image_url = None
        
        # Si es un mensaje con imagen, descargar y guardar la imagen
        if message_type == "image" and message.get("attachment_url"):
            try:
                logger.info(f"Procesando imagen de Instagram: {message.get('attachment_url')}")
                
                # Descargar la imagen desde Instagram
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(message.get("attachment_url"))
                    if response.status_code == 200:
                        # Crear un archivo temporal con la imagen
                        import tempfile
                        import os
                        from datetime import datetime
                        
                        # Crear directorio temporal si no existe
                        temp_dir = os.path.join(os.getcwd(), "temp_images")
                        if not os.path.exists(temp_dir):
                            os.makedirs(temp_dir)
                        
                        # Generar nombre único para la imagen
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        file_extension = "jpg"  # Instagram generalmente usa JPG
                        temp_filename = f"instagram_{sender_id}_{timestamp}.{file_extension}"
                        temp_filepath = os.path.join(temp_dir, temp_filename)
                        
                        # Guardar la imagen
                        with open(temp_filepath, "wb") as f:
                            f.write(response.content)
                        
                        logger.info(f"Imagen guardada temporalmente: {temp_filepath} ({len(response.content)} bytes)")
                        
                        # Crear un objeto UploadFile simulado para el chat
                        from fastapi import UploadFile
                        from io import BytesIO
                        
                        # Leer el archivo guardado
                        with open(temp_filepath, "rb") as f:
                            image_content = f.read()
                        
                        # Crear UploadFile simulado
                        image_file = UploadFile(
                            filename=temp_filename,
                            content_type="image/jpeg",
                            file=BytesIO(image_content)
                        )
                        
                        # Guardar imagen en Supabase usando el servicio de archivos
                        from app.controler.chat.store.file_storage import FileStorage
                        file_storage = FileStorage()
                        image_url = await file_storage.save_image(project_id, image_file)
                        
                        logger.info(f"Imagen guardada en Supabase: {image_url}")
                        
                        # Limpiar archivo temporal
                        try:
                            os.remove(temp_filepath)
                            logger.debug(f"Archivo temporal eliminado: {temp_filepath}")
                        except Exception as cleanup_error:
                            logger.warning(f"Error eliminando archivo temporal: {cleanup_error}")
                        
                    else:
                        logger.error(f"Error descargando imagen de Instagram: {response.status_code} - {response.text}")
                        
            except Exception as e:
                logger.error(f"Error procesando imagen de Instagram: {e}", exc_info=True)
                # Continuar con el procesamiento sin imagen
        
        # Registrar otros tipos de contenido multimedia
        elif message_type in ["video", "audio"] and message.get("attachment_url"):
            logger.info(f"Contenido multimedia recibido - Tipo: {message_type}, URL: {message.get('attachment_url')}")
            # Por ahora solo registramos, no descargamos videos/audio
        
        # Construir el mensaje final
        final_message = text_message
        if image_url:
            if text_message:
                final_message = f"{text_message}\n\n![Imagen]({image_url})"
            else:
                final_message = f"![Imagen]({image_url})"
        
        # Si no hay mensaje de texto ni imagen, crear un mensaje descriptivo según el tipo
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
        
        # Obtener la respuesta usando el nuevo endpoint de chat
        response = await chatbot(chat_request)
        
        if response.status_code != 200:
            logger.error(f"Error en la respuesta del chat: {response.body}")
            return
            
        response_data = json.loads(response.body)

        # Enviar respuesta usando InstagramAdapter
        logger.info(f"Enviando respuesta a través de InstagramAdapter")
        api_response = await instagram_adapter.send_message(sender_id, response_data["response"])
        logger.info(f"Respuesta de Instagram API: {json.dumps(api_response, indent=2)}")

        if isinstance(api_response, dict) and "error" in api_response:
            logger.error(f"Error API IG al enviar mensaje: {api_response['error']}")
        else:
            logger.info(f"Respuesta enviada exitosamente a Instagram para usuario {sender_id}")

    except Exception as e:
        logger.error(f"Error procesando mensaje IG: {e}", exc_info=True)


########################################################
# Procesamiento de webhook de Instagram
########################################################
async def process_webhook_instagram(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Procesa los mensajes de webhook entrantes de Instagram."""
    try:
        logger.info("Iniciando procesamiento de webhook de Instagram")
        body = await request.json()
        logger.info(f"Webhook recibido: {json.dumps(body, indent=2)}")
        
        # Guardar el webhook para referencia
        await save_webhook_to_file(body)
        
        extracted_msgs = extract_instagram_messages(body)
        logger.info(f"Se extrajeron {len(extracted_msgs)} mensajes del webhook")
        
        if not extracted_msgs:
            logger.info("No hay mensajes para procesar (posiblemente un mensaje de eco)")
            return {"status": "ok", "processed": 0, "total": 0}
        
        processed_count = 0
        for msg in extracted_msgs:
            try:
                await process_instagram_message(msg, background_tasks)
                processed_count += 1
            except Exception as msg_err:
                logger.error(f"Error procesando mensaje: {msg_err}", exc_info=True)
                
        logger.info(f"Procesamiento completado. Mensajes procesados: {processed_count}/{len(extracted_msgs)}")
        return {"status": "ok", "processed": processed_count, "total": len(extracted_msgs)}
        
    except Exception as e:
        logger.error(f"Error procesando webhook de Instagram: {e}", exc_info=True)
        return {"status": "error", "detail": "Internal server error processing webhook"}
