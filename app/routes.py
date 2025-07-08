from fastapi import APIRouter, Request, FastAPI, BackgroundTasks, UploadFile, File
from app.chatbot import chatbot, chat_stream
from app.controler.webhook.instagram_webhook import process_webhook_instagram, verify_webhook_instagram
from app.controler.webhook.facebook_webhook import verify_webhook_facebook, process_webhook_facebook
from app.controler.webhook.whatsapp_webhook import verify_webhook_whatsapp, process_webhook_whatsapp
from app.models import ChatRequest
from app.controler.chat import chat, chat_stream, get_queue_status, get_system_stats, cancel_user_queue
from fastapi.responses import JSONResponse
from fastapi import HTTPException


chat_router = APIRouter(prefix="/api/chat", tags=["chat"])
webhook_router = APIRouter(prefix="/api/instagram", tags=["instagram"])
webhook_router_facebook = APIRouter(prefix="/api/facebook", tags=["facebook"])
webhook_router_whatsapp = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

##########################
# Chat
##########################

@chat_router.post("/message", operation_id="send_chat_message")
async def chat_with_agent(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = None
):
    """
    Chat con el servidor. Soporta mensajes con o sin imágenes.
    """
    return await chat(request, background_tasks, image)

@chat_router.post("/stream", operation_id="send_chat_message_stream")
async def chat_with_agent_stream(request: Request, background_tasks: BackgroundTasks):
    """🆕 Chat with the server using streaming for real-time responses."""
    return await chat_stream(request, background_tasks)

##########################
# Queue Management & Monitoring
##########################

@chat_router.get("/queue/status", operation_id="get_queue_status")
async def get_user_queue_status(request: Request):
    """📊 Obtiene el estado de la cola de un usuario específico."""
    return await get_queue_status(request)

@chat_router.get("/system/stats", operation_id="get_system_stats") 
async def get_chat_system_stats(request: Request):
    """📈 Obtiene estadísticas generales del sistema de chat."""
    return await get_system_stats(request)

@chat_router.post("/queue/cancel", operation_id="cancel_user_queue")
async def cancel_user_messages(request: Request):
    """🚫 Cancela todos los mensajes pendientes de un usuario."""
    try:
        req_body = await request.json()
        user_id = req_body.get("user_id")
        project_id = req_body.get("project_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id es requerido")
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id es requerido")
        
        from app.controler.chat.core.message_queue import message_queue
        
        # Cancelar mensajes en cola
        cancelled_count = await message_queue.cancel_user_messages(user_id, project_id)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "messages_cancelled": cancelled_count,
                "message": f"Se cancelaron {cancelled_count} mensajes pendientes"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno del servidor")

##########################
# Context Management
##########################

@chat_router.get("/context/accumulated", operation_id="get_accumulated_context")
async def get_user_accumulated_context(request: Request):
    """📝 Consulta el contexto acumulado de mensajes sin procesarlos."""
    return await get_accumulated_context(request)

@chat_router.post("/context/clear", operation_id="clear_accumulated_context")
async def clear_user_accumulated_context(request: Request):
    """🗑️ Limpia el contexto acumulado de un usuario."""
    return await clear_accumulated_context(request)

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

async def get_accumulated_context(request: Request):
    """
    📝 NUEVO: Endpoint para consultar el contexto acumulado de mensajes sin procesarlos
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
        
        # Importar función para obtener contexto acumulado
        from app.controler.chat import user_accumulated_context, context_lock
        
        # Obtener contexto sin limpiarlo
        async with context_lock:
            context_key = f"{project_id}_{user_id}"
            accumulated = user_accumulated_context.get(context_key, [])
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "user_id": user_id,
                "project_id": project_id,
                "accumulated_messages": accumulated,
                "message_count": len(accumulated),
                "has_pending_messages": len(accumulated) > 0,
                "message": f"Se encontraron {len(accumulated)} mensajes en contexto acumulado"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno del servidor")

async def clear_accumulated_context(request: Request):
    """
    🗑️ NUEVO: Endpoint para limpiar el contexto acumulado de un usuario
    """
    try:
        req_body = await request.json()
        user_id = req_body.get("user_id")
        project_id = req_body.get("project_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id es requerido")
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id es requerido")
        
        # Importar función para limpiar contexto acumulado
        from app.controler.chat import user_accumulated_context, context_lock
        
        # Limpiar contexto
        async with context_lock:
            context_key = f"{project_id}_{user_id}"
            cleared_count = 0
            if context_key in user_accumulated_context:
                cleared_count = len(user_accumulated_context[context_key])
                del user_accumulated_context[context_key]
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "user_id": user_id,
                "project_id": project_id,
                "messages_cleared": cleared_count,
                "message": f"Se limpiaron {cleared_count} mensajes del contexto acumulado"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno del servidor")

async def init_routes(app: FastAPI):
    app.include_router(chat_router)
    return app
