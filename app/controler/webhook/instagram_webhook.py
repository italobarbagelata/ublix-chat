
import logging
import json
import os
import httpx
from typing import Dict, Any, List, Optional
from fastapi import Request
from dotenv import load_dotenv
from app.controler.chat.store.persistence import SupabaseDatabase
from app.controler.chat.core.graph import Graph
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
async def process_instagram_message(message: Dict[str, Any]):
    """Procesa un mensaje de Instagram y envía respuesta a través del adapter."""
    try:
        logger.info(f"Iniciando procesamiento de mensaje: {json.dumps(message, indent=2)}")
        recipient_id = message.get("recipient_id")
        sender_id = message.get("sender_id")
        text_message = message.get("text")
        message_type = message.get("type")
        
        if message_type != "text" or not recipient_id or not sender_id or not text_message:
            logger.warning(f"Mensaje IG omitido - Tipo: {message_type}, Recipient: {recipient_id}, Sender: {sender_id}, Texto: {text_message}")
            return
        
        logger.info(f"Buscando project_id para el mensaje")
        project_id = await get_project_id_for_instagram(recipient_id, sender_id)
        if not project_id:
            logger.warning(f"No se encontró proyecto para IG Recipient ID: {recipient_id}")
            db = SupabaseDatabase()
            instagram_configs = db.select(INSTAGRAM_COLLECTION, {"instagram_page_id": None})
            logger.info(f"Instagram configs: {json.dumps(instagram_configs, indent=2)}")
            for instagram_config in instagram_configs:
                token = instagram_config.get("user_access_token")
                page_data = await get_instagram_user_info(instagram_id=recipient_id,access_token=token)
                logger.info(f"Page data: {json.dumps(page_data, indent=2)}")
                if page_data:
                    db.update(INSTAGRAM_COLLECTION, {"instagram_page_id": page_data.get("id")}, {"project_id": instagram_config.get("project_id")})
                    break

        # Inicializar el adaptador de Instagram para obtener información del usuario
        instagram_adapter = InstagramAdapter(project_id, recipient_id)
        
        # Obtener información detallada del usuario de Instagram
        logger.info(f"Obteniendo información detallada del usuario: {sender_id}")
        
        #obtener el username y el user_id del usuario de instagram
        user = await get_instagram_user_info(instagram_id=sender_id,access_token=token)
        logger.info(f"User: {json.dumps(user, indent=2)}")
        username = "Instagram User"
        user_id = sender_id
      
            
        # Procesar mensaje con Graph
        logger.info(f"Procesando mensaje con Graph para project_id: {project_id} y user_id: {user_id}")
        graph = Graph(project_id, user_id, username, "no igsid", "instagram")
        response = await graph.execute(text_message)
        logger.info(f"Respuesta de Graph: {json.dumps(response, indent=2)}")

        # Enviar respuesta usando InstagramAdapter
        logger.info(f"Enviando respuesta a través de InstagramAdapter")
        api_response = await instagram_adapter.send_message(sender_id, response["response"])
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
async def process_webhook_instagram(request: Request) -> Dict[str, Any]:
    """Procesa los mensajes de webhook entrantes de Instagram."""
    try:
        logger.info("Iniciando procesamiento de webhook de Instagram")
        body = await request.json()
        logger.info(f"Webhook recibido: {json.dumps(body, indent=2)}")
        
        # Guardar el webhook para referencia
        await save_webhook_to_file(body)
        
            
        extracted_msgs = extract_instagram_messages(body)
        logger.info(f"Se extrajeron {len(extracted_msgs)} mensajes del webhook")
        
        recipient_id = extracted_msgs[0].get("recipient_id")
        logger.info(f"Recipient ID: {recipient_id}")
        
        
        processed_count = 0
        for msg in extracted_msgs:
            try:
                #logger.info(f"Procesando mensaje: {json.dumps(msg, indent=2)}")
                await process_instagram_message(msg)
                processed_count += 1
                #logger.info(f"Mensaje procesado exitosamente. Total procesados: {processed_count}")
            except Exception as msg_err:
                logger.error(f"Error procesando mensaje: {msg_err}", exc_info=True)
                
        logger.info(f"Procesamiento completado. Mensajes procesados: {processed_count}/{len(extracted_msgs)}")
        return {"status": "ok", "processed": processed_count, "total": len(extracted_msgs)}
        
    except Exception as e:
        logger.error(f"Error procesando webhook de Instagram: {e}", exc_info=True)
        return {"status": "error", "detail": "Internal server error processing webhook"}
