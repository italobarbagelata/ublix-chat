import logging
import os
import aiohttp
import asyncio
from typing import Optional, List, Dict, Any
from langchain_core.tools import BaseTool
from langchain_core.callbacks.manager import CallbackManagerForToolRun

logger = logging.getLogger(__name__)

def send_email_background(
    to: str,
    subject: str,
    html: Optional[str] = None,
    text: Optional[str] = None,
    from_email: str = "noreply@ublix.app",
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    reply_to: Optional[str] = None
):
    """
    Programa el envío de un email en background sin bloquear la respuesta.
    """
    def _send_in_background():
        try:
            asyncio.run(send_email_async(
                to=to, subject=subject, html=html, text=text,
                from_email=from_email, cc=cc, bcc=bcc, reply_to=reply_to
            ))
            logger.info(f"✅ Email enviado en background a {to}")
        except Exception as e:
            logger.error(f"❌ Error enviando email en background: {str(e)}")
    
    # Ejecutar en un hilo separado
    import threading
    thread = threading.Thread(target=_send_in_background)
    thread.daemon = True  # El hilo terminará cuando termine el programa principal
    thread.start()
    logger.info(f"📤 Email programado para envío en background a {to}")

def extract_value(value):
    """
    Extrae el valor real de un FieldInfo o cualquier otro objeto.
    """
    # Si es un tipo PydanticUndefined, retornar None
    if str(type(value).__name__) == 'PydanticUndefinedType':
        return None
    # Si tiene default, usarlo
    if hasattr(value, 'default'):
        return value.default
    elif hasattr(value, 'annotation'):
        return value.annotation
    else:
        return value

async def send_email_async(
    to: str | List[str],
    subject: str,
    html: Optional[str] = None,
    text: Optional[str] = None,
    from_email: str = "noreply@ublix.app",
    cc: Optional[str | List[str]] = None,
    bcc: Optional[str | List[str]] = None,
    reply_to: Optional[str | List[str]] = None,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Función independiente para enviar emails usando Resend.
    
    Parámetros:
    - to: Email(s) del destinatario (string o lista)
    - subject: Asunto del email
    - html: Contenido HTML del email (opcional)
    - text: Contenido de texto plano del email (opcional)
    - from_email: Email del remitente (por defecto: "noreply@ublix.app")
    - cc: Email(s) en copia (opcional)
    - bcc: Email(s) en copia oculta (opcional)
    - reply_to: Email(s) para responder (opcional)
    - headers: Headers personalizados (opcional)
    
    Retorna:
    - Dict con 'success': bool y 'email_id' o 'error'
    
    Ejemplo de uso:
    ```python
    from app.controler.chat.core.tools.email_tool import send_email_async
    
    # Uso básico
    result = await send_email_async(
        to="cliente@email.com",
        subject="Confirmación de cita",
        html="<h2>Su cita ha sido confirmada</h2>"
    )
    
    # Con múltiples destinatarios
    result = await send_email_async(
        to=["cliente1@email.com", "cliente2@email.com"],
        subject="Newsletter",
        html="<p>Contenido del newsletter</p>",
        cc="manager@empresa.com"
    )
    ```
    """
    api_key = os.getenv("RESEND_API_KEY")
    
    if not api_key:
        logger.error("RESEND_API_KEY no configurada")
        return {"success": False, "error": "API key de Resend no configurada"}
        
    try:
        logger.info(f"Intentando enviar email desde {from_email} a {to}")
        
        # Validar que hay contenido
        if not html and not text:
            return {"success": False, "error": "Se requiere contenido HTML o texto"}
        
        # Preparar el payload
        payload = {
            "from": from_email,
            "to": to,
            "subject": subject
        }
        
        # Agregar campos opcionales si están presentes
        if html:
            payload["html"] = html
        if text:
            payload["text"] = text
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc
        if reply_to:
            payload["reply_to"] = reply_to
        if headers:
            payload["headers"] = headers
            
        logger.info(f"Payload preparado: {payload}")
            
        # Headers de la petición
        request_headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        base_url = "https://api.resend.com"
        logger.info(f"Enviando petición a {base_url}/emails")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/emails",
                json=payload,
                headers=request_headers
            ) as response:
                logger.info(f"Respuesta de Resend: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Email enviado exitosamente. ID: {result.get('id')}")
                    return {
                        "success": True,
                        "email_id": result.get("id"),
                        "message": "Email enviado correctamente"
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Error enviando email: {response.status} - {error_text}")
                    return {
                        "success": False,
                        "error": f"Error {response.status}: {error_text}"
                    }
                    
    except Exception as e:
        logger.error(f"Error en send_email_async: {str(e)}")
        return {
            "success": False,
            "error": f"Error enviando email: {str(e)}"
        }

def send_email_sync(
    to: str | List[str],
    subject: str,
    html: Optional[str] = None,
    text: Optional[str] = None,
    from_email: str = "noreply@ublix.app",
    cc: Optional[str | List[str]] = None,
    bcc: Optional[str | List[str]] = None,
    reply_to: Optional[str | List[str]] = None,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Función síncrona para enviar emails usando Resend.
    
    Wrapper síncrono para send_email_async usando asyncio.
    
    Ejemplo de uso:
    ```python
    from app.controler.chat.core.tools.email_tool import send_email_sync
    
    # Uso síncrono
    result = send_email_sync(
        to="cliente@email.com",
        subject="Confirmación de cita",
        html="<h2>Su cita ha sido confirmada</h2>"
    )
    
    if result['success']:
        print(f"Email enviado con ID: {result['email_id']}")
    else:
        print(f"Error: {result['error']}")
    ```
    """
    import asyncio
    
    try:
        # Crear o usar el event loop existente
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Si ya hay un loop corriendo, crear una tarea
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(send_email_async(
                        to=to, subject=subject, html=html, text=text,
                        from_email=from_email, cc=cc, bcc=bcc,
                        reply_to=reply_to, headers=headers
                    ))
                )
                return future.result()
        else:
            # Si no hay loop corriendo, usar asyncio.run
            return asyncio.run(send_email_async(
                to=to, subject=subject, html=html, text=text,
                from_email=from_email, cc=cc, bcc=bcc,
                reply_to=reply_to, headers=headers
            ))
    except Exception as e:
        logger.error(f"Error en send_email_sync: {str(e)}")
        return {
            "success": False,
            "error": f"Error enviando email: {str(e)}"
        }

class EmailTool(BaseTool):
    """
    Herramienta optimizada de email que envía correos en background
    para no atrasar la respuesta del bot.
    """
    name: str = "send_email"
    description: str = """
    Herramienta RÁPIDA para envío de emails en background. NO atrasa la respuesta del bot.
    
    🚀 OPTIMIZADA PARA VELOCIDAD:
    - Programa el envío en background inmediatamente
    - Responde al usuario sin esperar
    - El email se envía en paralelo en un hilo separado
    
    📧 USO PARA NOTIFICACIONES:
    - Perfecto para notificar al dueño del bot sobre nuevos contactos
    - No afecta la velocidad de respuesta al usuario
    - Logging automático del estado de envío
    
    PARÁMETROS:
    - to: Email del destinatario (REQUERIDO)
    - subject: Asunto del email (REQUERIDO) 
    - html: Contenido HTML (OPCIONAL)
    - text: Contenido texto plano (OPCIONAL)
    - from_email: Remitente (por defecto: "noreply@ublix.app")
    - cc, bcc, reply_to: Opcionales
    """
    
    def __init__(self):
        super().__init__()
        # Verificar que la API key esté configurada
        api_key = os.getenv("RESEND_API_KEY")
        if not api_key:
            logger.warning("RESEND_API_KEY no configurada - emails no se enviarán")
        else:
            logger.info("EmailTool inicializada correctamente")
    
    async def _arun(
        self,
        to: str = None,
        subject: str = None,
        html: Optional[str] = None,
        text: Optional[str] = None,
        from_email: str = "noreply@ublix.app",
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        reply_to: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Envía email en background - respuesta inmediata sin esperar.
        """
        try:
            # Validar parámetros básicos
            if not to:
                return "❌ Error: Email de destinatario es requerido"
            if not subject:
                return "❌ Error: Asunto del email es requerido"
            
            # Normalizar parámetros
            from_email = from_email if isinstance(from_email, str) else "noreply@ublix.app"
            to = to if isinstance(to, str) else None
            subject = subject if isinstance(subject, str) else None
            
            # Programar envío en background
            send_email_background(
                to=to,
                subject=subject, 
                html=html,
                text=text,
                from_email=from_email,
                cc=cc,
                bcc=bcc,
                reply_to=reply_to
            )
            
            return f"✅ Email programado para envío a {to}"
            
        except Exception as e:
            logger.error(f"Error en EmailTool: {str(e)}")
            return f"❌ Error programando email: {str(e)}"
    
    def _run(self, *args, **kwargs) -> str:
        """Implementación síncrona - no usada pero requerida"""
        raise NotImplementedError("EmailTool solo soporta ejecución asíncrona")

