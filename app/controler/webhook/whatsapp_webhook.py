import logging
import json
import os
from typing import Dict, Any, List
from fastapi import Request, HTTPException
from fastapi.responses import PlainTextResponse
from app.resources.constants import STATUS_BAD_REQUEST
from app.controler.chat.core.graph import Graph
from app.resources.postgresql import SupabaseDatabase
import httpx

logger = logging.getLogger("root")

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

async def process_webhook_whatsapp(request: Request) -> Dict[str, Any]:
    """
    Procesa los eventos entrantes del webhook de WhatsApp.
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
            await process_message(message)

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
                        "entry_id": entry.get("id")
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
                        "entry_id": entry.get("id")
                    })
    except Exception as e:
        logger.error(f"Error extrayendo mensajes: {e}")
    
    return messages

async def process_message(message: Dict[str, Any]):
    """
    Procesa un mensaje individual de WhatsApp.
    """
    try:
        logger.info(f"Iniciando procesamiento de mensaje: {json.dumps(message, indent=2)}")
        
        # Por ahora solo procesamos mensajes de texto
        if message["type"] != "text":
            logger.info(f"Omitiendo mensaje no textual de tipo: {message['type']}")
            return
        
        # Obtener el ID del proyecto asociado con este número de WhatsApp
        db = SupabaseDatabase()
        logger.info(f"Buscando configuración para phone_number_id: {message['phone_number_id']}")
        
        # Buscar la configuración activa de WhatsApp
        configs = db.find("meta_configs", {
            "integration_type": "whatsapp",
            "whatsapp_account_id": message["entry_id"],
            "active": True
        }, limit=1)
        
        # Obtener la primera configuración si existe
        config = configs[0] if configs else None
        
        if not config:
            logger.warning(f"No se encontró configuración activa de WhatsApp para entry_id: {message['entry_id']}")
            return
        
        logger.info(f"Configuración encontrada: {json.dumps(config, indent=2)}")
        project_id = config.get("project_id")
        
        # Crear una instancia de Graph y procesar el mensaje
        user_id = message["from_number"]
        text_message = message["text"]
        
        logger.info(f"Creando instancia de Graph con project_id: {project_id}, user_id: {user_id}")
        graph = Graph(project_id, user_id, "WhatsApp User", user_id, "whatsapp")
        response = await graph.execute(text_message)
        logger.info(f"Respuesta de Graph: {json.dumps(response, indent=2)}")
        
        # Enviar la respuesta de vuelta a WhatsApp
        logger.info(f"Enviando respuesta a WhatsApp para user_id: {user_id}")
        await send_whatsapp_message(project_id, user_id, response["response"], message["phone_number_id"])
        
        logger.info(f"Mensaje procesado de {user_id} y respuesta enviada")
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}", exc_info=True)

async def send_whatsapp_message(project_id: str, recipient_id: str, message_text: str, phone_number_id: str):
    """
    Envía un mensaje a través de WhatsApp.
    """
    try:
        logger.info(f"Iniciando envío de mensaje. Project_id: {project_id}, Recipient_id: {recipient_id}, Phone_number_id: {phone_number_id}")
        
        # Obtener la configuración de WhatsApp
        db = SupabaseDatabase()
        logger.info(f"Buscando configuración para project_id: {project_id}")
        configs = db.find("meta_configs", {
            "project_id": project_id, 
            "integration_type": "whatsapp"
        })
        
        # Buscar la configuración que tenga el phone_number_id en su array pages
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
            
            if any(page.get("id") == phone_number_id for page in pages):
                config = cfg
                break
        
        if not config:
            logger.error(f"No se encontró configuración de WhatsApp para project_id: {project_id}, phone_number_id: {phone_number_id}")
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
        
        page_config = next((page for page in pages if page.get("id") == phone_number_id), None)
        if not page_config:
            logger.error(f"No se encontró configuración de página para phone_number_id: {phone_number_id}")
            return
            
        access_token = page_config.get("access_token")
        if not access_token:
            logger.error("Falta access_token en la configuración de la página")
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
