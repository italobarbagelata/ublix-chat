import logging
import json
import os
from typing import Dict, Any, List
from fastapi import Request, HTTPException
from fastapi.responses import PlainTextResponse
from app.resources.constants import STATUS_BAD_REQUEST, STATUS_UNAUTHORIZED
from app.controler.chat.core.graph import Graph
from app.resources.postgresql import SupabaseDatabase
import httpx

logger = logging.getLogger("root")

async def verify_webhook(request: Request):
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

async def process_webhook(request: Request) -> Dict[str, Any]:
    """
    Procesa los eventos entrantes del webhook de Messenger.
    
    Args:
        request: El objeto Request de FastAPI
        
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
        logger.info(f"Mensajes extraídos: {json.dumps(messages, indent=2)}")
        
        for message in messages:
            # Procesar cada mensaje
            logger.info(f"Procesando mensaje: {json.dumps(message, indent=2)}")
            await process_message(message)
        
        return {"status": "ok"}
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
            message_type = message.get("type", "text")
            
            if message_type == "text":
                messages.append({
                    "sender_id": sender_id,
                    "page_id": page_id,  # Agregar el page_id al mensaje
                    "type": message_type,
                    "text": message.get("text", ""),
                    "timestamp": messaging.get("timestamp"),
                    "message_id": message.get("mid")
                })
            elif message_type in ["image", "audio", "file", "video"]:
                # Manejar mensajes multimedia
                messages.append({
                    "sender_id": sender_id,
                    "page_id": page_id,  # Agregar el page_id al mensaje
                    "type": message_type,
                    "media_id": message.get(message_type, {}).get("id"),
                    "timestamp": messaging.get("timestamp"),
                    "message_id": message.get("mid")
                })
    except Exception as e:
        logger.error(f"Error extrayendo mensajes: {e}")
    
    return messages

async def process_message(message: Dict[str, Any]):
    """
    Procesa un mensaje individual de Messenger.
    
    Args:
        message: El objeto de mensaje
    """
    try:
        logger.info(f"Iniciando procesamiento de mensaje: {json.dumps(message, indent=2)}")
        
        # Por ahora solo procesamos mensajes de texto
        if message["type"] != "text":
            logger.info(f"Omitiendo mensaje no textual de tipo: {message['type']}")
            return
        
        # Obtener el ID del proyecto asociado con esta página de Facebook
        db = SupabaseDatabase()
        logger.info(f"Buscando configuración para page_id: {message['page_id']}")
        config = db.find_one("meta_configs", {
            "integration_type": "messenger", 
            "active": True,
            "page_id": message["page_id"]
        })
        
        if not config:
            logger.warning(f"No se encontró configuración activa de Messenger para page_id: {message['page_id']}")
            return
        
        logger.info(f"Configuración encontrada: {json.dumps(config, indent=2)}")
        project_id = config.get("project_id")
        
        # Crear una instancia de Graph y procesar el mensaje
        user_id = message["sender_id"]
        text_message = message["text"]
        
        logger.info(f"Creando instancia de Graph con project_id: {project_id}, user_id: {user_id}")
        graph = Graph(project_id, user_id, "Facebook User", "no number", "messenger")
        response = await graph.execute(text_message)
        logger.info(f"Respuesta de Graph: {json.dumps(response, indent=2)}")
        
        # Enviar la respuesta de vuelta a Messenger
        logger.info(f"Enviando respuesta a Messenger para user_id: {user_id}")
        await send_messenger_message(project_id, user_id, response["response"], message["page_id"])
        
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
        logger.info(f"Buscando configuración para project_id: {project_id}, page_id: {page_id}")
        config = db.find_one("meta_configs", {
            "project_id": project_id, 
            "integration_type": "messenger",
            "page_id": page_id
        })
        
        if not config:
            logger.error(f"No se encontró configuración de Messenger para project_id: {project_id}, page_id: {page_id}")
            return
        
        logger.info(f"Configuración encontrada: {json.dumps(config, indent=2)}")
        access_token = config.get("access_token")
        
        if not access_token:
            logger.error("Falta access_token en la configuración")
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
