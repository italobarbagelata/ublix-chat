from fastapi import HTTPException
from fastapi.exceptions import ValidationException
from fastapi.responses import JSONResponse

from bson import ObjectId
from pydantic import BaseModel
from app.controler.chat.core.graph import Graph   
from dotenv import load_dotenv
from app.controler.chat.store.persistence import Persist
from app.core.logger_config import get_conversation_logger



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
    conv_logger = get_conversation_logger(unique_id, request.user_id)
    
    # Log inicio de conversación
    conv_logger.log_inicio_conversacion(request.message)
    
    database = Persist()
    
    try:
        project = database.find_project(request.project_id)
        conv_logger.log_proyecto_cargado(request.project_id)
    except ValueError as e:
        conv_logger.log_error(f"Proyecto no encontrado: {request.project_id}", critico=True)
        return JSONResponse(status_code=404, content={"error": "Project not found"})
    except Exception as e:
        conv_logger.log_error(f"Error al cargar proyecto: {str(e)}", critico=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    graph = await Graph.create(request.project_id, request.user_id, request.name, request.number_phone_agent, request.source, request.source_id, unique_id, project)
    response = await graph.execute(request.message)

    return JSONResponse(status_code=200, content=response)


