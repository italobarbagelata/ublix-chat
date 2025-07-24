"""
AgendaTool - Herramienta de agendamiento optimizada y modular.
Utiliza servicios especializados para mejor mantenabilidad y performance.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from langchain.tools import BaseTool

from app.controler.chat.core.agenda_workflow.workflow_manager import WorkflowManager, WorkflowContext
from app.controler.chat.core.agenda_workflow.calendar_service import CalendarService
from app.controler.chat.core.agenda_workflow.notification_service import NotificationService
from app.controler.chat.core.agenda_workflow.contact_manager import ContactManager
from app.controler.chat.core.security.input_validator import InputValidator, SecurityAuditLogger
from app.controler.chat.core.security.error_handler import safe_execute, raise_calendar_error, ErrorCategory, ErrorSeverity

logger = logging.getLogger(__name__)

class AgendaTool(BaseTool):
    """
    Herramienta de agenda con arquitectura modular.
    
    Responsabilidades:
    - Coordinar workflows a través de WorkflowManager
    - Validar entrada de datos
    - Manejar errores de forma robusta
    - Proporcionar interfaz unificada para LangChain
    """
    
    name: str = "agenda_tool"
    
    class Config:
        """Configuración de Pydantic para permitir campos arbitrarios."""
        arbitrary_types_allowed = True
        extra = "allow"  # Permitir campos extra
    description: str = """
    HERRAMIENTA PROFESIONAL DE AGENDAMIENTO Y HORARIOS
    FUNCIONALIDAD PRINCIPAL:
    - Gestión completa de agendamiento con arquitectura modular optimizada
    - Validación robusta y manejo de errores sin fallos silenciosos
    - Performance mejorada con operaciones asíncronas y cache inteligente
    - Separación de responsabilidades en servicios especializados

    WORKFLOWS DISPONIBLES:
    1. BUSQUEDA_HORARIOS - Búsqueda optimizada de horarios disponibles
    2. AGENDA_COMPLETA - Agendamiento completo con notificaciones automáticas
    3. ACTUALIZACION_COMPLETA - Actualización de eventos con notificaciones
    4. CANCELACION_WORKFLOW - Cancelación con notificaciones automáticas
    5. COMUNICACION_EVENTO - Consulta de información de eventos

    PARÁMETROS:
    - workflow_type: str (requerido) - Tipo de operación
    - title: str - Descripción de la cita
    - start_datetime: str (ISO) - Fecha/hora inicio para agendar
    - end_datetime: str (ISO) - Fecha/hora fin (opcional)
    - specific_date: str (YYYY-MM-DD) - Fecha específica para búsqueda (opcional)
    - attendee_email: str - Email del cliente
    - attendee_name: str - Nombre del cliente (opcional)
    - attendee_phone: str - Teléfono del cliente (opcional)
    - description: str - Descripción adicional (opcional)
    - event_id: str - ID del evento (para actualizar/cancelar/consultar)
    - conversation_summary: str - Resumen de conversación (opcional)

    MEJORAS DE ESTA VERSIÓN:
    -  Servicios especializados (Calendar, Notification, Contact, Workflow)
    -  Validación robusta con auditoría de seguridad
    -  Operaciones asíncronas optimizadas
    -  Cache thread-safe para prevenir race conditions
    -  Retry automático con backoff exponencial
    -  Manejo de errores estructurado sin fallos silenciosos
    -  Logging estructurado para debugging y monitoring
    """
    
    def __init__(self, project_id: str = None, project=None, user_id: str = None, **kwargs):
        # Primero inicializar la clase padre
        super().__init__(**kwargs)
        
        # Validación de parámetros de inicialización
        self._security_audit = SecurityAuditLogger()
        
        # Validar y sanitizar parámetros
        if project_id:
            validation_result = InputValidator.validate_project_id(project_id)
            if not validation_result.is_valid:
                self._security_audit.log_validation_failure("project_id", validation_result.error_code, validation_result.error_message)
                raise ValueError(f"Invalid project_id: {validation_result.error_message}")
            self._project_id = validation_result.sanitized_value
        else:
            self._project_id = project_id
        
        if user_id:
            validation_result = InputValidator.validate_user_id(user_id)
            if not validation_result.is_valid:
                self._security_audit.log_validation_failure("user_id", validation_result.error_code, validation_result.error_message)
                raise ValueError(f"Invalid user_id: {validation_result.error_message}")
            self._user_id = validation_result.sanitized_value
        else:
            self._user_id = user_id
            
        self._project = project
        
        # Estado interno
        self._initialized = True
        self.logger = logging.getLogger(__name__)
        
        # Inicializar servicios especializados (después de super().__init__)
        self._init_services()
    
    def _init_services(self):
        """Inicializa los servicios especializados de forma segura."""
        try:
            self._workflow_manager = WorkflowManager()
            self._calendar_service = CalendarService()
            
            # Obtener configuración de agenda para NotificationService
            agenda_config = self._get_agenda_config()
            self._notification_service = NotificationService(cached_project_config=agenda_config)
            
            self._contact_manager = ContactManager()
            self.logger.info("Servicios especializados inicializados correctamente")
        except Exception as e:
            self.logger.error(f"Error inicializando servicios: {str(e)}")
            raise
    
    @property
    def workflow_manager(self):
        """Getter para workflow_manager."""
        return getattr(self, '_workflow_manager', None)
    
    @property
    def calendar_service(self):
        """Getter para calendar_service."""
        return getattr(self, '_calendar_service', None)
    
    @property
    def notification_service(self):
        """Getter para notification_service."""
        return getattr(self, '_notification_service', None)
    
    @property
    def contact_manager(self):
        """Getter para contact_manager."""
        return getattr(self, '_contact_manager', None)
    
    @property
    def project_id(self):
        return getattr(self, '_project_id', None)
    
    @property 
    def project(self):
        return getattr(self, '_project', None)
    
    @property
    def user_id(self):
        return getattr(self, '_user_id', None)
    
    def _run(self,
            workflow_type: str,
            title: Optional[str] = None,
            start_datetime: Optional[str] = None,
            end_datetime: Optional[str] = None,
            specific_date: Optional[str] = None,
            attendee_email: Optional[str] = None,
            attendee_name: Optional[str] = None,
            attendee_phone: Optional[str] = None,
            description: Optional[str] = None,
            event_id: Optional[str] = None,
            conversation_summary: Optional[str] = None,
            **kwargs) -> str:
        """
        Ejecuta workflow de agenda de forma síncrona.
        Convierte llamada síncrona en asíncrona para compatibilidad con LangChain.
        """
        try:
            # Ejecutar de forma asíncrona
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._arun(
                        workflow_type=workflow_type,
                        title=title,
                        start_datetime=start_datetime,
                        end_datetime=end_datetime,
                        specific_date=specific_date,
                        attendee_email=attendee_email,
                        attendee_name=attendee_name,
                        attendee_phone=attendee_phone,
                        description=description,
                        event_id=event_id,
                        conversation_summary=conversation_summary,
                        **kwargs
                    )
                )
                return result
            finally:
                loop.close()
                
        except Exception as e:
            self.logger.error(f"Error en _run: {str(e)}")
            return f" Error ejecutando workflow: {str(e)}"
    
    async def _arun(self,
                   workflow_type: str,
                   title: Optional[str] = None,
                   start_datetime: Optional[str] = None,
                   end_datetime: Optional[str] = None,
                   specific_date: Optional[str] = None,
                   attendee_email: Optional[str] = None,
                   attendee_name: Optional[str] = None,
                   attendee_phone: Optional[str] = None,
                   description: Optional[str] = None,
                   event_id: Optional[str] = None,
                   conversation_summary: Optional[str] = None,
                   **kwargs) -> str:
        """
        Ejecuta workflow de agenda de forma asíncrona.
        Implementación con servicios especializados y validación robusta.
        """
        try:
            self.logger.info(f" Iniciando workflow refactorizado: {workflow_type}")
            
            # PASO 1: Validación robusta de entrada
            validated_params = await self._validate_and_sanitize_inputs(
                workflow_type=workflow_type,
                title=title,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                specific_date=specific_date,
                attendee_email=attendee_email,
                attendee_name=attendee_name,
                attendee_phone=attendee_phone,
                description=description,
                event_id=event_id,
                conversation_summary=conversation_summary
            )
            
            # PASO 2: Crear contexto de workflow
            context = WorkflowContext(
                user_id=self.user_id or "unknown",
                project_id=self.project_id or "unknown",
                project=self.project
            )
            
            # PASO 3: Ejecutar workflow usando WorkflowManager
            workflow_result = await self.workflow_manager.execute_workflow(
                workflow_type=validated_params['workflow_type'],
                context=context,
                parameters=validated_params
            )
            
            # PASO 4: Formatear respuesta para usuario
            response = self._format_workflow_response(workflow_result)
            
            self.logger.info(f" Workflow {workflow_type} completado exitosamente")
            return response
            
        except Exception as e:
            self.logger.error(f" Error en workflow {workflow_type}: {str(e)}")
            
            # Manejo de errores específico según tipo
            if "validation" in str(e).lower():
                return f" Error de validación: {str(e)}\n\n Verifica que todos los datos estén en el formato correcto."
            elif "authentication" in str(e).lower():
                return f" Error de autenticación: {str(e)}\n\n Verifica la configuración de Google Calendar."
            elif "network" in str(e).lower() or "timeout" in str(e).lower():
                return f" Error de conectividad: {str(e)}\n\n Verifica tu conexión a internet e intenta nuevamente."
            else:
                return f" Error inesperado: {str(e)}\n\n Si el problema persiste, contacta al soporte técnico."
    
    async def _validate_and_sanitize_inputs(self, **params) -> Dict[str, Any]:
        """
        Valida y sanitiza todos los parámetros de entrada.
        
        Returns:
            Diccionario con parámetros validados y sanitizados
        """
        validated = {}
        validation_errors = []
        
        # Validar workflow_type (requerido)
        workflow_type = params.get('workflow_type')
        if not workflow_type:
            validation_errors.append("workflow_type es requerido")
        else:
            workflow_validation = InputValidator.validate_workflow_type(workflow_type)
            if not workflow_validation.is_valid:
                validation_errors.append(f"workflow_type: {workflow_validation.error_message}")
                self._security_audit.log_validation_failure("workflow_type", workflow_validation.error_code, workflow_validation.error_message, self.user_id, self.project_id)
            else:
                validated['workflow_type'] = workflow_validation.sanitized_value
        
        # Validar parámetros opcionales
        optional_text_params = {
            'title': 200,
            'description': 1000,
            'attendee_name': 100,
            'attendee_phone': 20,
            'conversation_summary': 2000
        }
        
        for param_name, max_length in optional_text_params.items():
            value = params.get(param_name)
            if value is not None:
                text_validation = InputValidator.validate_text_input(value, param_name, max_length)
                if not text_validation.is_valid:
                    validation_errors.append(f"{param_name}: {text_validation.error_message}")
                    self._security_audit.log_validation_failure(param_name, text_validation.error_code, text_validation.error_message, self.user_id, self.project_id)
                else:
                    validated[param_name] = text_validation.sanitized_value
        
        # Validar email si se proporciona
        attendee_email = params.get('attendee_email')
        if attendee_email is not None:
            email_validation = InputValidator.validate_email(attendee_email)
            if not email_validation.is_valid:
                validation_errors.append(f"attendee_email: {email_validation.error_message}")
                self._security_audit.log_validation_failure("attendee_email", email_validation.error_code, email_validation.error_message, self.user_id, self.project_id)
            else:
                validated['attendee_email'] = email_validation.sanitized_value
        
        # Validar fechas si se proporcionan
        for date_param in ['start_datetime', 'end_datetime', 'specific_date']:
            value = params.get(date_param)
            if value is not None:
                datetime_validation = InputValidator.validate_datetime(value, date_param)
                if not datetime_validation.is_valid:
                    validation_errors.append(f"{date_param}: {datetime_validation.error_message}")
                    self._security_audit.log_validation_failure(date_param, datetime_validation.error_code, datetime_validation.error_message, self.user_id, self.project_id)
                else:
                    validated[date_param] = datetime_validation.sanitized_value
        
        # Validar event_id si se proporciona
        event_id = params.get('event_id')
        if event_id is not None:
            event_id_validation = InputValidator.validate_event_id(event_id)
            if not event_id_validation.is_valid:
                validation_errors.append(f"event_id: {event_id_validation.error_message}")
                self._security_audit.log_validation_failure("event_id", event_id_validation.error_code, event_id_validation.error_message, self.user_id, self.project_id)
            else:
                validated['event_id'] = event_id_validation.sanitized_value
        
        # Si hay errores de validación, lanzar excepción
        if validation_errors:
            error_msg = "Errores de validación detectados: " + "; ".join(validation_errors)
            self.logger.error(f"Validación fallida: {validation_errors}")
            raise_calendar_error(
                error_msg,
                ErrorCategory.VALIDATION,
                ErrorSeverity.MEDIUM,
                "VALIDATION_FAILED",
                validation_errors=validation_errors
            )
        
        return validated
    
    def _format_workflow_response(self, workflow_result: Dict[str, Any]) -> str:
        """
        Formatea el resultado del workflow para presentación al usuario.
        
        Args:
            workflow_result: Resultado del workflow manager
            
        Returns:
            Respuesta formateada para el usuario
        """
        if not workflow_result.get('success', False):
            error = workflow_result.get('error', 'Error desconocido')
            workflow_type = workflow_result.get('workflow_type', 'unknown')
            return f" Error en {workflow_type}: {error}"
        
        workflow_type = workflow_result.get('workflow_type', '')
        
        if workflow_type == 'BUSQUEDA_HORARIOS':
            # Usar el texto de resultado directo del workflow manager
            result_text = workflow_result.get('result_text', '')
            if result_text:
                return result_text
            
            # Fallback: formato manual si no hay result_text
            slots = workflow_result.get('slots', [])
            if not slots:
                return "No se encontraron horarios disponibles en el rango solicitado. Intenta con fechas diferentes o una duración más corta."
            
            response = "**Horarios disponibles encontrados:**\n\n"
            # No limitar aquí - el WorkflowManager ya aplicó el límite inteligente y filtros de preferencia
            for i, slot in enumerate(slots, 1):
                response += f"{i}. {slot.get('time_text', 'Horario disponible')}\n"
            
            # Agregar información sobre configuración de límites si está disponible en el resultado
            if workflow_result.get('limited_results', False):
                response += f"\n📋 *Mostrando los primeros {len(slots)} horarios según configuración.*"
                response += " *Para ver más opciones, solicita 'todos los horarios disponibles'.*"
            
            return response
        
        elif workflow_type == 'AGENDA_COMPLETA':
            # Verificar si es una cita duplicada
            if workflow_result.get('is_duplicate', False):
                return " ✅ **La cita ya fue agendada anteriormente**\n\n No se realizaron cambios duplicados."
            
            event_url = workflow_result.get('event_url', '')
            meet_url = workflow_result.get('meet_url', '')
            
            response = " **Cita agendada exitosamente**\n\n"
            response += " Se ha enviado confirmación por email\n"
            
            if meet_url:
                response += f" Google Meet: {meet_url}\n"
            
            if event_url:
                response += f" Ver en calendario: {event_url}\n"
            
            return response
        
        elif workflow_type == 'ACTUALIZACION_COMPLETA':
            return " **Evento actualizado exitosamente**\n\n Se han enviado notificaciones de la actualización"
        
        elif workflow_type == 'CANCELACION_WORKFLOW':
            return " **Evento cancelado exitosamente**\n\n Se han enviado notificaciones de cancelación"
        
        elif workflow_type == 'COMUNICACION_EVENTO':
            event_data = workflow_result.get('event_data', {})
            response = " **Información del evento:**\n\n"
            
            for key, value in event_data.items():
                if value:
                    response += f"• {key.replace('_', ' ').title()}: {value}\n"
            
            return response
        
        else:
            return f" Workflow {workflow_type} completado exitosamente"
    
    async def cleanup(self):
        """Limpia recursos de los servicios."""
        try:
            if hasattr(self, '_notification_service') and self._notification_service:
                await self._notification_service.cleanup()
            
            self.logger.info("AgendaTool cleanup completado")
        except Exception as e:
            self.logger.error(f"Error en cleanup: {str(e)}")
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la herramienta y servicios."""
        stats = {
            'tool': 'AgendaTool',
            'initialized': getattr(self, '_initialized', False),
            'project_id': self.project_id,
            'user_id': self.user_id
        }
        
        # Agregar estadísticas de servicios
        try:
            if hasattr(self, '_workflow_manager') and self._workflow_manager:
                stats['workflow_stats'] = self._workflow_manager.get_workflow_stats()
            
            if hasattr(self, '_notification_service') and self._notification_service:
                stats['notification_stats'] = self._notification_service.get_notification_stats()
            
            if hasattr(self, '_contact_manager') and self._contact_manager:
                stats['contact_stats'] = self._contact_manager.get_contact_stats()
                
        except Exception as e:
            stats['stats_error'] = str(e)
        
        return stats
    
    def _get_agenda_config(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene la configuración de la agenda desde la base de datos.
        
        Returns:
            Configuración de agenda o None si no se encuentra
        """
        try:
            if not self._project_id:
                self.logger.warning("No se puede obtener configuración de agenda sin project_id")
                return None
                
            from app.controler.chat.store.supabase_client import SupabaseClient
            supabase_client = SupabaseClient()
            response = supabase_client.client.table("agenda").select("*").eq("project_id", self._project_id).execute()
            
            if response.data and len(response.data) > 0:
                agenda_config = response.data[0]
                self.logger.info(f"📋 Configuración de agenda obtenida para project_id: {self._project_id}")
                return agenda_config
            else:
                self.logger.warning(f"📋 No se encontró configuración de agenda para project_id: {self._project_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error obteniendo configuración de agenda: {str(e)}")
            return None

# Función de conveniencia para crear la herramienta
def create_agenda_tool(project_id: str = None, project=None, user_id: str = None) -> AgendaTool:
    """
    Crea una instancia de AgendaTool.
    
    Args:
        project_id: ID del proyecto
        project: Objeto proyecto
        user_id: ID del usuario
        
    Returns:
        Instancia configurada de AgendaTool
    """
    return AgendaTool(project_id=project_id, project=project, user_id=user_id)