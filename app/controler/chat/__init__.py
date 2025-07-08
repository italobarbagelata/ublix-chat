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
from .core.message_queue import MessageQueue, QueuedMessage
import logging
from .store.file_storage import FileStorage
from bson import ObjectId
from app.controler.chat.store.persistence import Persist
from datetime import datetime

logger = logging.getLogger(__name__)

# 🔒 CONTROL DE CONCURRENCIA - Diccionario para rastrear conversaciones activas
active_conversations = {}
conversation_lock = asyncio.Lock()

# 📬 SISTEMA DE COLAS - Instancia global para conservar mensajes
message_queue = MessageQueue(max_queue_size=100)

# 🧠 CONTEXTO ACUMULADO - Mantener el contexto de mensajes encolados por usuario
user_accumulated_context = {}
context_lock = asyncio.Lock()

async def add_to_accumulated_context(user_id: str, project_id: str, message: str):
    """Añade un mensaje al contexto acumulado del usuario"""
    async with context_lock:
        context_key = f"{project_id}_{user_id}"
        if context_key not in user_accumulated_context:
            user_accumulated_context[context_key] = []
        
        user_accumulated_context[context_key].append({
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Limitar el contexto acumulado a los últimos 10 mensajes para evitar sobrecarga
        if len(user_accumulated_context[context_key]) > 10:
            user_accumulated_context[context_key] = user_accumulated_context[context_key][-10:]
        
        logger.info(f"📝 Añadido al contexto acumulado para {user_id}: {len(user_accumulated_context[context_key])} mensajes")

async def get_and_clear_accumulated_context(user_id: str, project_id: str) -> list:
    """Obtiene y limpia el contexto acumulado del usuario"""
    async with context_lock:
        context_key = f"{project_id}_{user_id}"
        accumulated = user_accumulated_context.get(context_key, [])
        if context_key in user_accumulated_context:
            del user_accumulated_context[context_key]
        return accumulated

async def process_chat_message(message: QueuedMessage) -> dict:
    """Handler para procesar mensajes de chat desde la cola"""
    try:
        # Obtener contexto acumulado si existe
        accumulated_context = await get_and_clear_accumulated_context(
            message.user_id, 
            message.project_id
        )
        
        # Construir mensaje final con contexto acumulado
        final_message = message.content
        if accumulated_context:
            context_messages = []
            for ctx in accumulated_context:
                context_messages.append(f"[{ctx['timestamp']}] {ctx['message']}")
            
            final_message = f"""Mensaje principal: {message.content}

Mensajes adicionales recibidos mientras procesaba:
{chr(10).join(context_messages)}

Por favor responde considerando toda esta información."""
            
            logger.info(f"📨 Procesando mensaje con contexto acumulado: {len(accumulated_context)} mensajes adicionales")
        
        # Obtener metadatos del mensaje
        metadata = message.metadata
        background_tasks = metadata.get('background_tasks')
        
        # Procesar con el sistema actual
        graph = await Graph.create(
            project_id=message.project_id,
            user_id=message.user_id,
            name=metadata.get('name', 'no name'),
            number_phone_agent=metadata.get('number_phone_agent', 'no number'),
            source=metadata.get('source', 'default'),
            source_id=metadata.get('source_id', 'default'),
            unique_id=metadata.get('unique_id', str(ObjectId())),
            project=metadata.get('project')
        )
        
        response = await graph.execute_with_immediate_response(final_message, background_tasks)
        
        # Añadir información sobre mensajes procesados
        if accumulated_context:
            response['messages_processed'] = len(accumulated_context) + 1
            response['includes_queued_messages'] = True
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Error procesando mensaje desde cola: {str(e)}")
        raise e

# Registrar el handler para mensajes de chat
message_queue.register_handler("chat", process_chat_message)

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
            # 📬 CONSERVAR MENSAJE: En lugar de rechazar, encolar para procesamiento posterior
            try:
                # Procesar imagen si existe
                image_url = None
                if image:
                    if not image.content_type.startswith('image/'):
                        raise HTTPException(
                            status_code=400,
                            detail="El archivo debe ser una imagen"
                        )
                    file_storage = FileStorage()
                    image_url = await file_storage.save_image(project_id, image)
                
                # Construir mensaje final
                final_message = message
                if image_url:
                    if message:
                        final_message = f"{message}\n\n![Imagen]({image_url})"
                    else:
                        final_message = f"![Imagen]({image_url})"
                
                # Añadir al contexto acumulado
                await add_to_accumulated_context(user_id, project_id, final_message)
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "response": "Recibido, dame un momento...",
                        "status": "queued",
                        "message": "Mensaje conservado en contexto",
                        "queued_message": True,
                        "will_be_processed": True
                    }
                )
                
            except Exception as e:
                logger.error(f"❌ Error conservando mensaje: {str(e)}")
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

            response = await graph.execute_with_immediate_response(final_message, background_tasks)
            
            # Si hubo imagen, agregar su URL a la respuesta
            if image_url:
                response['image_url'] = image_url
                # Asegurarnos de que el content contenga tanto el mensaje como la imagen
                if 'content' in response:
                    response['content'] = final_message

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

    # 🔒 CONTROL DE CONCURRENCIA - Verificar si el usuario ya tiene una conversación activa
    can_process = await acquire_conversation_lock(user_id, project_id)
    if not can_process:
        # 📬 CONSERVAR MENSAJE: En lugar de rechazar, encolar para procesamiento posterior
        try:
            # Añadir al contexto acumulado
            await add_to_accumulated_context(user_id, project_id, message)
            
            # Para streaming, enviar evento de confirmación
            async def queued_message_generator():
                queued_event = {
                    "type": "queued_message",
                    "message": "Recibido, dame un momento...",
                    "status": "queued",
                    "queued_message": True,
                    "will_be_processed": True,
                    "is_complete": True
                }
                yield f"data: {json.dumps(queued_event, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
            
            return StreamingResponse(
                queued_message_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Error conservando mensaje en streaming: {str(e)}")
            # Fallback al comportamiento anterior
            async def error_generator():
                error_event = {
                    "type": "error",
                    "error": "⏳ Estoy procesando tu mensaje anterior. Por favor espera un momento.",
                    "status": "processing",
                    "is_complete": True
                }
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
            
            return StreamingResponse(
                error_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                }
            )

    try:
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
            finally:
                # 🔓 Liberar el lock cuando termine el streaming
                await release_conversation_lock(user_id, project_id)
            
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
    
    except Exception as e:
        # Liberar lock en caso de error
        await release_conversation_lock(user_id, project_id)
        raise e


async def get_queue_status(request: Request):
    """
    📊 NUEVO: Endpoint para obtener el estado de la cola de un usuario
    """
    try:
        # Obtener parámetros de query
        user_id = request.query_params.get("user_id")
        project_id = request.query_params.get("project_id")
        
        if not user_id or not project_id:
            raise HTTPException(
                status_code=400, 
                detail="user_id y project_id son requeridos"
            )
        
        from app.controler.chat.core.message_queue import message_queue
        
        # Obtener estado de la cola
        queue_status = await message_queue.get_queue_status(user_id, project_id)
        
        # Verificar si hay conversación activa (fuera de cola)
        conversation_key = f"{project_id}_{user_id}"
        is_conversation_active = conversation_key in active_conversations
        
        response = {
            "user_id": user_id,
            "project_id": project_id,
            "queue_status": queue_status,
            "conversation_active": is_conversation_active,
            "timestamp": datetime.now().isoformat()
        }
        
        return JSONResponse(status_code=200, content=response)
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de cola: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo estado de cola: {str(e)}"
        )


async def get_system_stats(request: Request):
    """
    📈 NUEVO: Endpoint para obtener estadísticas del sistema de colas
    """
    try:
        from app.controler.chat.core.message_queue import message_queue
        
        # Obtener estadísticas
        stats = message_queue.get_stats()
        
        # Agregar información adicional
        stats.update({
            "active_conversations": len(active_conversations),
            "concurrent_limit_hit": sum(1 for _ in active_conversations.keys()),
            "timestamp": datetime.now().isoformat()
        })
        
        return JSONResponse(status_code=200, content=stats)
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )


async def cancel_user_queue(request: Request):
    """
    🚫 NUEVO: Endpoint para cancelar mensajes pendientes de un usuario
    """
    try:
        req_body = await validate_json_body(request)
        user_id = await validate_required_body_param(req_body, "user_id")
        project_id = await validate_required_body_param(req_body, "project_id")
        
        from app.controler.chat.core.message_queue import message_queue
        
        # Cancelar mensajes en cola
        cancelled_count = await message_queue.cancel_user_messages(user_id, project_id)
        
        # Liberar lock de conversación si existe
        await release_conversation_lock(user_id, project_id)
        
        response = {
            "user_id": user_id,
            "project_id": project_id,
            "cancelled_messages": cancelled_count,
            "conversation_cleared": True,
            "timestamp": datetime.now().isoformat()
        }
        
        return JSONResponse(status_code=200, content=response)
        
    except ValidationException as e:
        raise HTTPException(status_code=STATUS_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error cancelando cola: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error cancelando cola: {str(e)}"
        )
