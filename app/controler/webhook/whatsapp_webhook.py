import logging
import json
import os
from typing import Dict, Any, List
from fastapi import Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from app.resources.constants import STATUS_BAD_REQUEST
from app.controler.chat.core.graph import Graph
from app.resources.postgresql import SupabaseDatabase
import httpx
from app.models import ChatRequest
from app.chatbot import chatbot

logger = logging.getLogger("root")

TABLE_INTEGRATION = "integration_whatsapp"

async def verify_webhook_whatsapp(request: Request):
    """
    Verifica la suscripción del webhook de WhatsApp enviada por Meta.
    """
    params = request.query_params

    # Obtener el token de verificación desde las variables de entorno
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if not verify_token:
        logger.error("WHATSAPP_VERIFY_TOKEN no está configurado en las variables de entorno")
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

async def process_webhook_whatsapp(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Procesa los eventos entrantes del webhook de WhatsApp.
    
    Args:
        request: El objeto Request de FastAPI
        background_tasks: Tareas en segundo plano de FastAPI
    """
    # Log inicial para verificar si la función se está ejecutando para POST
    logger.info(f"Recibida solicitud {request} en /api/whatsapp/webhook")
    try:
        # Verificar si es un método POST antes de intentar leer el body
        if request.method != "POST":
            logger.warning(f"Método no permitido: {request.method}")
            raise HTTPException(status_code=405, detail="Method Not Allowed")

        body = await request.json()
        logger.info(f"Webhook recibido: {json.dumps(body, indent=2)}")

        # Verificar si es un mensaje válido de WhatsApp
        if not is_valid_whatsapp_message(body):
            logger.info("No es un mensaje válido de WhatsApp o no contiene cambios procesables.")
            return {"status": "ok"}

        # Extraer mensajes del webhook
        messages = extract_messages(body)
        if not messages:
            logger.info("No se extrajeron mensajes del webhook.")
            return {"status": "ok"}

        logger.info(f"Mensajes extraídos: {json.dumps(messages, indent=2)}")

        for message in messages:
            # Procesar cada mensaje
            logger.info(f"Procesando mensaje: {json.dumps(message, indent=2)}")
            await process_message(message, background_tasks)

        return {"status": "ok"}
    except json.JSONDecodeError:
        logger.error("Error al decodificar JSON del cuerpo de la solicitud POST")
        # Leer el cuerpo como texto para inspección si falla el JSON
        try:
            raw_body = await request.body()
            logger.info(f"Cuerpo crudo recibido (no JSON válido): {raw_body.decode()}")
        except Exception as read_err:
            logger.error(f"No se pudo leer el cuerpo crudo de la solicitud: {read_err}")
        raise HTTPException(status_code=STATUS_BAD_REQUEST, detail="Cuerpo de solicitud no es JSON válido")
    except Exception as e:
        logger.error(f"Error procesando webhook: {e}", exc_info=True)
        raise HTTPException(status_code=STATUS_BAD_REQUEST, detail=str(e))

def is_valid_whatsapp_message(body: Dict[str, Any]) -> bool:
    """
    Verifica si el webhook contiene un mensaje válido de WhatsApp
    con cambios procesables (como mensajes).
    """
    logger.info(f"Validando mensaje de WhatsApp. Object: {body.get('object')}, Entry: {bool(body.get('entry'))}")
    if not (
        body.get("object") == "whatsapp_business_account" and
        body.get("entry") and
        isinstance(body["entry"], list) and
        len(body["entry"]) > 0
    ):
        logger.info("Validación fallida: 'object' no es 'whatsapp_business_account' o 'entry' está ausente/vacío.")
        return False

    # Verificar si hay 'changes' y si contienen 'messages' o 'statuses' (podrías querer manejar statuses también)
    try:
        change = body["entry"][0].get("changes", [{}])[0]
        value = change.get("value", {})
        if "messages" in value or "statuses" in value:
             logger.info("Validación exitosa: Se encontraron 'messages' o 'statuses' en 'changes'.")
             return True
        else:
            logger.info("Validación fallida: No se encontraron 'messages' ni 'statuses' en 'value'.")
            # Loguear qué contenía 'value' para depuración
            logger.debug(f"Contenido de 'value': {json.dumps(value)}")
            return False
    except (IndexError, KeyError, TypeError) as e:
        logger.warning(f"Error estructural al validar el mensaje: {e}. Body: {json.dumps(body)}")
        return False

def extract_messages(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrae mensajes del cuerpo del webhook de WhatsApp.
    """
    messages = []
    
    try:
        entry = body["entry"][0]
        entry_id = entry["id"]  # Obtener el ID de la entrada
        change = entry["changes"][0]
        value = change.get("value", {})
        
        if "messages" in value:
            for message in value["messages"]:
                # Obtener el ID del remitente y el ID del número de WhatsApp
                from_number = message.get("from")
                phone_number_id = value.get("metadata", {}).get("phone_number_id")
                
                # Extraer el mensaje según su tipo
                message_type = message.get("type", "text")
                
                if message_type == "text":
                    messages.append({
                        "from_number": from_number,
                        "phone_number_id": phone_number_id,
                        "type": message_type,
                        "text": message.get("text", {}).get("body", ""),
                        "timestamp": message.get("timestamp"),
                        "message_id": message.get("id"),
                        "entry_id": entry_id  # Usar el entry_id extraído
                    })
                elif message_type in ["image", "audio", "document", "video"]:
                    # Manejar mensajes multimedia
                    messages.append({
                        "from_number": from_number,
                        "phone_number_id": phone_number_id,
                        "type": message_type,
                        "media_id": message.get(message_type, {}).get("id"),
                        "timestamp": message.get("timestamp"),
                        "message_id": message.get("id"),
                        "entry_id": entry_id  # Usar el entry_id extraído
                    })
    except Exception as e:
        logger.error(f"Error extrayendo mensajes: {e}")
    
    return messages

async def process_message(message: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Procesa un mensaje individual de WhatsApp.
    
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
        
        # Obtener el ID del proyecto asociado con este número de WhatsApp
        db = SupabaseDatabase()
        logger.info(f"Buscando configuración para phone_number_id: {message['phone_number_id']}")
        
        # Buscar la configuración activa de WhatsApp
        configs = db.select(TABLE_INTEGRATION, {
            "business_account_id": message["entry_id"],
            "active": True
        }, limit=1)
        
        # Obtener la primera configuración si existe
        config = configs[0] if configs else None
        
        if not config:
            logger.warning(f"No se encontró configuración activa de WhatsApp para entry_id: {message['entry_id']}")
            return
        
        logger.info(f"Configuración encontrada: {json.dumps(config, indent=2)}")
        project_id = config.get("project_id")

        # Verificar si el bot está desactivado para este usuario
        conversation_state = db.find_one("whatsapp_conversation_states", {
            "project_id": project_id,
            "business_account_id": message["entry_id"],
            "phone_number_id": message["phone_number_id"],
            "user_id": message["from_number"]
        })
        
        if not conversation_state:
            # Si no existe el registro, crear uno nuevo con el bot activado
            conversation_state = {
                "project_id": project_id,
                "business_account_id": message["entry_id"],
                "phone_number_id": message["phone_number_id"],
                "user_id": message["from_number"],
                "bot_active": True
            }
            db.insert("whatsapp_conversation_states", conversation_state)
            logger.info("Nuevo estado de conversación de WhatsApp creado con bot activado")
        elif not conversation_state.get("bot_active", True):
            logger.info("Bot desactivado para este usuario de WhatsApp - omitiendo procesamiento")
            return
        
        user_id = message["from_number"]
        source_id = message["phone_number_id"]
        final_message = None
        image_url = None
        
        if message["type"] == "image" and message.get("media_id"):
            # Descargar la imagen desde la API de WhatsApp
            logger.info(f"Procesando imagen de WhatsApp: {message.get('media_id')}")
            try:
                access_token = config.get("access_token")
                if not access_token:
                    logger.error("Falta access_token en la configuración")
                    return
                # Obtener la URL de la imagen
                url = f"https://graph.facebook.com/v22.0/{message['media_id']}?access_token={access_token}"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        image_src = data.get("url")
                        if not image_src:
                            logger.error("No se pudo obtener la URL de la imagen desde la API de WhatsApp")
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
                            temp_filename = f"whatsapp_{user_id}_{timestamp}.jpg"
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
                            logger.error(f"Error descargando imagen de WhatsApp: {img_response.status_code}")
                            return
                    else:
                        logger.error(f"Error obteniendo info de imagen de WhatsApp: {response.status_code} - {response.text}")
                        return
            except Exception as e:
                logger.error(f"Error procesando imagen de WhatsApp: {e}", exc_info=True)
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
            name=user_id,  # Usamos el número como nombre por defecto
            source="whatsapp",
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
        
        # Enviar la respuesta de vuelta a WhatsApp
        logger.info(f"Enviando respuesta a WhatsApp para user_id: {user_id}")
        await send_whatsapp_message(project_id, user_id, message["entry_id"], response_data["response"], source_id)
        
        logger.info(f"Mensaje procesado de {user_id} y respuesta enviada")
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}", exc_info=True)

async def send_whatsapp_message(project_id: str, recipient_id: str, entry_id: str, message_text: str, phone_number_id: str):
    """
    Envía un mensaje a través de WhatsApp.
    """
    try:
        logger.info(f"Iniciando envío de mensaje. Project_id: {project_id}, Recipient_id: {recipient_id}, Phone_number_id: {phone_number_id}")
        
        # Obtener la configuración de WhatsApp
        db = SupabaseDatabase()
        logger.info(f"Buscando configuración para project_id: {project_id}")
        configs = db.select(TABLE_INTEGRATION, {
            "project_id": project_id,
            "business_account_id": entry_id,
            "active": True,
        }, limit=1)
        
        logger.info(f"Configuraciones encontradas: {configs}")
        
        if not configs:
            logger.error("No se encontró configuración de WhatsApp")
            return
            
        config = configs[0]  # Tomar la primera configuración
        access_token = config.get("access_token")
        if not access_token:
            logger.error("Falta access_token en la configuración")
            return
        
        # Enviar mensaje usando la API de WhatsApp
        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        logger.info(f"URL de API: {url}")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_id,
            "type": "text",
            "text": {
                "body": message_text
            }
        }
        
        logger.info(f"Enviando datos a WhatsApp: {json.dumps(data, indent=2)}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            logger.info(f"Respuesta de WhatsApp API: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code != 200:
                error_data = response.json()
                logger.error(f"Error enviando mensaje de WhatsApp: {error_data}")
                if error_data.get("error", {}).get("code") == 190:
                    logger.error("El token de acceso ha expirado o es inválido")
                return
            
            logger.info(f"Mensaje enviado exitosamente a {recipient_id}")
    except Exception as e:
        logger.error(f"Error enviando mensaje de WhatsApp: {e}", exc_info=True)
