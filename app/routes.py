from fastapi import APIRouter, Request, FastAPI, BackgroundTasks
from app.chatbot import chatbot, chat_stream
from app.controler.webhook.instagram_webhook import process_webhook_instagram, verify_webhook_instagram
from app.controler.webhook.facebook_webhook import verify_webhook_facebook, process_webhook_facebook
from app.controler.webhook.whatsapp_webhook import verify_webhook_whatsapp, process_webhook_whatsapp
from app.models import ChatRequest
    
chat_router = APIRouter(prefix="/api/chat", tags=["chat"])
webhook_router = APIRouter(prefix="/api/instagram", tags=["instagram"])
webhook_router_facebook = APIRouter(prefix="/api/facebook", tags=["facebook"])
webhook_router_whatsapp = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

##########################
# Chat
##########################

@chat_router.post("/message", operation_id="send_chat_message")
async def chat_with_agent(request: ChatRequest):
    """Chat with the server."""
    return await chatbot(request)

@chat_router.post("/stream", operation_id="send_chat_message_stream")
async def chat_with_agent_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    """🆕 Chat with the server using streaming for real-time responses."""
    return await chat_stream(request, background_tasks)


##########################
# Webhook
##########################

##########################
# Instagram
##########################
@webhook_router.post("/webhook", operation_id="process_instagram_webhook")
async def process_instagram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Procesa el webhook de Instagram."""
    return await process_webhook_instagram(request, background_tasks)

@webhook_router.get("/webhook", operation_id="verify_instagram_webhook")
async def instagram_verify(request: Request):
    """Verify Instagram webhook subscription."""
    return await verify_webhook_instagram(request)


##########################
# Facebook
##########################
@webhook_router_facebook.post("/webhook", operation_id="process_facebook_webhook")
async def process_facebook_webhook(request: Request, background_tasks: BackgroundTasks):
    """Procesa el webhook de Facebook."""
    return await process_webhook_facebook(request, background_tasks)

@webhook_router_facebook.get("/webhook", operation_id="verify_facebook_webhook")
async def facebook_verify(request: Request):
    """Verify Facebook webhook subscription."""
    return await verify_webhook_facebook(request)


##########################
# WhatsApp
##########################
@webhook_router_whatsapp.post("/webhook", operation_id="process_whatsapp_webhook")
async def process_whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Procesa el webhook de WhatsApp."""
    return await process_webhook_whatsapp(request, background_tasks)

@webhook_router_whatsapp.get("/webhook", operation_id="verify_whatsapp_webhook")
async def whatsapp_verify(request: Request):
    """Verify WhatsApp webhook subscription."""
    return await verify_webhook_whatsapp(request)

async def init_routes(app: FastAPI):
    app.include_router(chat_router)
    return app
