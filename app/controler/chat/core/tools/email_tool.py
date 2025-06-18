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

class EmailTool(BaseTool):
    name: str = "send_email"
    description: str = """
    Herramienta para enviar emails usando Resend.
    
    Parámetros disponibles:
    - from: Email del remitente (requerido)
    - to: Email(s) del destinatario (requerido, puede ser string o lista)
    - subject: Asunto del email (requerido)
    - html: Contenido HTML del email
    - text: Contenido de texto plano del email
    - cc: Email(s) en copia
    - bcc: Email(s) en copia oculta
    - reply_to: Email(s) para responder
    - headers: Headers personalizados (opcional)
    
    Ejemplos de uso:
    - Enviar email simple: from="sender@domain.com", to="recipient@domain.com", subject="Hola", html="<h1>Hola mundo</h1>"
    - Enviar con copia: from="sender@domain.com", to="recipient@domain.com", cc="copy@domain.com", subject="Test", html="<p>Contenido</p>"
    - Enviar a múltiples destinatarios: from="sender@domain.com", to=["user1@domain.com", "user2@domain.com"], subject="Newsletter", html="<p>Contenido</p>"
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
        Envía un email usando la API de Resend.
        """
        if not self._api_key:
            logger.error("RESEND_API_KEY no configurada")
            return {"error": "API key de Resend no configurada"}
            
        try:
            logger.info(f"Intentando enviar email desde {from_email} a {to}")
            
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
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"Enviando petición a {self._base_url}/emails")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/emails",
                    json=payload,
                    headers=headers
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
            logger.error(f"Error en send_email: {str(e)}")
            return {
                "success": False,
                "error": f"Error enviando email: {str(e)}"
            }
    
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
                from_email = "noreply@ublix.com"
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