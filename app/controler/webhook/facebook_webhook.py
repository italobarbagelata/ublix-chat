import logging
import json
import os
from typing import Dict, Any, List
from fastapi import Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from app.resources.constants import STATUS_BAD_REQUEST, STATUS_UNAUTHORIZED
from app.controler.chat.core.graph import Graph
from app.resources.postgresql import SupabaseDatabase
import httpx
from datetime import datetime
import asyncio
from app.models import ChatRequest
from app.chatbot import chatbot

logger = logging.getLogger("root")

TABLE_INTEGRATION = "integration_messenger"
TABLE_CONVERSATION_STATES = "messenger_conversation_states"

async def verify_webhook_facebook(request: Request):
    """
    Verifica la suscripción del webhook de Messenger enviada por Meta.

    Meta enviará una solicitud GET con los parámetros:
    - hub.mode
    - hub.verify_token
    - hub.challenge

    Si el token es válido y el modo es 'subscribe', se debe retornar el challenge en texto plano.
    """
    params = request.query_params

    # Obtener el token de verificación desde las variables de entorno
    verify_token = os.getenv("MESSENGER_VERIFY_TOKEN")
    if not verify_token:
        logger.error("MESSENGER_VERIFY_TOKEN no está configurado en las variables de entorno")
        raise HTTPException(status_code=500, detail="Error interno: Verify token no configurado")

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    # Verifica que todos los parámetros requeridos estén presentes
    if not all([mode, token, challenge]):
        logger.warning(f"Parámetros faltantes en la verificación del webhook: {params}")
        raise HTTPException(status_code=400, detail="Faltan parámetros requeridos")

    # Validar el modo y el token
    if mode == "subscribe" and token == verify_token:
        logger.info("Webhook verificado correctamente")
        return PlainTextResponse(content=str(challenge), status_code=200)
    else:
        logger.warning("Fallo en la verificación del webhook: token inválido o modo incorrecto")
        raise HTTPException(status_code=403, detail="Verificación fallida")

async def process_webhook_facebook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Procesa los eventos entrantes del webhook de Messenger.
    
    Args:
        request: El objeto Request de FastAPI
        background_tasks: Tareas en segundo plano de FastAPI
        
    Returns:
        Respuesta indicando el procesamiento exitoso
    """
    try:
        body = await request.json()
        logger.info(f"Webhook recibido: {json.dumps(body, indent=2)}")
        
        # Verificar si es un mensaje válido de Messenger
        if not is_valid_messenger_message(body):
            logger.info("No es un mensaje válido de Messenger")
            return {"status": "ok"}
        
        # Extraer mensajes del webhook
        messages = extract_messages(body)
        
        # Responder inmediatamente a Facebook
        response = {"status": "ok"}
        
        # Procesar mensajes de forma asíncrona
        for message in messages:
            # Procesar cada mensaje (cambiar create_task por await)
            await process_message(message, background_tasks)
        
        return response
    except Exception as e:
        logger.error(f"Error procesando webhook: {e}", exc_info=True)
        raise HTTPException(status_code=STATUS_BAD_REQUEST, detail=str(e))

def is_valid_messenger_message(body: Dict[str, Any]) -> bool:
    """
    Verifica si el webhook contiene un mensaje válido de Messenger.
    
    Args:
        body: El cuerpo del webhook
        
    Returns:
        True si es un mensaje válido de Messenger, False en caso contrario
    """
    logger.info(f"Validando mensaje de Messenger. Object: {body.get('object')}, Entry: {body.get('entry')}")
    return (
        body.get("object") == "page" and
        body.get("entry") and
        len(body["entry"]) > 0 and
        body["entry"][0].get("messaging") and
        len(body["entry"][0]["messaging"]) > 0
    )

def extract_messages(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrae mensajes del cuerpo del webhook.
    
    Args:
        body: El cuerpo del webhook
        
    Returns:
        Lista de objetos de mensaje
    """
    messages = []
    
    try:
        entry = body["entry"][0]
        messaging = entry["messaging"][0]
        
        # Obtener el ID del remitente y el ID de la página
        sender_id = messaging.get("sender", {}).get("id")
        page_id = entry.get("id")  # ID de la página que recibió el mensaje
        
        # Extraer el mensaje
        if "message" in messaging:
            message = messaging["message"]
            
            # Verificar si hay attachments (imágenes, archivos, etc.)
            if "attachments" in message and message["attachments"]:
                attachment = message["attachments"][0]
                attachment_type = attachment.get("type", "image")
                
                if attachment_type == "image":
                    # Imagen con URL directa
                    payload = attachment.get("payload", {})
                    image_url = payload.get("url")
                    
                    messages.append({
                        "sender_id": sender_id,
                        "page_id": page_id,
                        "type": "image",
                        "image_url": image_url,  # URL directa de la imagen
                        "timestamp": messaging.get("timestamp"),
                        "message_id": message.get("mid")
                    })
                else:
                    # Otros tipos de attachments
                    messages.append({
                        "sender_id": sender_id,
                        "page_id": page_id,
                        "type": attachment_type,
                        "attachment_url": attachment.get("payload", {}).get("url"),
                        "timestamp": messaging.get("timestamp"),
                        "message_id": message.get("mid")
                    })
            else:
                # Mensaje de texto normal
                message_type = message.get("type", "text")
                
                if message_type == "text":
                    messages.append({
                        "sender_id": sender_id,
                        "page_id": page_id,
                        "type": message_type,
                        "text": message.get("text", ""),
                        "timestamp": messaging.get("timestamp"),
                        "message_id": message.get("mid")
                    })
                elif message_type in ["image", "audio", "file", "video"]:
                    # Manejar mensajes multimedia con media_id
                    messages.append({
                        "sender_id": sender_id,
                        "page_id": page_id,
                        "type": message_type,
                        "media_id": message.get(message_type, {}).get("id"),
                        "timestamp": messaging.get("timestamp"),
                        "message_id": message.get("mid")
                    })
    except Exception as e:
        logger.error(f"Error extrayendo mensajes: {e}")
    
    return messages

async def process_message(message: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Procesa un mensaje individual de Messenger.
    
    Args:
        message: El objeto de mensaje
        background_tasks: Tareas en segundo plano de FastAPI
    """
    try:
        logger.info(f"Iniciando procesamiento de mensaje: {json.dumps(message, indent=2)}")
        
        # Procesar solo texto o imagen
        if message["type"] not in ["text", "image"]:
            logger.info(f"Omitiendo mensaje no soportado de tipo: {message['type']}")
            return
        
        # Obtener el ID del proyecto asociado con esta página de Facebook
        db = SupabaseDatabase()
        logger.info(f"Buscando configuración para page_id: {message['page_id']}")
        
        # Buscar todas las configuraciones activas de Messenger
        configs = db.find(TABLE_INTEGRATION, {
            "integration_type": "messenger", 
            "active": True
        })
        
        # Buscar la configuración que tenga el page_id en su array pages
        config = None
        for cfg in configs:
            pages = cfg.get("pages", [])
            # Si pages es una cadena, intentar parsearla como JSON
            if isinstance(pages, str):
                try:
                    pages = json.loads(pages)
                except json.JSONDecodeError:
                    logger.error(f"Error parseando pages como JSON: {pages}")
                    continue
            
            if any(page.get("id") == message["page_id"] for page in pages):
                config = cfg
                break
        
        if not config:
            logger.warning(f"No se encontró configuración activa de Messenger para page_id: {message['page_id']}")
            return
        
        logger.info(f"Configuración encontrada: {json.dumps(config, indent=2)}")
        project_id = config.get("project_id")
        
        # Verificar si el bot está desactivado para este usuario
        conversation_state = db.find_one(TABLE_CONVERSATION_STATES, {
            "project_id": project_id,
            "page_id": message["page_id"],
            "user_id": message["sender_id"]
        })
        
        if not conversation_state:
            # Si no existe el registro, crear uno nuevo con el bot activado
            conversation_state = {
                "project_id": project_id,
                "page_id": message["page_id"],
                "user_id": message["sender_id"],
                "bot_active": True
            }
            db.insert(TABLE_CONVERSATION_STATES, conversation_state)
            logger.info("Nuevo estado de conversación creado con bot activado")
        elif not conversation_state.get("bot_active", True):
            logger.info("Bot desactivado para este usuario - omitiendo procesamiento")
            return
        
        user_id = message["sender_id"]
        source_id = message["page_id"]
        final_message = None
        image_url = None
        
        if message["type"] == "image":
            if message.get("image_url"):
                # Imagen con URL directa (attachments)
                logger.info(f"Procesando imagen de Messenger con URL directa: {message.get('image_url')}")
                try:
                    import os
                    from datetime import datetime
                    from fastapi import UploadFile
                    from io import BytesIO
                    
                    # Descargar la imagen directamente desde la URL
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        img_response = await client.get(message["image_url"])
                        if img_response.status_code == 200:
                            # Crear directorio temporal si no existe
                            temp_dir = os.path.join(os.getcwd(), "temp_images")
                            if not os.path.exists(temp_dir):
                                os.makedirs(temp_dir)
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            temp_filename = f"messenger_{user_id}_{timestamp}.jpg"
                            temp_filepath = os.path.join(temp_dir, temp_filename)
                            with open(temp_filepath, "wb") as f:
                                f.write(img_response.content)
                            logger.info(f"Imagen guardada temporalmente: {temp_filepath} ({len(img_response.content)} bytes)")
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
                            logger.info(f"Imagen guardada en Supabase: {image_url}")
                            try:
                                os.remove(temp_filepath)
                                logger.debug(f"Archivo temporal eliminado: {temp_filepath}")
                            except Exception as cleanup_error:
                                logger.warning(f"Error eliminando archivo temporal: {cleanup_error}")
                            # Construir mensaje markdown para el bot
                            final_message = f"![Imagen]({image_url})"
                        else:
                            logger.error(f"Error descargando imagen desde URL directa: {img_response.status_code}")
                            return
                except Exception as e:
                    logger.error(f"Error procesando imagen de Messenger con URL directa: {e}", exc_info=True)
                    return
            elif message.get("media_id"):
                # Descargar la imagen desde la API de Facebook (método anterior)
                logger.info(f"Procesando imagen de Messenger: {message.get('media_id')}")
                try:
                    # Obtener access_token de la página
                    pages = config.get("pages", [])
                    if isinstance(pages, str):
                        try:
                            pages = json.loads(pages)
                        except json.JSONDecodeError:
                            logger.error(f"Error parseando pages como JSON: {pages}")
                            return
                    page_config = next((page for page in pages if page.get("id") == source_id), None)
                    if not page_config:
                        logger.error(f"No se encontró configuración de página para page_id: {source_id}")
                        return
                    access_token = page_config.get("access_token")
                    if not access_token:
                        logger.error("Falta access_token en la configuración de la página")
                        return
                    # Obtener la URL de la imagen
                    url = f"https://graph.facebook.com/v22.0/{message['media_id']}?fields=images&access_token={access_token}"
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(url)
                        if response.status_code == 200:
                            data = response.json()
                            image_src = data.get("images", [{}])[0].get("source")
                            if not image_src:
                                logger.error("No se pudo obtener la URL de la imagen desde la API de Facebook")
                                return
                            # Descargar la imagen
                            img_response = await client.get(image_src)
                            if img_response.status_code == 200:
                                import os
                                from datetime import datetime
                                from fastapi import UploadFile
                                from io import BytesIO
                                # Crear directorio temporal si no existe
                                temp_dir = os.path.join(os.getcwd(), "temp_images")
                                if not os.path.exists(temp_dir):
                                    os.makedirs(temp_dir)
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                temp_filename = f"messenger_{user_id}_{timestamp}.jpg"
                                temp_filepath = os.path.join(temp_dir, temp_filename)
                                with open(temp_filepath, "wb") as f:
                                    f.write(img_response.content)
                                logger.info(f"Imagen guardada temporalmente: {temp_filepath} ({len(img_response.content)} bytes)")
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
                                logger.info(f"Imagen guardada en Supabase: {image_url}")
                                try:
                                    os.remove(temp_filepath)
                                    logger.debug(f"Archivo temporal eliminado: {temp_filepath}")
                                except Exception as cleanup_error:
                                    logger.warning(f"Error eliminando archivo temporal: {cleanup_error}")
                                # Construir mensaje markdown para el bot
                                final_message = f"![Imagen]({image_url})"
                            else:
                                logger.error(f"Error descargando imagen de Facebook: {img_response.status_code}")
                                return
                        else:
                            logger.error(f"Error obteniendo info de imagen de Facebook: {response.status_code} - {response.text}")
                            return
                except Exception as e:
                    logger.error(f"Error procesando imagen de Messenger: {e}", exc_info=True)
                    return
            else:
                logger.error("Imagen sin URL ni media_id")
                return
        elif message["type"] == "text":
            final_message = message["text"]
        else:
            logger.info(f"Tipo de mensaje no soportado: {message['type']}")
            return
        # Crear el objeto ChatRequest
        chat_request = ChatRequest(
            message=final_message,
            project_id=project_id,
            user_id=user_id,
            name=user_id,  # Usamos el user_id como nombre por defecto
            source="messenger",
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
        # Enviar la respuesta de vuelta a Messenger
        logger.info(f"Enviando respuesta a Messenger para user_id: {user_id}")
        await send_messenger_message(project_id, user_id, response_data["response"], source_id)
        logger.info(f"Mensaje procesado de {user_id} y respuesta enviada")
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}", exc_info=True)

async def send_messenger_message(project_id: str, recipient_id: str, message_text: str, page_id: str):
    """
    Envía un mensaje a través de Messenger.
    
    Args:
        project_id: ID del proyecto
        recipient_id: ID del destinatario
        message_text: Texto del mensaje
        page_id: ID de la página asociada
    """
    try:
        logger.info(f"Iniciando envío de mensaje. Project_id: {project_id}, Recipient_id: {recipient_id}, Page_id: {page_id}")
        
        # Obtener la configuración de Messenger
        db = SupabaseDatabase()
        logger.info(f"Buscando configuración para project_id: {project_id}")
        configs = db.find(TABLE_INTEGRATION, {
            "project_id": project_id, 
            "integration_type": "messenger"
        })
        
        # Buscar la configuración que tenga el page_id en su array pages
        config = None
        for cfg in configs:
            pages = cfg.get("pages", [])
            # Si pages es una cadena, intentar parsearla como JSON
            if isinstance(pages, str):
                try:
                    pages = json.loads(pages)
                except json.JSONDecodeError:
                    logger.error(f"Error parseando pages como JSON: {pages}")
                    continue
            
            if any(page.get("id") == page_id for page in pages):
                config = cfg
                break
        
        if not config:
            logger.error(f"No se encontró configuración de Messenger para project_id: {project_id}, page_id: {page_id}")
            return
        
        logger.info(f"Configuración encontrada: {json.dumps(config, indent=2)}")
        
        # Obtener el access_token del array pages
        pages = config.get("pages", [])
        # Si pages es una cadena, intentar parsearla como JSON
        if isinstance(pages, str):
            try:
                pages = json.loads(pages)
            except json.JSONDecodeError:
                logger.error(f"Error parseando pages como JSON: {pages}")
                return
        
        page_config = next((page for page in pages if page.get("id") == page_id), None)
        if not page_config:
            logger.error(f"No se encontró configuración de página para page_id: {page_id}")
            return
            
        access_token = page_config.get("access_token")
        if not access_token:
            logger.error("Falta access_token en la configuración de la página")
            return
        
        # Enviar mensaje usando la API de Messenger
        url = f"https://graph.facebook.com/v22.0/{page_id}/messages"
        logger.info(f"URL de API: {url}")
        
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "text": message_text
            },
            "messaging_type": "RESPONSE",
            "access_token": access_token
        }
        
        logger.info(f"Enviando datos a Messenger: {json.dumps(data, indent=2)}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            logger.info(f"Respuesta de Messenger API: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code != 200:
                error_data = response.json()
                logger.error(f"Error enviando mensaje de Messenger: {error_data}")
                if error_data.get("error", {}).get("code") == 190:
                    logger.error("El token de acceso ha expirado o es inválido")
                return
            
            logger.info(f"Mensaje enviado exitosamente a {recipient_id}")
    except Exception as e:
        logger.error(f"Error enviando mensaje de Messenger: {e}", exc_info=True)
