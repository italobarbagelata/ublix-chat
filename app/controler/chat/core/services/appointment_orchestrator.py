"""
🎯 ORCHESTRATOR PRINCIPAL PARA SISTEMA DE CITAS

Coordina todos los servicios (Email, Webhook, Validación) manteniendo
todas las configuraciones y funcionalidades existentes de agenda_tool.py.
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

from .email_service import EmailService
from .webhook_service import WebhookService
from .schedule_validator import ScheduleValidator

logger = logging.getLogger(__name__)

class AppointmentOrchestrator:
    """Orchestrator principal que coordina el flujo completo de citas"""
    
    def __init__(self, cached_project_config: Dict[str, Any] = None, project_id: str = None):
        self.cached_project_config = cached_project_config
        self.project_id = project_id
        
        # Inicializar servicios especializados
        self.email_service = EmailService(cached_project_config)
        self.webhook_service = WebhookService(cached_project_config, project_id)
        self.schedule_validator = ScheduleValidator(cached_project_config)
    
    def validate_appointment_data(self, appointment_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida que todos los datos necesarios estén presentes"""
        required_fields = ['title', 'start_datetime', 'end_datetime', 'attendee_email']
        missing_fields = []
        
        for field in required_fields:
            if not appointment_data.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            return False, f"❌ Faltan campos requeridos: {', '.join(missing_fields)}"
        
        return True, "✅ Datos de cita válidos"
    
    def get_schedule_configuration(self, workflow_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Obtiene la configuración granular de horarios desde workflow_settings"""
        return self.schedule_validator.parse_granular_schedule(workflow_settings)
    
    def validate_specific_day_availability(self, day_name: str, workflow_settings: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida si un día específico está disponible según configuración granular"""
        schedule = self.get_schedule_configuration(workflow_settings)
        return self.schedule_validator.validate_specific_day_request(schedule, day_name)
    
    def validate_datetime_in_schedule(self, target_datetime: datetime, workflow_settings: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida si una fecha/hora específica está dentro de horarios laborales"""
        schedule = self.get_schedule_configuration(workflow_settings)
        return self.schedule_validator.is_time_in_working_hours(schedule, target_datetime)
    
    def get_available_schedule_summary(self, workflow_settings: Dict[str, Any]) -> str:
        """Genera resumen de horarios disponibles"""
        schedule = self.get_schedule_configuration(workflow_settings)
        return self.schedule_validator.get_available_schedule_summary(schedule)
    
    def extract_day_from_request(self, user_text: str) -> Optional[str]:
        """Extrae el día solicitado del texto del usuario"""
        return self.schedule_validator.extract_day_from_text(user_text)
    
    def validate_date_consistency(self, user_text: str) -> Tuple[bool, str, Optional[str]]:
        """Valida consistencia entre día y fecha mencionados"""
        return self.schedule_validator.validate_date_consistency(user_text)
    
    async def send_confirmation_emails(
        self, appointment_data: Dict[str, Any], conversation_summary: str = None
    ) -> Dict[str, Any]:
        """Envía emails de confirmación tanto al cliente como al dueño"""
        try:
            email_results = {"client": None, "owner": None}
            
            # Email al cliente
            if appointment_data.get('attendee_email'):
                client_result = await self.email_service.send_client_confirmation_email(
                    attendee_email=appointment_data['attendee_email'],
                    title=appointment_data['title'],
                    start_datetime=appointment_data['start_datetime'],
                    end_datetime=appointment_data['end_datetime'],
                    attendee_name=appointment_data.get('attendee_name', ''),
                    attendee_phone=appointment_data.get('attendee_phone', ''),
                    description=appointment_data.get('description', ''),
                    meet_url=appointment_data.get('meet_url')
                )
                email_results["client"] = client_result
            
            # Email al dueño del proyecto
            owner_email = self.email_service.get_owner_email()
            if owner_email:
                owner_result = await self.email_service.send_owner_notification_email(
                    project_owner_email=owner_email,
                    title=appointment_data['title'],
                    start_datetime=appointment_data['start_datetime'],
                    end_datetime=appointment_data['end_datetime'],
                    attendee_email=appointment_data['attendee_email'],
                    attendee_name=appointment_data.get('attendee_name', ''),
                    attendee_phone=appointment_data.get('attendee_phone', ''),
                    description=appointment_data.get('description', ''),
                    link_conversation=appointment_data.get('conversation_link', 'No disponible')
                )
                email_results["owner"] = owner_result
            
            return email_results
            
        except Exception as e:
            logger.error(f"❌ Error enviando emails: {str(e)}")
            return {"client": {"success": False, "error": str(e)}, "owner": {"success": False, "error": str(e)}}
    
    async def send_webhook_notification(
        self, appointment_data: Dict[str, Any], conversation_summary: str = None
    ) -> Optional[str]:
        """Envía notificación a webhook si está configurado"""
        if not self.webhook_service.has_webhook_configured():
            return None
        
        return await self.webhook_service.send_webhook_notification(
            title=appointment_data['title'],
            start_datetime=appointment_data['start_datetime'],
            end_datetime=appointment_data['end_datetime'],
            attendee_email=appointment_data['attendee_email'],
            description=appointment_data.get('description', ''),
            conversation_summary=conversation_summary
        )
    
    async def process_complete_appointment(
        self, appointment_data: Dict[str, Any], conversation_summary: str = None
    ) -> Dict[str, Any]:
        """Procesa una cita completa: validación, emails y webhook"""
        try:
            # 1. Validar datos de la cita
            is_valid, validation_message = self.validate_appointment_data(appointment_data)
            if not is_valid:
                return {"success": False, "error": validation_message}
            
            # 2. Enviar emails de confirmación (paralelo)
            email_task = self.send_confirmation_emails(appointment_data, conversation_summary)
            
            # 3. Enviar webhook (paralelo)
            webhook_task = self.send_webhook_notification(appointment_data, conversation_summary)
            
            # Ejecutar ambas tareas en paralelo
            email_results, webhook_result = await asyncio.gather(
                email_task, webhook_task, return_exceptions=True
            )
            
            # Procesar resultados
            results = {
                "success": True,
                "appointment": appointment_data,
                "emails": email_results if not isinstance(email_results, Exception) else {"error": str(email_results)},
                "webhook": webhook_result if not isinstance(webhook_result, Exception) else {"error": str(webhook_result)}
            }
            
            # Generar mensaje de resumen
            summary_parts = [f"✅ Cita '{appointment_data['title']}' procesada exitosamente"]
            
            # Resumen de emails
            if isinstance(email_results, dict):
                if email_results.get("client", {}).get("success"):
                    summary_parts.append(f"📧 Email enviado al cliente: {appointment_data['attendee_email']}")
                if email_results.get("owner", {}).get("success"):
                    summary_parts.append(f"📧 Notificación enviada al dueño del proyecto")
            
            # Resumen de webhook
            if webhook_result:
                summary_parts.append(f"📡 Webhook ejecutado")
            
            results["summary"] = "\n".join(summary_parts)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error procesando cita completa: {str(e)}")
            return {
                "success": False,
                "error": f"Error procesando cita: {str(e)}",
                "appointment": appointment_data
            }
    
    def get_project_notifications_config(self) -> Dict[str, bool]:
        """Obtiene configuración de notificaciones del proyecto"""
        try:
            if not self.cached_project_config:
                return {"email_enabled": True, "webhook_enabled": False}
            
            general_settings = self.cached_project_config.get("general_settings", {})
            
            return {
                "email_enabled": True,  # Siempre habilitado por defecto
                "webhook_enabled": bool(general_settings.get("Webhook_url")),
                "owner_email": self.email_service.get_owner_email(),
                "webhook_url": self.webhook_service.get_webhook_url()
            }
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo configuración de notificaciones: {str(e)}")
            return {"email_enabled": True, "webhook_enabled": False}
    
    def generate_appointment_summary(self, appointment_data: Dict[str, Any]) -> str:
        """Genera un resumen legible de la cita"""
        try:
            # Información básica
            summary = f"📅 **{appointment_data.get('title', 'Cita')}**\n"
            summary += f"🕒 **Inicio:** {appointment_data.get('start_datetime', 'No especificado')}\n"
            summary += f"⏰ **Fin:** {appointment_data.get('end_datetime', 'No especificado')}\n"
            summary += f"📧 **Cliente:** {appointment_data.get('attendee_email', 'No especificado')}\n"
            
            # Información opcional
            if appointment_data.get('attendee_name'):
                summary += f"👤 **Nombre:** {appointment_data['attendee_name']}\n"
            
            if appointment_data.get('attendee_phone'):
                summary += f"📱 **Teléfono:** {appointment_data['attendee_phone']}\n"
            
            if appointment_data.get('description'):
                summary += f"📝 **Descripción:** {appointment_data['description']}\n"
            
            if appointment_data.get('meet_url'):
                summary += f"🎥 **Google Meet:** {appointment_data['meet_url']}\n"
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error generando resumen de cita: {str(e)}")
            return f"Cita: {appointment_data.get('title', 'Sin título')}" 