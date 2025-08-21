import json
import asyncio
from app.resources.constants import STATUS_BAD_REQUEST
from app.resources.validations import (
    ValidationException,
    validate_json_body,
    validate_required_body_param,
)
from fastapi import HTTPException, Request, BackgroundTasks, UploadFile, Form, Depends
from fastapi.responses import JSONResponse
from .core.graph import Graph
import logging
from .store.file_storage import FileStorage
from bson import ObjectId
from app.controler.chat.store.persistence import Persist
from datetime import datetime

logger = logging.getLogger(__name__)

# 🔒 CONTROL DE CONCURRENCIA - Diccionario para rastrear conversaciones activas
active_conversations = {}
conversation_lock = asyncio.Lock()




async def acquire_conversation_lock(user_id: str, project_id: str) -> bool:
    """
    Adquiere un lock para el usuario. Retorna True si puede procesar, False si ya está procesando.
    """
    async with conversation_lock:
        conversation_key = f"{project_id}_{user_id}"
        
        if conversation_key in active_conversations:
            logger.warning(f"⚠️ Usuario {user_id} ya tiene una conversación activa en proyecto {project_id}")
            return False
        
        active_conversations[conversation_key] = True
        logger.info(f"🔓 Lock adquirido para usuario {user_id} en proyecto {project_id}")
        return True

async def release_conversation_lock(user_id: str, project_id: str):
    """
    Libera el lock del usuario.
    """
    async with conversation_lock:
        conversation_key = f"{project_id}_{user_id}"
        
        if conversation_key in active_conversations:
            del active_conversations[conversation_key]
            logger.info(f"🔓 Lock liberado para usuario {user_id} en proyecto {project_id}")

async def chat(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = None
):
    """
    Endpoint unificado para chat que maneja tanto mensajes normales como mensajes con imágenes.
    ✅ MEJORADO: Conserva mensajes adicionales en cola en lugar de rechazarlos.
    """
    try:
        # Parsear el FormData
        form_data = await request.form()
        
        # Obtener los campos requeridos
        message = form_data.get("message", "")
        project_id = form_data.get("project_id")
        user_id = form_data.get("user_id")
        
        # Validar campos requeridos
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id es requerido")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id es requerido")
        
        # Obtener campos opcionales
        name = form_data.get("name", "no name")
        number_phone_agent = form_data.get("number_phone_agent", "no number")
        source_id = form_data.get("source_id", "default")
        source = form_data.get("source", "default")

        logger.info(f"Recibiendo mensaje - project_id: {project_id}, user_id: {user_id}")

        # 🔒 CONTROL DE CONCURRENCIA - Verificar si el usuario ya tiene una conversación activa
        can_process = await acquire_conversation_lock(user_id, project_id)
        
        if not can_process:
            return JSONResponse(
                status_code=429,
                content={
                    "response": "⏳ Estoy procesando tu mensaje anterior. Por favor espera un momento.",
                    "status": "processing",
                    "message": "Conversación en progreso"
                }
            )
            
        try:
            # Si hay una imagen, procesarla
            image_url = None
            if image:
                if not image.content_type.startswith('image/'):
                    raise HTTPException(
                        status_code=400,
                        detail="El archivo debe ser una imagen"
                    )
                
                # Guardar imagen en Supabase
                file_storage = FileStorage()
                image_url = await file_storage.save_image(project_id, image)

            # Obtener proyecto y unique_id
            unique_id = str(ObjectId())
            database = Persist()
            
            try:
                project = database.find_project(project_id)
                logger.info(f"Proyecto encontrado: {project_id}")
            except ValueError as e:
                logger.error(f"Project not found: {project_id}")
                raise HTTPException(status_code=404, detail="Project not found")
            except Exception as e:
                logger.error(f"Error fetching project: {str(e)}")
                raise HTTPException(status_code=500, detail="Internal server error")

            # Procesar chat
            graph = await Graph.create(
                project_id=project_id,
                user_id=user_id,
                name=name,
                number_phone_agent=number_phone_agent,
                source=source,
                source_id=source_id,
                unique_id=unique_id,
                project=project
            )

            # Construir el mensaje final
            final_message = message
            if image_url:
                if message:
                    final_message = f"{message}\n\n![Imagen]({image_url})"
                else:
                    final_message = f"![Imagen]({image_url})"

            response = await graph.execute(final_message)
            
            # NO enviar la imagen de vuelta al usuario
            # La imagen se usa solo para procesamiento interno

            return JSONResponse(status_code=200, content=response)

        finally:
            # 🔓 SIEMPRE liberar el lock, incluso si hay error
            await release_conversation_lock(user_id, project_id)

    except HTTPException as e:
        # Liberar lock en caso de error HTTP
        if 'user_id' in locals() and 'project_id' in locals():
            await release_conversation_lock(user_id, project_id)
        raise e
    except Exception as e:
        # Liberar lock en caso de error general
        if 'user_id' in locals() and 'project_id' in locals():
            await release_conversation_lock(user_id, project_id)
        logger.error(f"Error en chat: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando mensaje: {str(e)}"
        )


