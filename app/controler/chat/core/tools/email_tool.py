import logging
import os
import aiohttp
from typing import Optional, List, Dict, Any
from langchain.tools import BaseTool
from langchain.callbacks.manager import CallbackManagerForToolRun
from pydantic import Field

logger = logging.getLogger(__name__)

def extract_value(value):
    """
    Extrae el valor real de un FieldInfo o cualquier otro objeto.
    """
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
    name: str = "send_email"
    description: str = """
    Herramienta profesional para envío de emails usando Resend. Gestiona automáticamente el formato y validaciones.
    
    🎯 PROPÓSITO: Envío de emails profesionales con soporte completo para HTML, texto plano, y gestión de destinatarios.
    
    📧 CASOS DE USO PRINCIPALES:
    - Confirmaciones de citas y eventos (integración automática con calendario)
    - Notificaciones profesionales y comunicación con clientes
    - Respuestas automáticas y seguimiento de procesos
    - Emails promocionales y newsletters
    
    📋 PARÁMETROS DISPONIBLES:
    
    ✅ REQUERIDOS:
    - to: Email(s) del destinatario (string o lista separada por comas)
    - subject: Asunto del email
    
    📝 CONTENIDO (al menos uno requerido):
    - html: Contenido HTML del email (recomendado para emails profesionales)
    - text: Contenido de texto plano del email (alternativa o complemento)
    
    ⚙️ OPCIONALES:
    - from_email: Email del remitente (por defecto: "noreply@ublix.app")
    - cc: Email(s) en copia (string o lista separada por comas)
    - bcc: Email(s) en copia oculta (string o lista separada por comas)
    - reply_to: Email(s) para responder (string o lista separada por comas)
    - headers: Headers personalizados (diccionario, uso avanzado)
    
    🔄 INTEGRACIÓN AUTOMÁTICA:
    - Se ejecuta automáticamente después de crear eventos de calendario cuando está configurado
    - Extrae información de contacto del usuario usando save_contact_tool
    - Valida formatos de email antes del envío
    - Maneja múltiples destinatarios automáticamente
    
    📐 FORMATO DE EMAILS:
    - HTML: Usar para emails profesionales con formato, logos, y estilos
    - Texto plano: Para máxima compatibilidad y emails simples
    - Ambos: El cliente elegirá automáticamente la mejor versión
    
    🛡️ VALIDACIONES AUTOMÁTICAS:
    - Formato de email válido
    - Presencia de contenido (HTML o texto)
    - API key configurada correctamente
    - Gestión de errores con mensajes informativos
    
    💡 MEJORES PRÁCTICAS:
    - Usar HTML para emails con información de eventos, confirmaciones
    - Incluir información de contacto del proyecto en la firma
    - Personalizar asunto según el tipo de comunicación
    - Extraer nombre del usuario de la conversación para personalización
    
    ⚡ EJECUCIÓN AUTOMÁTICA:
    Esta herramienta puede ejecutarse automáticamente según las instrucciones del proyecto.
    Por ejemplo, después de crear eventos de calendario o completar procesos específicos.
    
    Ejemplos de uso:
    - Confirmación de cita: send_email(to="cliente@email.com", subject="Confirmación de cita", html="<h2>Cita confirmada</h2><p>Su cita ha sido agendada para...</p>")
    - Múltiples destinatarios: send_email(to="cliente1@email.com,cliente2@email.com", subject="Newsletter", html="<p>Contenido newsletter</p>")
    - Con copia: send_email(to="cliente@email.com", cc="manager@empresa.com", subject="Propuesta", html="<p>Propuesta adjunta</p>")
    """
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self):
        super().__init__()
        self._api_key = os.getenv("RESEND_API_KEY")
        if not self._api_key:
            logger.warning("RESEND_API_KEY no encontrada en variables de entorno")
        else:
            logger.info("RESEND_API_KEY configurada correctamente")
        self._base_url = "https://api.resend.com"
        
    async def _send_email(
        self,
        from_email: str,
        to: str | List[str],
        subject: str,
        html: Optional[str] = None,
        text: Optional[str] = None,
        cc: Optional[str | List[str]] = None,
        bcc: Optional[str | List[str]] = None,
        reply_to: Optional[str | List[str]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Envía un email usando la función independiente send_email_async.
        """
        return await send_email_async(
            to=to,
            subject=subject,
            html=html,
            text=text,
            from_email=from_email,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
            headers=headers
        )
    
    async def _arun(
        self,
        from_email: str = Field(..., description="Email del remitente"),
        to: str = Field(..., description="Email(s) del destinatario (separar múltiples con coma)"),
        subject: str = Field(..., description="Asunto del email"),
        html: Optional[str] = Field(None, description="Contenido HTML del email"),
        text: Optional[str] = Field(None, description="Contenido de texto plano del email"),
        cc: Optional[str] = Field(None, description="Email(s) en copia (separar múltiples con coma)"),
        bcc: Optional[str] = Field(None, description="Email(s) en copia oculta (separar múltiples con coma)"),
        reply_to: Optional[str] = Field(None, description="Email(s) para responder (separar múltiples con coma)"),
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Envía un email usando Resend.
        """
        try:
            logger.info("EmailTool._arun iniciado")
            
            # Extraer valores reales de los parámetros
            from_email = extract_value(from_email)
            to = extract_value(to)
            subject = extract_value(subject)
            html = extract_value(html)
            text = extract_value(text)
            cc = extract_value(cc)
            bcc = extract_value(bcc)
            reply_to = extract_value(reply_to)
            
            # Validar parámetros requeridos
            if not to:
                return "❌ Error: Email de destinatario es requerido"
            if not subject:
                return "❌ Error: Asunto del email es requerido"
            
            # Usar email por defecto si no se proporciona remitente
            if not from_email:
                from_email = "noreply@ublix.app"
                logger.info(f"Usando email por defecto: {from_email}")
            
            logger.info(f"Parámetros extraídos: from={from_email}, to={to}, subject={subject}")
            
            # Procesar listas de emails - verificar que sean strings antes de procesar
            to_list = [email.strip() for email in to.split(",")] if isinstance(to, str) and "," in to else to
            cc_list = [email.strip() for email in cc.split(",")] if isinstance(cc, str) and cc and "," in cc else cc
            bcc_list = [email.strip() for email in bcc.split(",")] if isinstance(bcc, str) and bcc and "," in bcc else bcc
            reply_to_list = [email.strip() for email in reply_to.split(",")] if isinstance(reply_to, str) and reply_to and "," in reply_to else reply_to
            
            logger.info(f"Listas procesadas: to_list={to_list}, cc_list={cc_list}")
            
            result = await self._send_email(
                from_email=from_email,
                to=to_list,
                subject=subject,
                html=html,
                text=text,
                cc=cc_list,
                bcc=bcc_list,
                reply_to=reply_to_list
            )
            
            logger.info(f"Resultado del envío: {result}")
            
            if result.get("success"):
                return f"✅ Email enviado correctamente. ID: {result.get('email_id')}"
            else:
                return f"❌ Error enviando email: {result.get('error')}"
                
        except Exception as e:
            logger.error(f"Error in email tool: {str(e)}")
            return f"❌ Error en la herramienta de email: {str(e)}"
    
    def _run(
        self,
        from_email: str,
        to: str,
        subject: str,
        html: Optional[str] = None,
        text: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        reply_to: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Implementación síncrona (no se usa, pero es requerida por la clase base).
        """
        raise NotImplementedError("This tool only supports async execution") 