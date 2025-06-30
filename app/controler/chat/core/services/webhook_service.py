"""
🔗 SERVICIO DE WEBHOOKS PARA SISTEMA DE CITAS

Extrae y centraliza toda la lógica de webhook de agenda_tool.py
manteniendo todas las configuraciones y funcionalidades existentes.
"""

import logging
import aiohttp
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class WebhookService:
    """Servicio especializado para manejo de webhooks de citas"""
    
    def __init__(self, cached_project_config: Dict[str, Any] = None, project_id: str = None):
        self.cached_project_config = cached_project_config
        self.project_id = project_id
    
    async def send_webhook_notification(
        self, title: str, start_datetime: str, end_datetime: str, 
        attendee_email: str, description: str, conversation_summary: str = None
    ) -> Optional[str]:
        """Envía datos de la conversación al webhook configurado si está habilitado"""
        try:
            if not self.cached_project_config:
                logger.info("📡 No hay configuración cached del proyecto")
                return None
            
            # Verificar si existe webhook_url en general_settings
            general_settings = self.cached_project_config.get("general_settings", {})
            webhook_url = general_settings.get("Webhook_url")
            
            if not webhook_url:
                logger.info("📡 No hay webhook configurado en general_settings")
                return None
            
            logger.info(f"📡 Enviando datos al webhook: {webhook_url}")
            logger.info(f"🔍 Debug conversation_summary en webhook: '{conversation_summary}' (tipo: {type(conversation_summary)})")
            
            # Preparar datos del evento y conversación
            webhook_data = {
                "event_type": "appointment_scheduled",
                "timestamp": datetime.now().isoformat(),
                "project_id": self.project_id,
                "project_name": self.cached_project_config.get("name", "Proyecto"),
                "appointment_data": {
                    "title": title,
                    "start_datetime": start_datetime,
                    "end_datetime": end_datetime,
                    "attendee_email": attendee_email,
                    "description": description
                },
                "conversation_data": {
                    "summary": conversation_summary or "Resumen no disponible",
                    "client_email": attendee_email,
                    "scheduled_at": datetime.now().isoformat()
                },
                "project_config": {
                    "company_info": general_settings.get("company_info", {}),
                    "timezone": general_settings.get("timezone", "America/Santiago")
                }
            }
            
            # Enviar POST al webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=webhook_data,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Ublix-Webhook/1.0"
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ Webhook enviado exitosamente a {webhook_url}")
                        return f"✅ Datos enviados al webhook externo ({webhook_url})"
                    else:
                        logger.error(f"❌ Error en webhook: HTTP {response.status}")
                        return f"⚠️ Error en webhook: HTTP {response.status}"
                        
        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout al enviar webhook a {webhook_url}")
            return f"⚠️ Timeout enviando al webhook ({webhook_url})"
        except Exception as e:
            logger.error(f"❌ Error enviando webhook: {str(e)}")
            return f"⚠️ Error enviando webhook: {str(e)}"
    
    def has_webhook_configured(self) -> bool:
        """Verifica si hay un webhook configurado"""
        try:
            if not self.cached_project_config:
                return False
            
            general_settings = self.cached_project_config.get("general_settings", {})
            webhook_url = general_settings.get("Webhook_url")
            
            return bool(webhook_url)
        except Exception as e:
            logger.error(f"❌ Error verificando webhook: {str(e)}")
            return False
    
    def get_webhook_url(self) -> Optional[str]:
        """Obtiene la URL del webhook configurado"""
        try:
            if not self.cached_project_config:
                return None
            
            general_settings = self.cached_project_config.get("general_settings", {})
            return general_settings.get("Webhook_url")
        except Exception as e:
            logger.error(f"❌ Error obteniendo webhook URL: {str(e)}")
            return None 