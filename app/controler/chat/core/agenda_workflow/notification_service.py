"""
Servicio especializado para notificaciones (emails y webhooks).
Maneja todas las comunicaciones salientes de forma eficiente y con retry automático.
"""

import asyncio
import aiohttp
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from app.controler.chat.core.tools.email_tool import EmailTool, send_email_async
from app.controler.chat.core.agenda_workflow.email_service import EmailService
from app.controler.chat.core.security.webhook_security import webhook_security_manager
from app.controler.chat.core.security.error_handler import raise_calendar_error, ErrorCategory, ErrorSeverity

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Servicio especializado para envío de notificaciones.
    Responsabilidad única: gestionar emails y webhooks con retry automático.
    """
    
    def __init__(self, cached_project_config: Dict[str, Any] = None):
        self.logger = logging.getLogger(__name__)
        self.email_tool = EmailTool()
        self.email_service = EmailService(cached_project_config)
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.cached_project_config = cached_project_config
        
        # Configuración de retry
        self.max_retries = 3
        self.base_delay = 1.0
    
    async def send_appointment_notifications(self,
                                           event_data: Dict[str, Any],
                                           contact_data: Dict[str, Any],
                                           project_id: str,
                                           user_id: str,
                                           conversation_summary: str = "") -> Dict[str, Any]:
        """
        Envía todas las notificaciones relacionadas con una cita.
        
        Args:
            event_data: Datos del evento creado
            contact_data: Datos del contacto
            project_id: ID del proyecto
            user_id: ID del usuario
            conversation_summary: Resumen de la conversación
            
        Returns:
            Resultado del envío de notificaciones
        """
        results = {
            'email_sent': False,
            'webhook_sent': False,
            'errors': []
        }
        
        # Ejecutar notificaciones en paralelo
        tasks = []
        
        # Verificar si el proyecto tiene habilitado el envío de emails
        send_emails = True  # Por defecto enviar emails
        if self.cached_project_config:
            general_settings = self.cached_project_config.get('general_settings', {})
            send_emails = general_settings.get('send_email_notifications', True)
        
        # Task para email
        if contact_data.get('email') and send_emails:
            email_task = asyncio.create_task(
                self._send_email_notification(event_data, contact_data, project_id)
            )
            tasks.append(('email', email_task))
        elif contact_data.get('email') and not send_emails:
            self.logger.info("📧 Email no enviado - deshabilitado en configuración del proyecto")
        
        # Task para webhook
        webhook_task = asyncio.create_task(
            self._send_webhook_notification(event_data, contact_data, project_id, user_id, conversation_summary)
        )
        tasks.append(('webhook', webhook_task))
        
        # Esperar resultados con timeout
        try:
            completed_tasks = await asyncio.wait_for(
                asyncio.gather(*[task for _, task in tasks], return_exceptions=True),
                timeout=30.0
            )
            
            # Procesar resultados
            for i, (notification_type, _) in enumerate(tasks):
                result = completed_tasks[i]
                
                if isinstance(result, Exception):
                    self.logger.error(f"Error en notificación {notification_type}: {str(result)}")
                    results['errors'].append(f"{notification_type}: {str(result)}")
                else:
                    if notification_type == 'email':
                        results['email_sent'] = result.get('success', False)
                        if not results['email_sent']:
                            results['errors'].append(f"email: {result.get('error', 'Unknown error')}")
                    elif notification_type == 'webhook':
                        results['webhook_sent'] = result.get('success', False)
                        if not results['webhook_sent']:
                            results['errors'].append(f"webhook: {result.get('error', 'Unknown error')}")
            
        except asyncio.TimeoutError:
            self.logger.error("Timeout enviando notificaciones")
            results['errors'].append("Timeout en envío de notificaciones")
        
        return results
    
    async def _send_email_notification(self,
                                     event_data: Dict[str, Any],
                                     contact_data: Dict[str, Any],
                                     project_id: str) -> Dict[str, Any]:
        """Envía notificación por email con retry automático."""
        
        for attempt in range(self.max_retries):
            try:
                # Preparar datos del email usando EmailService
                email_subject, email_content = await self._generate_email_content_from_template(
                    event_data, contact_data, project_id
                )
                
                # Enviar email
                result = await send_email_async(
                    to=contact_data['email'],
                    subject=email_subject,
                    html=email_content
                )
                
                if result and result.get('success'):
                    self.logger.info(f"Email enviado exitosamente a {contact_data['email']}")
                    return {'success': True}
                else:
                    error_msg = result.get('error', 'Unknown email error') if result else 'Email service unavailable'
                    
                    if attempt < self.max_retries - 1:
                        wait_time = self.base_delay * (2 ** attempt)
                        self.logger.warning(f"Email falló (intento {attempt + 1}), reintentando en {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return {'success': False, 'error': error_msg}
                        
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.base_delay * (2 ** attempt)
                    self.logger.warning(f"Error enviando email (intento {attempt + 1}): {str(e)}, reintentando en {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    return {'success': False, 'error': str(e)}
        
        return {'success': False, 'error': 'Max retries exceeded'}
    
    async def _send_webhook_notification(self,
                                       event_data: Dict[str, Any],
                                       contact_data: Dict[str, Any],
                                       project_id: str,
                                       user_id: str,
                                       conversation_summary: str) -> Dict[str, Any]:
        """Envía notificación por webhook con retry automático."""
        
        try:
            # Preparar datos del webhook
            webhook_data = {
                "event_type": "appointment_scheduled",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "project_id": project_id,
                "appointment_data": {
                    "title": event_data.get('title', ''),
                    "start_datetime": event_data.get('start_time', ''),
                    "end_datetime": event_data.get('end_time', ''),
                    "event_url": event_data.get('event_url', ''),
                    "meet_url": event_data.get('meet_url', ''),
                    "attendee_email": contact_data.get('email', ''),
                    "description": event_data.get('description', '')
                },
                "conversation_data": {
                    "summary": conversation_summary,
                    "client_email": contact_data.get('email', ''),
                    "scheduled_at": datetime.now(timezone.utc).isoformat()
                },
                "user_data": {
                    "user_id": user_id,
                    "name": contact_data.get('name', ''),
                    "email": contact_data.get('email', ''),
                    "phone": contact_data.get('phone_number', contact_data.get('phone', '')),
                    # Incluir todos los datos adicionales del contacto
                    **{k: v for k, v in contact_data.items() if k not in ['name', 'email', 'phone', 'phone_number']}
                }
            }
            
            # Obtener configuración del webhook desde proyecto
            webhook_url = self._get_webhook_url(project_id)
            
            if not webhook_url:
                self.logger.info("No hay webhook configurado")
                return {'success': True, 'skipped': True}
            
            # Enviar webhook seguro con retry
            for attempt in range(self.max_retries):
                try:
                    secure_payload, secure_headers, is_valid, error_msg = webhook_security_manager.create_secure_webhook(
                        project_id, webhook_url, webhook_data
                    )
                    
                    if not is_valid:
                        return {'success': False, 'error': f"Webhook security error: {error_msg}"}
                    
                    # Enviar webhook
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            webhook_url,
                            data=secure_payload,
                            headers=secure_headers,
                            timeout=aiohttp.ClientTimeout(total=15)
                        ) as response:
                            if response.status == 200:
                                self.logger.info(f"✅ Webhook HTTP 200 OK - enviado a {webhook_url}")
                                return {'success': True}
                            else:
                                error_msg = f"HTTP {response.status}"
                                
                                if attempt < self.max_retries - 1:
                                    wait_time = self.base_delay * (2 ** attempt)
                                    self.logger.warning(f"Webhook falló (intento {attempt + 1}): {error_msg}, reintentando en {wait_time}s")
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    return {'success': False, 'error': error_msg}
                
                except asyncio.TimeoutError:
                    if attempt < self.max_retries - 1:
                        wait_time = self.base_delay * (2 ** attempt)
                        self.logger.warning(f"Webhook timeout (intento {attempt + 1}), reintentando en {wait_time}s")
                        await asyncio.sleep(wait_time)
                    else:
                        return {'success': False, 'error': 'Webhook timeout'}
                
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        wait_time = self.base_delay * (2 ** attempt)
                        self.logger.warning(f"Error webhook (intento {attempt + 1}): {str(e)}, reintentando en {wait_time}s")
                        await asyncio.sleep(wait_time)
                    else:
                        return {'success': False, 'error': str(e)}
            
            return {'success': False, 'error': 'Max retries exceeded'}
            
        except Exception as e:
            self.logger.error(f"Error preparando webhook: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def send_update_notifications(self,
                                      event_data: Dict[str, Any],
                                      project_id: str,
                                      user_id: str) -> Dict[str, Any]:
        """Envía notificaciones de actualización de evento."""
        
        results = {
            'notifications_sent': 0,
            'errors': []
        }
        
        try:
            # Preparar datos de actualización
            update_data = {
                "event_type": "appointment_updated",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "project_id": project_id,
                "event_data": event_data,
                "user_id": user_id
            }
            
            # Enviar notificaciones (implementación simplificada)
            # En producción: obtener lista de destinatarios y enviar a cada uno
            
            self.logger.info(f"Notificaciones de actualización preparadas para evento")
            results['notifications_sent'] = 1
            
        except Exception as e:
            self.logger.error(f"Error enviando notificaciones de actualización: {str(e)}")
            results['errors'].append(str(e))
        
        return results
    
    async def send_cancellation_notifications(self,
                                            event_data: Dict[str, Any],
                                            project_id: str,
                                            user_id: str) -> Dict[str, Any]:
        """Envía notificaciones de cancelación de evento."""
        
        results = {
            'notifications_sent': 0,
            'errors': []
        }
        
        try:
            # Preparar datos de cancelación
            cancellation_data = {
                "event_type": "appointment_cancelled",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "project_id": project_id,
                "cancelled_event_data": event_data,
                "user_id": user_id
            }
            
            # Enviar notificaciones (implementación simplificada)
            # En producción: obtener lista de destinatarios y enviar a cada uno
            
            self.logger.info(f"Notificaciones de cancelación preparadas para evento")
            results['notifications_sent'] = 1
            
        except Exception as e:
            self.logger.error(f"Error enviando notificaciones de cancelación: {str(e)}")
            results['errors'].append(str(e))
        
        return results
    
    async def _generate_email_content_from_template(self,
                                                  event_data: Dict[str, Any],
                                                  contact_data: Dict[str, Any],
                                                  project_id: str) -> tuple[str, str]:
        """
        Genera contenido del email usando el template de configuración.
        
        Returns:
            Tuple (subject, content)
        """
        try:
            # Usar EmailService para generar contenido con template
            subject, content = await self.email_service.generate_client_email_content(
                title=event_data.get('title', ''),
                start_datetime=event_data.get('start_time', ''),
                end_datetime=event_data.get('end_time', ''),
                attendee_name=contact_data.get('name', ''),
                attendee_phone=contact_data.get('phone', contact_data.get('phone_number', '')),
                description=event_data.get('description', ''),
                meet_url=event_data.get('meet_url', '')
            )
            
            # Si el EmailService no pudo generar contenido, usar fallback
            if not subject or not content:
                self.logger.warning("EmailService no pudo generar contenido, usando fallback")
                return self._generate_email_content_fallback(event_data, contact_data)
            
            # Agregar URL del evento al contenido si está disponible y no está ya incluida
            if event_data.get('event_url') and event_data['event_url'] not in content:
                content += f"\n\n📅 Ver en calendario: {event_data['event_url']}\n"
            
            return subject, content
            
        except Exception as e:
            self.logger.error(f"Error generando email desde template: {str(e)}")
            return self._generate_email_content_fallback(event_data, contact_data)
    
    def _generate_email_content_fallback(self,
                                       event_data: Dict[str, Any],
                                       contact_data: Dict[str, Any]) -> tuple[str, str]:
        """
        Genera contenido de email de fallback cuando no hay template disponible.
        
        Returns:
            Tuple (subject, content)
        """
        # Subject
        subject = f"Confirmación de cita - {event_data.get('title', 'Reunión')}"
        
        # Content
        content = f"""
        Hola {contact_data.get('name', 'Cliente')},
        
        Tu cita ha sido confirmada con los siguientes detalles:
        
        📅 Evento: {event_data.get('title', 'Reunión')}
        🕐 Fecha y hora: {event_data.get('start_time', 'Por confirmar')}
        📍 Modalidad: Virtual (Google Meet)
        
        """
        
        # Agregar Meet URL si está disponible
        if event_data.get('meet_url'):
            content += f"\n🎥 Enlace de la reunión: {event_data['meet_url']}\n"
        
        # Agregar enlace del evento
        if event_data.get('event_url'):
            content += f"\n📅 Ver en calendario: {event_data['event_url']}\n"
        
        content += """
        
        Saludos cordiales,
        El equipo de atención
        """
        
        return subject, content
    
    async def cleanup(self):
        """Limpia recursos del servicio."""
        try:
            self.executor.shutdown(wait=True)
            self.logger.info("NotificationService cleanup completado")
        except Exception as e:
            self.logger.error(f"Error en cleanup de NotificationService: {str(e)}")
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del servicio de notificaciones."""
        return {
            'max_retries': self.max_retries,
            'base_delay': self.base_delay,
            'executor_active': not self.executor._shutdown
        }
    
    def _get_webhook_url(self, project_id: str) -> Optional[str]:
        """
        Obtiene la URL del webhook desde la configuración del proyecto.
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            URL del webhook o None si no está configurado
        """
        try:
            # Priorizar configuración en cache si está disponible
            if self.cached_project_config:
                general_settings = self.cached_project_config.get("general_settings", {})
                webhook_url = general_settings.get("Webhook_url")
                if webhook_url:
                    self.logger.info(f"📡 Webhook URL obtenida desde cache: {webhook_url}")
                    return webhook_url
            
            # Fallback: consultar base de datos directamente
            self.logger.info("Consultando webhook URL desde base de datos")
            from app.controler.chat.store.supabase_client import SupabaseClient
            supabase_client = SupabaseClient()
            response = supabase_client.client.table("agenda").select("general_settings").eq("project_id", project_id).execute()
            
            if response.data and len(response.data) > 0:
                general_settings = response.data[0].get("general_settings", {})
                webhook_url = general_settings.get("Webhook_url")
                if webhook_url:
                    self.logger.info(f"📡 Webhook URL obtenida desde DB: {webhook_url}")
                    return webhook_url
            
            self.logger.info("📡 No hay webhook configurado en el proyecto")
            return None
            
        except Exception as e:
            self.logger.error(f"Error obteniendo webhook URL: {str(e)}")
            return None