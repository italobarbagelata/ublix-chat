import logging
import json
import asyncio
from fastapi import Request, BackgroundTasks, HTTPException
from fastapi.exceptions import ValidationException
from fastapi.responses import JSONResponse, StreamingResponse

from bson import ObjectId
from pydantic import BaseModel
from app.controler.chat.core.graph import Graph   
from dotenv import load_dotenv
from app.controler.chat.store.persistence import Persist



load_dotenv()


class ChatRequest(BaseModel):
    message: str
    project_id: str
    user_id: str
    name: str = "no name"
    source: str = ""
    source_id: str = ""
    number_phone_agent: str = "no number"
    debug: bool = False


async def chatbot(request: ChatRequest):
    unique_id = str(ObjectId())

    database = Persist()
    
    try:
        project = database.find_project(request.project_id)
    except ValueError as e:
        logging.error("Project not found: %s", request.project_id)
        return JSONResponse(status_code=404, content={"error": "Project not found"})
    except Exception as e:
        logging.error("Error fetching project: %s", str(e))
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    graph = await Graph.create(request.project_id, request.user_id, request.name, request.number_phone_agent, request.source, request.source_id, unique_id, project)
    response = await graph.execute(request.message, request.debug)

    return JSONResponse(status_code=200, content=response)


async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    🆕 NUEVO: Endpoint de streaming para respuestas en tiempo real
    ✅ Mantiene todas las validaciones y estructura existente
    """
    try:
        logging.info(request)
        name = request.name
        number_phone_agent = request.number_phone_agent
        source_id = request.source
        project_id = request.project_id
        user_id = request.user_id
        message = request.message

    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))

    unique_id = str(ObjectId())
    database = Persist()
    
    try:
        project = database.find_project(project_id)
    except ValueError as e:
        logging.error("Project not found: %s", project_id)
        return JSONResponse(status_code=404, content={"error": "Project not found"})
    except Exception as e:
        logging.error("Error fetching project: %s", str(e))
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    graph = await Graph.create(project_id, user_id, name, number_phone_agent, source_id, request.source_id, unique_id, project)
    
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
