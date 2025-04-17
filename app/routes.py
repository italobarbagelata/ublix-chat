from fastapi import APIRouter, Request, FastAPI
from app.controler.chat import chat
from app.controler.webhook.instagram_webhook import process_webhook_instagram

chat_router = APIRouter(prefix="/api/chat", tags=["chat"])
webhook_router = APIRouter(prefix="/api/webhook", tags=["webhook"])

##########################
# Chat
##########################
@chat_router.post("/message", operation_id="send_chat_message")
async def chat_with_agent(request: Request):
    """Chat with the server."""
    return await chat(request)


##########################
# Webhook
##########################
@webhook_router.post("/instagram", operation_id="process_instagram_webhook")
async def process_instagram_webhook(request: Request):
    """Procesa el webhook de Instagram."""
    return await process_webhook_instagram(request)

async def init_routes(app: FastAPI):
    app.include_router(chat_router)
    return app
