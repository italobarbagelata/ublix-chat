from fastapi import APIRouter, Request, FastAPI
from app.controler.chat import chat

chat_router = APIRouter(prefix="/api/chat", tags=["chat"])

##########################
# Chat
##########################
@chat_router.post("/message", operation_id="send_chat_message")
async def chat_with_agent(request: Request):
    """Chat with the server."""
    return await chat(request)


async def init_routes(app: FastAPI):
    app.include_router(chat_router)
    return app
