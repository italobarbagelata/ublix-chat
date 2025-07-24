"""
📧 SERVICIO DE EMAILS PARA SISTEMA DE CITAS

Extrae y centraliza toda la lógica de email de agenda_tool.py
manteniendo todas las configuraciones y funcionalidades existentes.
"""

import logging
import aiohttp
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from app.controler.chat.core.tools.email_tool import send_email_async

logger = logging.getLogger(__name__)

class EmailService:
    """Servicio especializado para manejo de emails de citas"""
    
    def __init__(self, cached_project_config: Dict[str, Any] = None):
        self.cached_project_config = cached_project_config
    
    async def get_email_template_from_config(self) -> Optional[Dict[str, str]]:
        """Extrae template de email desde configuración del proyecto (template único)"""
        try:
            if not self.cached_project_config:
                logger.error("❌ No hay configuración cached del proyecto")
                return None
                
            email_templates = self.cached_project_config.get("email_templates", {})
            
            # Buscar el template único (puede estar como objeto directo o con clave específica)
            if isinstance(email_templates, dict):
                # Si hay un template directo con subject y content
                if "subject" in email_templates and "content" in email_templates:
                    logger.info(f"✅ Template único encontrado para {self.cached_project_config.get('name', 'proyecto')}")
                    return {
                        "subject": email_templates.get("subject", "Confirmación de Reunión"),
                        "content": email_templates.get("content", "")
                    }
                # Si hay templates con claves, usar el primero disponible (confirmacion, etc.)
                elif email_templates:
                    template_keys = ["confirmacion", "confirmation", "default"]
                    for key in template_keys:
                        if key in email_templates:
                            template = email_templates[key]
                            logger.info(f"✅ Template '{key}' encontrado para {self.cached_project_config.get('name', 'proyecto')}")
                            return {
                                "subject": template.get("subject", f"Confirmación de Reunión"),
                                "content": template.get("content", "")
                            }
                    
                    # Si no hay claves específicas, usar el primer template disponible
                    first_key = list(email_templates.keys())[0]
                    template = email_templates[first_key]
                    logger.info(f"✅ Usando primer template disponible '{first_key}' para {self.cached_project_config.get('name', 'proyecto')}")
                    return {
                        "subject": template.get("subject", f"Confirmación de Reunión"),
                        "content": template.get("content", "")
                    }
                else:
                    logger.error(f"❌ No se encontraron templates de email en la configuración")
                    return None
            else:
                logger.error(f"❌ Formato incorrecto de email_templates en la configuración")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error extrayendo template de email: {str(e)}")
            return None
    
    async def generate_client_email_content(
        self, title: str, start_datetime: str, end_datetime: str, 
        attendee_name: str, attendee_phone: str, description: str, meet_url: str = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """Genera contenido de email para cliente usando configuración del proyecto"""
        try:
            template = await self.get_email_template_from_config()
            
            if not template:
                return None, None
            
            description_section = f'<p><strong>📝 Descripción:</strong> {description}</p>' if description else ''
            
            # Generar sección de Meet URL si está disponible
            meet_section = ""
            if meet_url:
                meet_section = f'<p><strong>🎥 Link de Google Meet:</strong> <a href="{meet_url}" target="_blank">{meet_url}</a></p>'
            
            # Generar subject
            subject = template.get("subject", "Confirmación de Reunión")
            if "{title}" in subject:
                subject = subject.replace("{title}", title or "Evento")
            
            # Generar contenido
            content = template.get("content", "")
            
            # Reemplazar variables en el contenido (manejar valores None)
            replacements = {
                "{attendee_name}": attendee_name or "Cliente",
                "{title}": title or "Evento",
                "{start_datetime}": start_datetime or "Por confirmar",
                "{end_datetime}": end_datetime or "Por confirmar",
                "{description_section}": description_section,
                "{description}": description or "Sin descripción",
                "{attendee_phone}": attendee_phone or "No especificado",
                "{meet_url}": meet_url or "No disponible",
                "{meet_section}": meet_section,
            }
            
            for placeholder, value in replacements.items():
                if placeholder in content:
                    content = content.replace(placeholder, str(value))
            
            return subject, content
            
        except Exception as e:
            logger.error(f"Error generando contenido de email: {str(e)}")
            return None, None
    
    def generate_owner_notification(
        self, title: str, start_datetime: str, end_datetime: str, 
        attendee_email: str, attendee_name: str, attendee_phone: str, 
        description: str, link_conversation: str
    ) -> Tuple[str, str]:
        """Genera email de notificación para el dueño del proyecto"""
        subject = f"🔔 Nueva cita agendada: {title}"
        
        content = f"""
        <html lang="en">
        <head>
            <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Email</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Mulish:ital,wght@0,200..1000;1,200..1000&display=swap" rel="stylesheet">
        </head>
        <body style="background-color: #fafafa;">
            <div style="box-sizing:border-box;margin:32px auto;font-family:'Segoe UI', Arial, sans-serif;background-color:#f5f7fa;border-radius:16px;box-shadow:0 6px 24px rgba(44, 62, 80, 0.10);max-width:540px;overflow:hidden;">
            <div style="box-sizing:border-box;margin:0px;background-color:#764ba2;padding:28px 0;text-align:center;">
                <h2 style="box-sizing:border-box;margin:0;overflow-wrap:break-word;line-height:1.35em;font-size:2rem;padding-top:0.8em;color:#fff;letter-spacing:1px;">
                <strong style="box-sizing:border-box;margin:0px;">🔔 Nueva Cita Confirmada</strong>
                </h2>
            </div>
            <div style="box-sizing:border-box;margin:0px;padding:32px 24px 18px;">
                <h3 style="box-sizing:border-box;margin:0px 0px 8px;overflow-wrap:break-word;line-height:1.35em;font-size:1.1rem;padding-top:0.8em;color:#21293c;letter-spacing:0.2px;">
                Detalles del Cliente
                </h3>
                <div style="box-sizing:border-box;margin:0px 0px 18px;background-color:#fff;border-radius:10px;border:1px solid #ececec;padding:18px 18px 10px;">
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">📝 Nombre:</strong> {attendee_name or 'No especificado'}
                </p>
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">📧 Email:</strong> {attendee_email or 'No especificado'}
                </p>
                <p style="box-sizing:border-box;margin:0;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">📱 Teléfono:</strong> {attendee_phone or 'No especificado'}
                </p>
                </div>
                <h3 style="box-sizing:border-box;margin:0px 0px 8px;overflow-wrap:break-word;line-height:1.35em;font-size:1.1rem;padding-top:0.8em;color:#21293c;letter-spacing:0.2px;">
                Detalles de la Cita
                </h3>
                <div style="box-sizing:border-box;margin:0px 0px 18px;background-color:#fff;border-radius:10px;border:1px solid #ececec;padding:18px;">
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">📅 Evento:</strong> {title}
                </p>
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">🕒 Inicio:</strong> {start_datetime}
                </p>
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">⏰ Fin:</strong> {end_datetime}
                </p>
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    <strong style="box-sizing:border-box;margin:0px;">📝 Descripción:</strong> {description}
                </p>
                <p style="box-sizing:border-box;margin:0 0 10px;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;">
                    💬 <strong style="box-sizing:border-box;margin:0px;">Conversación:</strong> {link_conversation}
                </p>
                </div>
                <div style="box-sizing:border-box;margin:6px 0px 0px;background-color:#e0f7ea;border-left:4px solid #13b87b;border-radius:8px;padding:15px;">
                <p style="box-sizing:border-box;margin:0;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:1em;line-height:1.6em;color:#127d56;">
                    <strong style="box-sizing:border-box;margin:0px;">✅ Estado: </strong><span style="box-sizing:border-box;margin:0px;font-weight:400;"><strong style="box-sizing:border-box;margin:0px;">Cita confirmada automáticamente</strong></span>
                </p>
                </div>
            </div>
            <div style="box-sizing:border-box;margin:0px;background-color:#263238;border-top:1px solid #313b48;color:#fff;padding:14px 0;text-align:center;">
                <p style="box-sizing:border-box;margin:0;overflow-wrap:break-word;max-width:none;padding-top:0.2em;font-size:13px;line-height:1.6em;letter-spacing:0.5px;">
                🚀  Ublix.app — Notificación automática
                </p>
            </div>
            </div>
        </body>
        </html>
        """
        
        return subject, content
    
    def get_owner_email(self) -> Optional[str]:
        """Obtiene email del dueño desde configuración cached"""
        try:
            if not self.cached_project_config:
                return None
            
            owner_email = self.cached_project_config.get('owner_email')
            contact_email = self.cached_project_config.get('contact_email')
            
            return owner_email or contact_email
                
        except Exception as e:
            logger.error(f"Error obteniendo email del dueño: {str(e)}")
            return None
    
    async def send_client_confirmation_email(
        self, attendee_email: str, title: str, start_datetime: str, 
        end_datetime: str, attendee_name: str, attendee_phone: str, 
        description: str, meet_url: str = None
    ) -> Dict[str, Any]:
        """Envía email de confirmación al cliente"""
        try:
            logger.info(f"📧 [EmailService] Enviando email a cliente: {attendee_email}")
            
            email_subject, email_content = await self.generate_client_email_content(
                title, start_datetime, end_datetime, attendee_name, attendee_phone, description, meet_url
            )
            
            if not email_subject or not email_content:
                return {"success": False, "error": "No se pudo generar contenido de email"}
            
            company_info = self.cached_project_config.get("general_settings", {}).get("company_info", {})
            company_name = company_info.get("name", "")
            from_email_with_name = f"{company_name} <noreply@ublix.app>"
            
            email_result = await send_email_async(
                from_email=from_email_with_name,
                to=attendee_email,
                subject=email_subject,
                html=email_content
            )
            
            if email_result.get("success"):
                logger.info(f"✅ [EmailService] Email de confirmación enviado a {attendee_email}")
                return {"success": True, "message": f"Email enviado a {attendee_email}"}
            else:
                logger.error(f"⚠️ [EmailService] Error enviando email: {email_result.get('error', 'Error desconocido')}")
                return {"success": False, "error": email_result.get('error', 'Error desconocido')}
                
        except Exception as e:
            logger.error(f"❌ [EmailService] Error enviando email al cliente: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def send_owner_notification_email(
        self, project_owner_email: str, title: str, start_datetime: str, 
        end_datetime: str, attendee_email: str, attendee_name: str, 
        attendee_phone: str, description: str, link_conversation: str
    ) -> Dict[str, Any]:
        """Envía email de notificación al dueño del proyecto"""
        try:
            logger.info(f"📧 [EmailService] Enviando notificación a dueño: {project_owner_email}")
            
            owner_subject, owner_content = self.generate_owner_notification(
                title, start_datetime, end_datetime, attendee_email, 
                attendee_name, attendee_phone, description, link_conversation
            )
            
            owner_email_result = await send_email_async(
                from_email="Agenda <noreply@ublix.app>",
                to=project_owner_email,
                subject=owner_subject,
                html=owner_content
            )
            
            if owner_email_result.get("success"):
                logger.info(f"✅ [EmailService] Notificación enviada al dueño del proyecto")
                return {"success": True, "message": f"Notificación enviada a {project_owner_email}"}
            else:
                logger.error(f"❌ [EmailService] Error notificando al dueño: {owner_email_result.get('error', 'Error desconocido')}")
                return {"success": False, "error": owner_email_result.get('error', 'Error desconocido')}
                
        except Exception as e:
            logger.error(f"❌ [EmailService] Error enviando notificación al dueño: {str(e)}")
            return {"success": False, "error": str(e)} 