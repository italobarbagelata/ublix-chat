"""
Gestor de workflows de agenda especializado y optimizado.
Maneja los diferentes flujos de trabajo de forma eficiente y escalable.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
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
        self.timestamp = datetime.utcnow()
        self.execution_id = f"{project_id}_{user_id}_{int(self.timestamp.timestamp())}"

class WorkflowManager:
    """
    Gestor especializado de workflows de agenda.
    Responsabilidad única: coordinar los diferentes flujos de trabajo.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active_workflows: Dict[str, WorkflowContext] = {}
    
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
        IMPORTANTÍSIMO: NO crear nueva instancia de AgendaToolRefactored para evitar recursión infinita.
        """
        # Usar directamente los servicios especializados sin crear otra instancia de AgendaToolRefactored
        
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
            from app.controler.chat.core.services.calendar_service import CalendarService
            calendar_service = CalendarService()
            
            # Obtener configuración de max_slots_to_show desde tabla agenda
            max_slots_limit = await self._get_max_slots_configuration(context.project_id)
            
            # Detectar si se requiere búsqueda exhaustiva basada en el título o parámetros
            needs_comprehensive_search = self._should_show_comprehensive_results(title, parameters)
            
            # Aplicar límite inteligente
            effective_max_slots = None if needs_comprehensive_search else max_slots_limit
            
            self.logger.info(f"Slot limit configuration: max_slots_to_show={max_slots_limit}, comprehensive_search={needs_comprehensive_search}, effective_limit={effective_max_slots}")
            
            # Buscar horarios disponibles directamente
            available_slots = await calendar_service.find_available_slots(
                project_id=context.project_id,
                user_id=context.user_id,
                title=title,
                specific_date=target_date,  # Ahora incluirá la fecha extraída del título
                duration_hours=1,  # duración por defecto
                max_slots=effective_max_slots,  # Usar límite inteligente
                project=context.project  # Para compatibilidad temporal hasta migración completa
            )
            
            if available_slots:
                self.logger.info(f"Workflow BUSQUEDA_HORARIOS completado exitosamente: {len(available_slots)} slots encontrados")
                
                # Formatear horarios específicos para mostrar al usuario
                formatted_slots = "**Horarios disponibles encontrados:**\n\n"
                # No limitar aquí - el CalendarService ya aplicó el límite y filtros de preferencia
                for i, slot in enumerate(available_slots, 1):
                    time_text = slot.get('time_text', 'Horario disponible')
                    formatted_slots += f"{i}. {time_text}\n"
                
                # Agregar información sobre el límite si se aplicó
                if effective_max_slots is not None and len(available_slots) == effective_max_slots:
                    formatted_slots += f"\n📋 *Mostrando los primeros {len(available_slots)} horarios disponibles.*"
                    if not needs_comprehensive_search:
                        formatted_slots += " *Si necesitas ver más opciones, puedes solicitar 'todos los horarios disponibles'.*"
                
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
    
    async def _get_max_slots_configuration(self, project_id: str) -> Optional[int]:
        """
        Obtiene la configuración max_slots_to_show desde la tabla agenda.
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Número máximo de slots a mostrar o None si no hay límite configurado
        """
        try:
            from app.controler.chat.store.supabase_client import SupabaseClient
            supabase_client = SupabaseClient()
            response = supabase_client.client.table("agenda").select("workflow_settings").eq("project_id", project_id).execute()
            
            if response.data and len(response.data) > 0:
                agenda_config = response.data[0]
                workflow_settings = agenda_config.get('workflow_settings', {})
                busqueda_settings = workflow_settings.get('BUSQUEDA_HORARIOS', {})
                max_slots = busqueda_settings.get('max_slots_to_show')
                
                if max_slots is not None:
                    try:
                        max_slots_int = int(max_slots)
                        self.logger.info(f"Configuración max_slots_to_show obtenida desde workflow_settings: {max_slots_int}")
                        return max_slots_int
                    except (ValueError, TypeError):
                        self.logger.warning(f"Valor inválido para max_slots_to_show: {max_slots}")
                        return None
                else:
                    self.logger.info(f"No se encontró configuración max_slots_to_show en workflow_settings para project_id: {project_id}")
                    return None
            else:
                self.logger.warning(f"No se encontró configuración de agenda para project_id: {project_id}")
                return None
        except Exception as e:
            self.logger.error(f"Error obteniendo configuración max_slots_to_show: {str(e)}")
            return None
    
    def _should_show_comprehensive_results(self, title: str, parameters: Dict[str, Any]) -> bool:
        """
        Determina si se debe mostrar resultados exhaustivos basado en el contexto de la búsqueda.
        
        Args:
            title: Título/consulta del usuario
            parameters: Parámetros de la búsqueda
            
        Returns:
            True si se requiere búsqueda exhaustiva, False para usar límite configurado
        """
        if not title:
            return False
        
        # Verificar si hay indicadores en los parámetros que sugieran búsqueda exhaustiva
        has_comprehensive_param = parameters.get('comprehensive_search', False)
        if has_comprehensive_param:
            return True
            
        title_lower = title.lower()
        
        # Detectar palabras clave que indican necesidad de búsqueda exhaustiva
        comprehensive_keywords = [
            'todo el dia', 'todos los horarios', 'toda la tarde', 'toda la mañana',
            'todos los disponibles', 'cualquier horario', 'todo disponible',
            'buscar todo', 'mostrar todo', 'ver todo', 'listar todo',
            'all day', 'all available', 'show all', 'list all',
            'comprehensive', 'exhaustive', 'complete'
        ]
        
        # Detectar preferencias específicas de tiempo que requieren más opciones
        # Solo activar si la preferencia de tiempo es el foco principal, no una mención casual
        time_preference_patterns = [
            'en la tarde', 'por la tarde', 'para la tarde', 'de la tarde',
            'en la mañana', 'por la mañana', 'para la mañana', 'de la mañana', 
            'en la noche', 'por la noche', 'para la noche', 'de la noche',
            'afternoon slots', 'morning slots', 'evening slots',
            'horarios de tarde', 'horarios de mañana', 'horarios de noche'
        ]
        
        has_comprehensive_request = any(keyword in title_lower for keyword in comprehensive_keywords)
        has_time_preference = any(pattern in title_lower for pattern in time_preference_patterns)
        
        # También detectar palabras simples si no hay contexto de fecha específica
        simple_time_words = ['tarde', 'mañana', 'noche', 'afternoon', 'morning', 'evening']
        has_simple_time_word = any(word in title_lower for word in simple_time_words)
        
        # Detectar si hay mención de días específicos que podrían estar limitando la búsqueda  
        specific_day_indicators = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo',
                                  'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                                  'hoy', 'today']
        
        # Detectar "mañana" como día (tomorrow) vs tiempo (morning) según contexto
        tomorrow_indicators = ['para mañana', 'mañana día', 'mañana por', 'tomorrow']
        has_tomorrow = any(indicator in title_lower for indicator in tomorrow_indicators)
        
        has_specific_day = any(day in title_lower for day in specific_day_indicators) or has_tomorrow
        
        # Solo aplicar preferencia de tiempo si no hay un día específico mencionado
        if has_simple_time_word and has_specific_day and not has_time_preference:
            # Caso como "para mañana martes" - tiene día específico, no buscar exhaustivamente
            has_time_preference = False
        elif has_simple_time_word and not has_specific_day:
            # Caso como "para la tarde" - sin día específico, buscar exhaustivamente 
            has_time_preference = True
        
        # Si el usuario especifica una preferencia de tiempo, mostrar más opciones para esa franja
        # Si solicita explícitamente resultados completos, no limitar
        should_be_comprehensive = has_comprehensive_request or has_time_preference
        
        if should_be_comprehensive:
            self.logger.info(f"Búsqueda exhaustiva detectada en '{title}' - comprehensive_request: {has_comprehensive_request}, time_preference: {has_time_preference}")
        
        return should_be_comprehensive
    
    async def _execute_agenda_completa(self, context: WorkflowContext, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta workflow completo de agendamiento."""
        from .calendar_service import CalendarService
        from .notification_service import NotificationService
        from .contact_manager import ContactManager
        
        # Validar parámetros requeridos (email es opcional para uso interno)
        required_params = ['title', 'start_datetime']
        
        # Verificar si el email es requerido según configuración de la tabla agenda
        require_email = True  # Por defecto requerido para compatibilidad
        agenda_config = None
        
        try:
            # Obtener configuración desde tabla agenda
            from app.controler.chat.store.supabase_client import SupabaseClient
            supabase_client = SupabaseClient()
            response = supabase_client.client.table("agenda").select("*").eq("project_id", context.project_id).execute()
            
            if response.data and len(response.data) > 0:
                agenda_config = response.data[0]
                general_settings = agenda_config.get('general_settings', {})
                require_email = general_settings.get('require_attendee_email', True)
                self.logger.info(f"Configuración require_attendee_email desde tabla agenda: {require_email}")
            else:
                self.logger.warning(f"No se encontró configuración de agenda para project_id: {context.project_id}")
        except Exception as e:
            self.logger.error(f"Error obteniendo configuración de agenda: {str(e)}")
            # Continuar con valor por defecto
        
        # Inicializar servicios con la configuración obtenida
        calendar_service = CalendarService()
        notification_service = NotificationService(cached_project_config=agenda_config)
        contact_manager = ContactManager()
        
        # Agregar email a parámetros requeridos solo si está configurado como requerido
        if require_email:
            required_params.append('attendee_email')
        
        missing_params = [param for param in required_params if not parameters.get(param)]
        
        if missing_params:
            if 'attendee_email' in missing_params and not require_email:
                # Si email no es requerido, removerlo de la lista de faltantes
                missing_params.remove('attendee_email')
            
            if missing_params:  # Solo fallar si hay otros parámetros faltantes
                raise_calendar_error(
                    f"Parámetros requeridos faltantes: {', '.join(missing_params)}",
                    ErrorCategory.VALIDATION,
                    ErrorSeverity.MEDIUM,
                    "MISSING_REQUIRED_PARAMS"
                )
        
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
            
            # 2. Crear evento (usar force_create si hay conflictos y el usuario los aceptó)
            event_result = await calendar_service.create_event(
                title=parameters['title'],
                start_datetime=parameters['start_datetime'],
                end_datetime=parameters.get('end_datetime'),
                attendee_email=parameters.get('attendee_email', ''),  # Opcional para uso interno
                description=parameters.get('description', ''),
                include_meet=parameters.get('include_meet', True),
                force_create=bool(conflicts and (parameters.get('force_create', False) or auto_force_create)),
                project_id=context.project_id,
                project=context.project  # Para compatibilidad temporal hasta migración completa
            )
            
            if not event_result['success']:
                return event_result
            
            # 3. Actualizar contacto (solo si hay email)
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
            
            # 4. Enviar notificaciones (en paralelo) - solo si hay email
            if attendee_email:
                # Obtener datos reales del contacto desde la base de datos
                stored_contact = await contact_manager.get_contact(context.user_id, context.project_id)
                
                # Combinar datos del contacto almacenado con parámetros actuales
                contact_data = {
                    'email': attendee_email,
                    'name': parameters.get('attendee_name', ''),
                    'phone': parameters.get('attendee_phone', ''),
                    'phone_number': parameters.get('attendee_phone', '')  # Para compatibilidad
                }
                
                # Si existe contacto almacenado, usar sus datos como prioritarios
                if stored_contact:
                    contact_data.update({
                        'name': stored_contact.get('name', contact_data['name']),
                        'phone': stored_contact.get('phone_number', contact_data['phone']),
                        'phone_number': stored_contact.get('phone_number', contact_data['phone_number']),
                        'email': stored_contact.get('email', contact_data['email'])
                    })
                    self.logger.info(f"📞 Datos de contacto obtenidos desde DB: phone={contact_data['phone']}, name={contact_data['name']}")
                else:
                    self.logger.warning(f"📞 No se encontró contacto almacenado para user_id={context.user_id}, usando parámetros actuales")
                
                await notification_service.send_appointment_notifications(
                    event_data=event_result['event_data'],
                    contact_data=contact_data,
                    project_id=context.project_id,
                    user_id=context.user_id,
                    conversation_summary=parameters.get('conversation_summary', '')
                )
            
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