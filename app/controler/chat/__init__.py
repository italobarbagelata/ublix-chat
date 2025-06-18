import json
import asyncio
from app.resources.constants import STATUS_BAD_REQUEST
from app.resources.validations import (
    ValidationException,
    validate_json_body,
    validate_required_body_param,
)
from fastapi import HTTPException, Request, BackgroundTasks, UploadFile, Form, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from .core.graph import Graph
import logging
from .store.file_storage import FileStorage
from bson import ObjectId
from app.controler.chat.store.persistence import Persist

logger = logging.getLogger(__name__)

async def chat(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = None
):
    """
    Endpoint unificado para chat que maneja tanto mensajes normales como mensajes con imágenes.
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

        response = await graph.execute(final_message, background_tasks)
        
        # Si hubo imagen, agregar su URL a la respuesta
        if image_url:
            response['image_url'] = image_url
            # Asegurarnos de que el content contenga tanto el mensaje como la imagen
            if 'content' in response:
                response['content'] = final_message

        return JSONResponse(status_code=200, content=response)

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error en chat: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando mensaje: {str(e)}"
        )


async def chat_stream(request: Request, background_tasks: BackgroundTasks):
    """
    🆕 NUEVO: Endpoint de streaming para respuestas en tiempo real
    ✅ Mantiene todas las validaciones y estructura existente
    """
    try:
        req_body = await validate_json_body(request)
        message = await validate_required_body_param(req_body, "message")
        project_id = await validate_required_body_param(req_body, "project_id")
        user_id = await validate_required_body_param(req_body, "user_id")

        name = req_body.get("name", "no name")
        number_phone_agent = req_body.get("number_phone_agent", "no number")
        source_id = req_body.get("source", "default")
        source = req_body.get("source_name", "default")

    except ValidationException as e:
        raise HTTPException(status_code=STATUS_BAD_REQUEST, detail=str(e))

    graph = Graph.create(project_id, user_id, name, number_phone_agent, source, source_id)
    
    # Generador para Server-Sent Events 
    async def event_generator():
        try:
            async for chunk in graph.execute_stream(message, background_tasks):
                # Formatear como Server-Sent Event
                event_data = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {event_data}\n\n"
                
                # Pequeña pausa para no saturar
                await asyncio.sleep(0.01)
                
        except Exception as e:
            # Enviar error como evento
            error_event = {
                "type": "error",
                "error": str(e),
                "is_complete": True
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        
        # Evento final de cierre
        yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
    
    # Retornar StreamingResponse con headers apropiados
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )
