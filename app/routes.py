from fastapi import APIRouter, Request, FastAPI
from app.controler.chat import chat
from app.controler.webhook.instagram_webhook import process_webhook_instagram, verify_webhook_instagram
from app.controler.webhook.facebook_webhook import verify_webhook_facebook, process_webhook_facebook
from app.controler.webhook.whatsapp_webhook import verify_webhook_whatsapp, process_webhook_whatsapp
    
chat_router = APIRouter(prefix="/api/chat", tags=["chat"])
webhook_router = APIRouter(prefix="/api/instagram", tags=["instagram"])
webhook_router_facebook = APIRouter(prefix="/api/facebook", tags=["facebook"])
webhook_router_whatsapp = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

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

##########################
# Instagram
##########################
@webhook_router.post("/webhook", operation_id="process_instagram_webhook")
async def process_instagram_webhook(request: Request):
    """Procesa el webhook de Instagram."""
    return await process_webhook_instagram(request)

@webhook_router.get("/webhook", operation_id="verify_instagram_webhook")
async def instagram_verify(request: Request):
    """Verify Instagram webhook subscription."""
    return await verify_webhook_instagram(request)


##########################
# Facebook
##########################
@webhook_router_facebook.post("/webhook", operation_id="process_facebook_webhook")
async def process_facebook_webhook(request: Request):
    """Procesa el webhook de Facebook."""
    return await process_webhook_facebook(request)

@webhook_router_facebook.get("/webhook", operation_id="verify_facebook_webhook")
async def facebook_verify(request: Request):
    """Verify Facebook webhook subscription."""
    return await verify_webhook_facebook(request)


##########################
# WhatsApp
##########################
@webhook_router_whatsapp.post("/webhook", operation_id="process_whatsapp_webhook")
async def process_whatsapp_webhook(request: Request):
    """Procesa el webhook de WhatsApp."""
    return await process_webhook_whatsapp(request)

@webhook_router_whatsapp.get("/webhook", operation_id="verify_whatsapp_webhook")
async def whatsapp_verify(request: Request):
    """Verify WhatsApp webhook subscription."""
    return await verify_webhook_whatsapp(request)

async def init_routes(app: FastAPI):
    app.include_router(chat_router)
    return app
