import json
import asyncio
from app.resources.constants import STATUS_BAD_REQUEST
from app.resources.validations import (
    ValidationException,
    validate_json_body,
    validate_required_body_param,
)
from fastapi import HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from .core.graph import Graph


async def chat(request: Request, background_tasks: BackgroundTasks):
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

    graph = Graph(project_id, user_id, name, number_phone_agent, source_id, source)
    response = await graph.execute(message, background_tasks)
    return JSONResponse(status_code=200, content=response)


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

    graph = Graph(project_id, user_id, name, number_phone_agent, source_id, source)
    
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
