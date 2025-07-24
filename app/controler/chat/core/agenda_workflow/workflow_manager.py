"""
Gestor de workflows de agenda especializado y optimizado.
Maneja los diferentes flujos de trabajo de forma eficiente y escalable.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from enum import Enum

from app.controler.chat.core.security.input_validator import InputValidator, ValidationResult
from app.controler.chat.core.security.error_handler import safe_execute, raise_calendar_error, ErrorCategory, ErrorSeverity

logger = logging.getLogger(__name__)

class WorkflowType(Enum):
    """Tipos de workflow disponibles."""
    BUSQUEDA_HORARIOS = "BUSQUEDA_HORARIOS"
    AGENDA_COMPLETA = "AGENDA_COMPLETA"
    ACTUALIZACION_COMPLETA = "ACTUALIZACION_COMPLETA"
    CANCELACION_WORKFLOW = "CANCELACION_WORKFLOW"
    COMUNICACION_EVENTO = "COMUNICACION_EVENTO"

class WorkflowContext:
    """Contexto de ejecución de workflow."""
    
    def __init__(self, user_id: str, project_id: str, project: Any = None):
        self.user_id = user_id
        self.project_id = project_id
        self.project = project
        self.timestamp = datetime.now(timezone.utc)
        # Usar UUID para garantizar unicidad incluso en ejecuciones simultáneas
        self.execution_id = f"{project_id}_{user_id}_{int(self.timestamp.timestamp())}_{uuid.uuid4().hex[:8]}"

class WorkflowManager:
    """
    Gestor especializado de workflows de agenda.
    Responsabilidad única: coordinar los diferentes flujos de trabajo.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active_workflows: Dict[str, WorkflowContext] = {}
    
    
    def _personalize_event_title(self, original_title: str, agenda_config: Optional[Dict[str, Any]], parameters: Dict[str, Any]) -> str:
        """
        Personaliza el título del evento usando la configuración title_calendar_email.
        
        Args:
            original_title: Título original proporcionado por el usuario
            agenda_config: Configuración de agenda desde la base de datos
            parameters: Parámetros del workflow con datos del contacto
            
        Returns:
            Título personalizado o título original si no hay configuración
        """
        if not agenda_config:
            return original_title
        
        # Obtener configuración de título personalizado
        general_settings = agenda_config.get('general_settings', {})
        title_template = general_settings.get('title_calendar_email')
        
        if not title_template:
            return original_title
        
        # Preparar datos para reemplazar placeholders
        contact_name = parameters.get('attendee_name', 'Cliente')
        contact_email = parameters.get('attendee_email', '')
        contact_phone = parameters.get('attendee_phone', '')
        
        # Obtener nombre de la empresa
        company_info = general_settings.get('company_info', {})
        company_name = company_info.get('name', '') if isinstance(company_info, dict) else ''
        
        # Reemplazar placeholders
        personalized_title = title_template
        personalized_title = personalized_title.replace('{contact_name}', contact_name)
        personalized_title = personalized_title.replace('{contact_email}', contact_email)
        personalized_title = personalized_title.replace('{contact_phone}', contact_phone)
        personalized_title = personalized_title.replace('{company_name}', company_name)
        personalized_title = personalized_title.replace('{original_title}', original_title)
        
        self.logger.info(f"📝 Título personalizado: '{original_title}' → '{personalized_title}'")
        return personalized_title
    
    def _should_exclude_date(self, date_obj: datetime, search_config: Dict[str, Any]) -> bool:
        """
        Determina si una fecha debe ser excluida basándose en la configuración.
        
        Args:
            date_obj: Fecha a evaluar
            search_config: Configuración de búsqueda
            
        Returns:
            True si la fecha debe ser excluida, False si es válida
        """
        # Los fines de semana ya están manejados por la configuración de working_days
        # No necesitamos un filtro adicional de exclude_weekends
        
        # Verificar si es feriado y exclude_holidays está activo
        if search_config.get('exclude_holidays', True):
            try:
                # Usar la herramienta de feriados chilenos existente
                from app.controler.chat.core.tools.datetime_tool import is_chile_holiday
                
                if is_chile_holiday(date_obj.date()):
                    self.logger.debug(f"📅 Excluyendo día feriado: {date_obj.strftime('%Y-%m-%d')}")
                    return True
            except Exception as e:
                self.logger.warning(f"Error verificando feriados para {date_obj.date()}: {str(e)}")
        
        return False
    
    def _get_search_date_range(self, start_date: datetime, search_config: Dict[str, Any]) -> datetime:
        """
        Calcula la fecha límite de búsqueda basándose en search_weeks_ahead.
        
        Args:
            start_date: Fecha de inicio de búsqueda
            search_config: Configuración de búsqueda
            
        Returns:
            Fecha límite de búsqueda
        """
        weeks_ahead = search_config.get('search_weeks_ahead', 3)
        end_date = start_date + timedelta(weeks=weeks_ahead)
        
        self.logger.info(f"📅 Rango de búsqueda: {start_date.strftime('%Y-%m-%d')} hasta {end_date.strftime('%Y-%m-%d')} ({weeks_ahead} semanas)")
        return end_date
    
    async def execute_workflow(self, 
                             workflow_type: str,
                             context: WorkflowContext,
                             parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta un workflow específico con contexto y parámetros validados.
        
        Args:
            workflow_type: Tipo de workflow a ejecutar
            context: Contexto de ejecución
            parameters: Parámetros del workflow
            
        Returns:
            Resultado del workflow
        """
        # Validar tipo de workflow
        workflow_validation = InputValidator.validate_workflow_type(workflow_type)
        if not workflow_validation.is_valid:
            raise_calendar_error(
                f"Tipo de workflow inválido: {workflow_validation.error_message}",
                ErrorCategory.VALIDATION,
                ErrorSeverity.MEDIUM,
                "INVALID_WORKFLOW_TYPE"
            )
        
        workflow_enum = WorkflowType(workflow_validation.sanitized_value)
        
        # Registrar workflow activo
        self.active_workflows[context.execution_id] = context
        
        try:
            self.logger.info(f"Ejecutando workflow {workflow_enum.value} para user {context.user_id}")
            
            if workflow_enum == WorkflowType.BUSQUEDA_HORARIOS:
                return await self._execute_busqueda_horarios(context, parameters)
            elif workflow_enum == WorkflowType.AGENDA_COMPLETA:
                return await self._execute_agenda_completa(context, parameters)
            elif workflow_enum == WorkflowType.ACTUALIZACION_COMPLETA:
                return await self._execute_actualizacion_completa(context, parameters)
            elif workflow_enum == WorkflowType.CANCELACION_WORKFLOW:
                return await self._execute_cancelacion_workflow(context, parameters)
            elif workflow_enum == WorkflowType.COMUNICACION_EVENTO:
                return await self._execute_comunicacion_evento(context, parameters)
            else:
                raise_calendar_error(
                    f"Workflow {workflow_enum.value} no implementado",
                    ErrorCategory.BUSINESS_LOGIC,
                    ErrorSeverity.HIGH,
                    "WORKFLOW_NOT_IMPLEMENTED"
                )
        finally:
            # Limpiar workflow activo
            self.active_workflows.pop(context.execution_id, None)
    
    async def _execute_busqueda_horarios(self, context: WorkflowContext, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta workflow de búsqueda de horarios disponibles.
        IMPORTANTÍSIMO: NO crear nueva instancia de AgendaTool para evitar recursión infinita.
        """
        # Usar directamente los servicios especializados sin crear otra instancia de AgendaTool
        
        # Validar parámetros específicos de búsqueda
        title = parameters.get('title', '')
        start_datetime = parameters.get('start_datetime', '')
        specific_date = parameters.get('specific_date', '')
        
        # PRIORIZAR specific_date sobre start_datetime para búsquedas de fechas específicas
        target_date = specific_date or start_datetime or None
        
        # Si no hay target_date pero el título contiene información de fecha específica, extraerla
        if not target_date and title:
            target_date = self._extract_date_from_title(title)
        
        # CRÍTICO: Validar consistencia de fechas especificadas, pero permitir fechas futuras específicas
        if target_date and any(day in title.lower() for day in ["miércoles", "jueves", "viernes", "lunes", "martes"]):
            import re
            from datetime import datetime
            import pytz
            
            try:
                # Extraer fecha del target_date
                if target_date:
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', str(target_date))
                    if date_match:
                        date_str = date_match.group(1)
                        parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
                        
                        # Solo validar que la fecha no sea en el pasado
                        now = datetime.now(pytz.timezone('America/Santiago'))
                        if parsed_date.date() < now.date():
                            self.logger.warning(f"Fecha en el pasado detectada: {date_str}, usando fecha actual como referencia")
                            # Solo corregir si está en el pasado, pero permitir fechas futuras específicas
                        else:
                            self.logger.info(f"Fecha válida especificada: {date_str} ({['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'][parsed_date.weekday()]})")
            except Exception as date_fix_error:
                self.logger.warning(f"Error validando fecha: {date_fix_error}")
        
        try:
            self.logger.info(f"Executing BUSQUEDA_HORARIOS workflow with title: {title}, start_datetime: {start_datetime}, specific_date: {specific_date}, target_date: {target_date}")
            
            if target_date:
                self.logger.info(f"Using extracted/provided target_date: {target_date} for calendar search")
            
            # Implementar la búsqueda de horarios directamente usando CalendarService
            from app.controler.chat.core.agenda_workflow.calendar_service import CalendarService
            calendar_service = CalendarService()
            
            # Obtener configuración completa de búsqueda desde tabla agenda (incluye duración)
            search_config = await self._get_search_configuration(context.project_id)
            
            # Buscar horarios disponibles con filtros de configuración
            available_slots = await calendar_service.find_available_slots(
                project_id=context.project_id,
                user_id=context.user_id,
                title=title,
                specific_date=target_date,  # Ahora incluirá la fecha extraída del título
                duration_hours=search_config['default_duration_hours'],  # duración desde configuración
                project=context.project,  # Para compatibilidad temporal hasta migración completa
                search_config=search_config  # Pasar configuración de filtros
            )
            
            if available_slots:
                self.logger.info(f"Workflow BUSQUEDA_HORARIOS completado exitosamente: {len(available_slots)} slots encontrados")
                
                # Formatear horarios específicos para mostrar al usuario
                formatted_slots = "**Horarios disponibles encontrados:**\n\n"
                # Mostrar todos los horarios disponibles del día
                for i, slot in enumerate(available_slots, 1):
                    time_text = slot.get('time_text', 'Horario disponible')
                    formatted_slots += f"{i}. **{time_text}**\n"
                
                formatted_slots += f"\nPor favor, indícame cuál de estos {len(available_slots)} horarios prefieres para agendar la cita."
                
                return {
                    'success': True,
                    'workflow_type': WorkflowType.BUSQUEDA_HORARIOS.value,
                    'slots': available_slots,
                    'execution_id': context.execution_id,
                    'timestamp': context.timestamp.isoformat(),
                    'result_text': formatted_slots
                }
            else:
                self.logger.info("Workflow BUSQUEDA_HORARIOS completado exitosamente: 0 slots encontrados")
                return {
                    'success': True,
                    'workflow_type': WorkflowType.BUSQUEDA_HORARIOS.value,
                    'slots': [],
                    'execution_id': context.execution_id,
                    'timestamp': context.timestamp.isoformat(),
                    'result_text': "No se encontraron horarios disponibles en el rango solicitado. Intenta con fechas diferentes o una duración más corta."
                }
            
        except Exception as e:
            self.logger.error(f"Error en workflow búsqueda horarios: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'workflow_type': WorkflowType.BUSQUEDA_HORARIOS.value,
                'execution_id': context.execution_id,
                'result_text': f"Error en la búsqueda de horarios: {str(e)}"
            }
    
    def _parse_agenda_tool_slots(self, result_text: str) -> List[Dict[str, Any]]:
        """Parsea slots del resultado de AgendaTool."""
        slots = []
        
        # Buscar diferentes formatos de respuesta del AgendaTool
        if "📅 **Horarios disponibles" in result_text or "Horarios disponibles" in result_text:
            lines = result_text.split('\n')
            for line in lines:
                line = line.strip()
                # Formato 1: "1. Lunes 14 De Julio De 2025 a las 09:00 horas"
                if line and line[0].isdigit() and '. ' in line:
                    time_text = line.split('. ', 1)[1] if '. ' in line else line
                    slots.append({
                        'time_text': time_text,
                        'available': True
                    })
                # Formato 2: Líneas que contienen horarios directamente
                elif any(time_word in line.lower() for time_word in ['horas', 'am', 'pm', ':']) and any(day in line.lower() for day in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']):
                    slots.append({
                        'time_text': line,
                        'available': True
                    })
        
        # Si no se encontraron slots con el formato esperado, pero hay contenido de horarios
        if not slots and ("disponible" in result_text.lower() or "horario" in result_text.lower()):
            # Logging para debug
            self.logger.warning(f"No se pudieron parsear slots del resultado: {result_text[:200]}...")
        
        self.logger.info(f"Slots parseados: {len(slots)} encontrados")
        for i, slot in enumerate(slots):
            self.logger.info(f"  Slot {i+1}: {slot['time_text']}")
        
        return slots
    
    async def _get_search_configuration(self, project_id: str) -> Dict[str, Any]:
        """
        Obtiene todas las configuraciones de BUSQUEDA_HORARIOS y AGENDA_COMPLETA desde la tabla agenda.
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Diccionario con configuraciones de búsqueda o valores por defecto
        """
        default_config = {
            'exclude_holidays': True,
            'search_weeks_ahead': 3,
            'default_duration_hours': 1.0  # fallback
        }
        
        try:
            from app.controler.chat.store.supabase_client import SupabaseClient
            supabase_client = SupabaseClient()
            response = supabase_client.client.table("agenda").select("workflow_settings").eq("project_id", project_id).execute()
            
            if response.data and len(response.data) > 0:
                agenda_config = response.data[0]
                workflow_settings = agenda_config.get('workflow_settings', {})
                busqueda_settings = workflow_settings.get('BUSQUEDA_HORARIOS', {})
                agenda_completa_settings = workflow_settings.get('AGENDA_COMPLETA', {})
                
                # Combinar configuración con valores por defecto
                config = default_config.copy()
                config.update(busqueda_settings)
                
                # Obtener duración desde AGENDA_COMPLETA
                default_duration_minutes = agenda_completa_settings.get('default_duration_minutes', 60)
                config['default_duration_hours'] = default_duration_minutes / 60.0
                
                self.logger.info(f"🔍 Configuración completa obtenida: {config}")
                return config
            else:
                self.logger.warning(f"No se encontró configuración para project_id: {project_id}, usando valores por defecto")
                return default_config
                
        except Exception as e:
            self.logger.error(f"Error obteniendo configuración de búsqueda: {str(e)}")
            return default_config
    
    async def _get_agenda_configuration(self, project_id: str) -> Dict[str, Any]:
        """Obtiene configuración de agenda desde base de datos con cache."""
        try:
            from app.controler.chat.store.supabase_client import SupabaseClient
            supabase_client = SupabaseClient()
            response = supabase_client.client.table("agenda").select("*").eq("project_id", project_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            else:
                self.logger.warning(f"No se encontró configuración de agenda para project_id: {project_id}")
                return {}
        except Exception as e:
            self.logger.error(f"Error obteniendo configuración de agenda: {str(e)}")
            return {}

    def _calculate_event_duration(self, parameters: Dict[str, Any], agenda_settings: Dict[str, Any]) -> None:
        """Calcula la duración del evento usando la configuración."""
        if not parameters.get('start_datetime'):
            return
            
        duration_minutes = agenda_settings.get('default_duration_minutes', 60)
        self.logger.info(f"🕐 Duración configurada: {duration_minutes} minutos")
        self.logger.info(f"🕐 Start datetime: {parameters.get('start_datetime')}")
        
        from datetime import datetime, timedelta
        start_dt = datetime.fromisoformat(parameters['start_datetime'])
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        parameters['end_datetime'] = end_dt.isoformat()
        
        self.logger.info(f"🕐 End datetime calculado: {parameters['end_datetime']}")
        self.logger.info(f"🕐 Horario final: {parameters['start_datetime']} - {parameters['end_datetime']}")

    async def _prepare_contact_data(self, context: WorkflowContext, parameters: Dict[str, Any], 
                                   contact_manager, attendee_email: str) -> Dict[str, Any]:
        """Prepara datos de contacto combinando parámetros y base de datos."""
        # Datos base de parámetros
        contact_data = {
            'email': attendee_email,
            'name': parameters.get('attendee_name', ''),
            'phone': parameters.get('attendee_phone', ''),
            'phone_number': parameters.get('attendee_phone', '')  # Para compatibilidad
        }
        
        # Si hay email, enriquecer con datos de base de datos
        if attendee_email:
            try:
                stored_contact = await contact_manager.get_contact(context.user_id, context.project_id)
                
                if stored_contact:
                    # Actualizar campos básicos
                    contact_data.update({
                        'name': stored_contact.get('name', contact_data['name']),
                        'phone': stored_contact.get('phone_number', contact_data['phone']),
                        'phone_number': stored_contact.get('phone_number', contact_data['phone_number']),
                        'email': stored_contact.get('email', contact_data['email'])
                    })
                    
                    # Incluir additional_fields si existen
                    additional_fields = stored_contact.get('additional_fields')
                    if additional_fields:
                        if isinstance(additional_fields, str):
                            try:
                                import json
                                additional_fields = json.loads(additional_fields)
                            except json.JSONDecodeError:
                                self.logger.warning(f"Error parseando additional_fields JSON: {additional_fields}")
                                additional_fields = {}
                        
                        if isinstance(additional_fields, dict):
                            contact_data.update(additional_fields)
                            self.logger.info(f"📞 Additional_fields incluidos: {list(additional_fields.keys())}")
                    
                    self.logger.info(f"📞 Datos de contacto obtenidos desde DB: phone={contact_data['phone']}, name={contact_data['name']}")
                else:
                    self.logger.warning(f"📞 No se encontró contacto almacenado para user_id={context.user_id}")
            except Exception as e:
                self.logger.error(f"Error obteniendo datos de contacto: {str(e)}")
        
        return contact_data

    async def _add_event_attendees(self, calendar_service, event_id: str, parameters: Dict[str, Any], 
                                  calendar_owner_email: str, context: WorkflowContext) -> None:
        """Agrega attendees al evento después de crearlo."""
        attendees_to_add = []
        
        # Agregar email del cliente si existe
        if parameters.get('attendee_email'):
            attendees_to_add.append(('cliente', parameters['attendee_email']))
        
        # SIEMPRE agregar al dueño de la agenda
        if calendar_owner_email:
            attendees_to_add.append(('dueño', calendar_owner_email))
            self.logger.info(f"📧 Agregando al dueño como attendee: {calendar_owner_email}")
        
        # Enviar invitaciones a todos los emails
        for email_type, email in attendees_to_add:
            try:
                result = await calendar_service.add_attendee_to_event(
                    event_id=event_id,
                    attendee_email=email,
                    project_id=context.project_id,
                    project=context.project
                )
                if result.get('success'):
                    self.logger.info(f"📧 Invitación enviada exitosamente al {email_type}: {email}")
                else:
                    self.logger.error(f"📧 Error enviando invitación al {email_type} ({email}): {result.get('error')}")
            except Exception as invite_error:
                self.logger.error(f"📧 Excepción enviando invitación al {email_type} ({email}): {str(invite_error)}")
                # No fallar el workflow por error de invitación

    async def _execute_agenda_completa(self, context: WorkflowContext, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta workflow completo de agendamiento."""
        from .calendar_service import CalendarService
        from .notification_service import NotificationService
        from .contact_manager import ContactManager
        
        # 1. Obtener configuración
        agenda_config = await self._get_agenda_configuration(context.project_id)
        workflow_settings = agenda_config.get('workflow_settings', {})
        agenda_completa_settings = workflow_settings.get('AGENDA_COMPLETA', {})
        general_settings = agenda_config.get('general_settings', {})
        
        # 2. Verificar si el email es requerido
        require_email = agenda_completa_settings.get('require_email', 
                      general_settings.get('require_attendee_email', True))
        self.logger.info(f"Configuración require_email desde AGENDA_COMPLETA: {require_email}")
        
        # 3. Validar parámetros requeridos
        required_params = ['title', 'start_datetime']
        if require_email:
            required_params.append('attendee_email')
        
        missing_params = [param for param in required_params if not parameters.get(param)]
        if missing_params:
            raise_calendar_error(
                f"Parámetros requeridos faltantes: {', '.join(missing_params)}",
                ErrorCategory.VALIDATION,
                ErrorSeverity.MEDIUM,
                "MISSING_REQUIRED_PARAMS"
            )
        
        # 4. Inicializar servicios
        calendar_service = CalendarService()
        notification_service = NotificationService(cached_project_config=agenda_config)
        contact_manager = ContactManager()
        
        # 5. Calcular duración usando configuración
        self._calculate_event_duration(parameters, agenda_completa_settings)
        
        try:

            # 1. Verificar disponibilidad
            conflicts = await calendar_service.check_conflicts(
                start_time=parameters['start_datetime'],
                end_time=parameters.get('end_datetime'),
                project_id=context.project_id,
                project=context.project
            )
            
            # Detectar si es un conflicto menor de timezone (auto-force para conflictos de timezone)
            auto_force_create = False
            if conflicts and not parameters.get('force_create', False):
                # Si hay exactamente 1 conflicto y parece ser diferencia de timezone, usar force_create automáticamente
                if len(conflicts) == 1:
                    conflict_summary = conflicts[0].get('message', '').lower()
                    if any(keyword in conflict_summary for keyword in ['timezone', 'nicolás', 'nicolas', 'videollamada']):
                        auto_force_create = True
                        self.logger.info(f"Detectado conflicto menor de timezone con '{conflicts[0].get('message', '')}', usando force_create automáticamente")
                
                if not auto_force_create:
                    return {
                        'success': False,
                        'error': 'Conflicto de horario detectado',
                        'conflicts': conflicts,
                        'workflow_type': WorkflowType.AGENDA_COMPLETA.value
                    }
            
            # 2. Determinar si incluir Google Meet basado en configuración del proyecto
            auto_include_meet = True  # Valor por defecto
            if agenda_config:
                general_settings = agenda_config.get('general_settings', {})
                auto_include_meet = general_settings.get('auto_include_meet', True)
                self.logger.info(f"📅 Configuración auto_include_meet desde tabla agenda: {auto_include_meet}")
            else:
                self.logger.warning("📅 No hay configuración de agenda, usando auto_include_meet=True por defecto")
            
            # Permitir override explícito por parámetro (para casos especiales)
            include_meet_final = parameters.get('include_meet', auto_include_meet)
            self.logger.info(f"📅 include_meet final: {include_meet_final} (config: {auto_include_meet}, override: {parameters.get('include_meet', 'None')})")
            
            # 3. Personalizar título del evento usando configuración title_calendar_email
            personalized_title = self._personalize_event_title(
                original_title=parameters['title'],
                agenda_config=agenda_config,
                parameters=parameters
            )
            
            # 4. Obtener email del dueño de la agenda ANTES de crear el evento
            calendar_owner_email = None
            
            try:
                from app.controler.chat.store.supabase_client import SupabaseClient
                supabase_client = SupabaseClient()
                integration_response = supabase_client.client.table("calendar_integrations").select("user_email").eq("project_id", context.project_id).eq("is_active", True).execute()
                
                if integration_response.data and len(integration_response.data) > 0:
                    calendar_owner_email = integration_response.data[0].get('user_email', '')
                    self.logger.info(f"📧 Email del dueño para incluir en evento: {calendar_owner_email}")
            except Exception as e:
                self.logger.error(f"📧 Error obteniendo email del dueño: {str(e)}")
            
            # 5. Crear evento SIN attendees primero (como funcionaba antes)
            self.logger.info(f"📧 Creando evento sin attendees, luego agregando al dueño: {calendar_owner_email}")
            
            # 6. Crear evento SIN attendees (como funcionaba antes)
            event_result = await calendar_service.create_event(
                title=personalized_title,
                start_datetime=parameters['start_datetime'],
                end_datetime=parameters.get('end_datetime'),
                attendee_email='',  # SIN attendees durante la creación
                description=parameters.get('description', ''),
                include_meet=include_meet_final,
                force_create=bool(conflicts and (parameters.get('force_create', False) or auto_force_create)),
                project_id=context.project_id,
                project=context.project  # Para compatibilidad temporal hasta migración completa
            )
            
            if not event_result['success']:
                return event_result
            
            # 6. Actualizar contacto y preparar datos para notificaciones
            attendee_email = parameters.get('attendee_email', '')
            if attendee_email:  
                await contact_manager.update_or_create_contact(
                    user_id=context.user_id,
                    project_id=context.project_id,
                    email=attendee_email,
                    name=parameters.get('attendee_name', ''),
                    phone=parameters.get('attendee_phone', '')
                )
                self.logger.info(f"Contacto actualizado con email: {attendee_email}")
            else:
                self.logger.info("Cita creada para uso interno (sin email del cliente)")
            
            # 7. Preparar datos completos de contacto para notificaciones y webhook
            contact_data = await self._prepare_contact_data(context, parameters, contact_manager, attendee_email)
            
            # 8. Enviar notificaciones por email y webhook
            notifications_result = await notification_service.send_appointment_notifications(
                event_data=event_result['event_data'],
                contact_data=contact_data,
                project_id=context.project_id,
                user_id=context.user_id,
                conversation_summary=parameters.get('conversation_summary', '')
            )
            
            # Log del resultado del webhook desde las notificaciones
            if notifications_result:
                webhook_sent = notifications_result.get('webhook_sent', False)
                errors = notifications_result.get('errors', [])
                webhook_errors = [e for e in errors if e.startswith('webhook:')]
                
                if webhook_sent:
                    self.logger.info("📡 Workflow completado - webhook procesado")
                elif webhook_errors:
                    self.logger.warning(f"⚠️ Workflow completado - webhook falló: {webhook_errors[0]}")
                else:
                    self.logger.info("📡 Webhook no configurado - omitido")
            else:
                self.logger.warning("📡 No se recibió resultado de las notificaciones")
            
            # 9. Agregar attendees al evento (DESPUÉS de crear, como funcionaba antes)
            await self._add_event_attendees(calendar_service, event_result['event_id'], parameters, calendar_owner_email, context)
            
            
            
            return {
                'success': True,
                'workflow_type': WorkflowType.AGENDA_COMPLETA.value,
                'event_id': event_result['event_id'],
                'event_url': event_result.get('event_url'),
                'meet_url': event_result.get('meet_url'),
                'execution_id': context.execution_id,
                'timestamp': context.timestamp.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error en workflow agenda completa: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'workflow_type': WorkflowType.AGENDA_COMPLETA.value,
                'execution_id': context.execution_id
            }
    
    async def _execute_actualizacion_completa(self, context: WorkflowContext, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta workflow de actualización de evento."""
        from .calendar_service import CalendarService
        from .notification_service import NotificationService
        
        # Obtener configuración de agenda para el NotificationService
        agenda_config = None
        try:
            from app.controler.chat.store.supabase_client import SupabaseClient
            supabase_client = SupabaseClient()
            response = supabase_client.client.table("agenda").select("*").eq("project_id", context.project_id).execute()
            if response.data and len(response.data) > 0:
                agenda_config = response.data[0]
        except Exception as e:
            self.logger.error(f"Error obteniendo configuración de agenda: {str(e)}")
        
        calendar_service = CalendarService()
        notification_service = NotificationService(cached_project_config=agenda_config)
        
        event_id = parameters.get('event_id')
        if not event_id:
            raise_calendar_error(
                "event_id es requerido para actualización",
                ErrorCategory.VALIDATION,
                ErrorSeverity.MEDIUM,
                "MISSING_EVENT_ID"
            )
        
        try:
            # Actualizar evento
            update_result = await calendar_service.update_event(
                event_id=event_id,
                updates=parameters,
                project_id=context.project_id
            )
            
            if not update_result['success']:
                return update_result
            
            # Enviar notificaciones de actualización
            await notification_service.send_update_notifications(
                event_data=update_result['event_data'],
                project_id=context.project_id,
                user_id=context.user_id
            )
            
            return {
                'success': True,
                'workflow_type': WorkflowType.ACTUALIZACION_COMPLETA.value,
                'event_id': event_id,
                'execution_id': context.execution_id
            }
            
        except Exception as e:
            self.logger.error(f"Error en workflow actualización: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'workflow_type': WorkflowType.ACTUALIZACION_COMPLETA.value,
                'execution_id': context.execution_id
            }
    
    async def _execute_cancelacion_workflow(self, context: WorkflowContext, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta workflow de cancelación de evento."""
        from .calendar_service import CalendarService
        from .notification_service import NotificationService
        
        # Obtener configuración de agenda para el NotificationService
        agenda_config = None
        try:
            from app.controler.chat.store.supabase_client import SupabaseClient
            supabase_client = SupabaseClient()
            response = supabase_client.client.table("agenda").select("*").eq("project_id", context.project_id).execute()
            if response.data and len(response.data) > 0:
                agenda_config = response.data[0]
        except Exception as e:
            self.logger.error(f"Error obteniendo configuración de agenda: {str(e)}")
        
        calendar_service = CalendarService()
        notification_service = NotificationService(cached_project_config=agenda_config)
        
        event_id = parameters.get('event_id')
        if not event_id:
            raise_calendar_error(
                "event_id es requerido para cancelación",
                ErrorCategory.VALIDATION,
                ErrorSeverity.MEDIUM,
                "MISSING_EVENT_ID"
            )
        
        try:
            # Obtener datos del evento antes de cancelar
            event_data = await calendar_service.get_event(event_id, context.project_id)
            
            # Cancelar evento
            cancel_result = await calendar_service.delete_event(event_id, context.project_id)
            
            if not cancel_result['success']:
                return cancel_result
            
            # Enviar notificaciones de cancelación
            await notification_service.send_cancellation_notifications(
                event_data=event_data,
                project_id=context.project_id,
                user_id=context.user_id
            )
            
            return {
                'success': True,
                'workflow_type': WorkflowType.CANCELACION_WORKFLOW.value,
                'event_id': event_id,
                'execution_id': context.execution_id
            }
            
        except Exception as e:
            self.logger.error(f"Error en workflow cancelación: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'workflow_type': WorkflowType.CANCELACION_WORKFLOW.value,
                'execution_id': context.execution_id
            }
    
    async def _execute_comunicacion_evento(self, context: WorkflowContext, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta workflow de comunicación/consulta de evento."""
        from .calendar_service import CalendarService
        
        calendar_service = CalendarService()
        
        event_id = parameters.get('event_id')
        if not event_id:
            raise_calendar_error(
                "event_id es requerido para consulta",
                ErrorCategory.VALIDATION,
                ErrorSeverity.MEDIUM,
                "MISSING_EVENT_ID"
            )
        
        try:
            event_data = await calendar_service.get_event(event_id, context.project_id)
            
            return {
                'success': True,
                'workflow_type': WorkflowType.COMUNICACION_EVENTO.value,
                'event_data': event_data,
                'execution_id': context.execution_id
            }
            
        except Exception as e:
            self.logger.error(f"Error en workflow comunicación: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'workflow_type': WorkflowType.COMUNICACION_EVENTO.value,
                'execution_id': context.execution_id
            }
    
    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Obtiene workflows actualmente en ejecución."""
        return [
            {
                'execution_id': context.execution_id,
                'user_id': context.user_id,
                'project_id': context.project_id,
                'started_at': context.timestamp.isoformat()
            }
            for context in self.active_workflows.values()
        ]
    
    def _extract_date_from_title(self, title: str) -> Optional[str]:
        """
        Extrae fecha específica del título de la búsqueda.
        
        Args:
            title: Título que puede contener información de fecha
            
        Returns:
            Fecha en formato YYYY-MM-DD si se encuentra, None si no
        """
        if not title:
            return None
            
        try:
            import re
            from datetime import datetime, timedelta
            import pytz
            
            title_lower = title.lower()
            chile_tz = pytz.timezone('America/Santiago')
            now = datetime.now(chile_tz)
            
            # Mapeo de días a números de weekday (lunes=0, domingo=6)
            days_map = {
                'lunes': 0, 'martes': 1, 'miércoles': 2, 'jueves': 3, 
                'viernes': 4, 'sábado': 5, 'domingo': 6
            }
            
            # PRIORIDAD 1: Buscar fechas en formato ISO (YYYY-MM-DD) 
            iso_date_pattern = r'(\d{4}-\d{2}-\d{2})'
            iso_match = re.search(iso_date_pattern, title)
            
            if iso_match:
                iso_date = iso_match.group(1)
                try:
                    # Validar que la fecha sea válida
                    target_date = datetime.strptime(iso_date, '%Y-%m-%d')
                    self.logger.info(f"Fecha ISO extraída del título '{title}': {iso_date}")
                    return iso_date
                except ValueError as e:
                    self.logger.warning(f"Fecha ISO inválida: {iso_date}: {e}")
            
            # PRIORIDAD 2: Buscar patrones específicos con fechas exactas
            # Patrón: "jueves 17 de julio" o "miércoles 16 de julio de 2025"
            date_pattern = r'(\w+)\s+(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?'
            match = re.search(date_pattern, title_lower)
            
            if match:
                day_name = match.group(1)
                day_num = int(match.group(2))
                month_name = match.group(3)
                year = int(match.group(4)) if match.group(4) else now.year
                
                # Mapeo de meses
                months_map = {
                    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                }
                
                if month_name in months_map:
                    month_num = months_map[month_name]
                    try:
                        target_date = datetime(year, month_num, day_num)
                        self.logger.info(f"Fecha extraída del título '{title}': {target_date.strftime('%Y-%m-%d')}")
                        return target_date.strftime('%Y-%m-%d')
                    except ValueError as e:
                        self.logger.warning(f"Fecha inválida extraída: {year}-{month_num}-{day_num}: {e}")
            
            # PRIORIDAD 3: Buscar solo días de la semana (para fechas relativas)
            for day_name, weekday in days_map.items():
                if day_name in title_lower:
                    # Calcular la próxima ocurrencia de ese día
                    days_ahead = (weekday - now.weekday() + 7) % 7
                    if days_ahead == 0:  # Si es hoy, usar hoy
                        days_ahead = 0
                    target_date = now + timedelta(days=days_ahead)
                    self.logger.info(f"Día de semana extraído del título '{title}': {day_name} -> {target_date.strftime('%Y-%m-%d')}")
                    return target_date.strftime('%Y-%m-%d')
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extrayendo fecha del título '{title}': {str(e)}")
            return None

    def get_workflow_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de workflows."""
        return {
            'active_workflows': len(self.active_workflows),
            'workflow_types': list(WorkflowType.__members__.keys())
        }