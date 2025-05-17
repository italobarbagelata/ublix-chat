import json
from app.resources.constants import STATUS_BAD_REQUEST
from app.resources.validations import (
    ValidationException,
    validate_json_body,
    validate_required_body_param,
)
from fastapi import HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
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
