"""
Servicio especializado para operaciones de Google Calendar.
Encapsula toda la lógica de interacción con Google Calendar API.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import pytz

from app.controler.chat.core.tools.calendar_tool import google_calendar_tool
from app.controler.chat.core.security.thread_safe_cache import conflict_cache
from app.controler.chat.core.security.error_handler import raise_calendar_error, ErrorCategory, ErrorSeverity

logger = logging.getLogger(__name__)

class CalendarService:
    """
    Servicio especializado para operaciones de Google Calendar.
    Responsabilidad única: gestionar interacciones con Google Calendar API.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.chile_tz = pytz.timezone('America/Santiago')
        
        # Configuración de timeouts y retry
        self.calendar_operation_timeout = 30.0  # 30 segundos para operaciones de calendario complejas
        self.max_retries = 3
        self.base_delay = 1.0
    
    async def find_available_slots(self, 
                                 project_id: str,
                                 user_id: str, 
                                 title: str = "",
                                 specific_date: Optional[str] = None,
                                 duration_hours: int = 1,
                                 project: Any = None,
                                 search_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Busca slots disponibles en el calendario.
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario
            title: Título de búsqueda (para contexto)
            specific_date: Fecha específica (YYYY-MM-DD)
            duration_hours: Duración en horas
            project: Objeto proyecto para configuración
            search_config: Configuración de filtros (exclude_holidays, search_weeks_ahead)
            
        Returns:
            Lista de slots disponibles
        """
        try:
            # Construir query para calendar_tool
            query_parts = ["find_available_slots"]
            
            if specific_date:
                query_parts.append(f"specific_date={specific_date}")
            
            if duration_hours != 1:
                query_parts.append(f"duration={duration_hours}")
            
            if title:
                query_parts.append(f"title={title}")
            
            # Agregar configuraciones de filtro si están disponibles
            if search_config:
                exclude_holidays = search_config.get('exclude_holidays', True)
                search_weeks_ahead = search_config.get('search_weeks_ahead', 3)
                
                if exclude_holidays:
                    query_parts.append("exclude_holidays=true")
                    
                if search_weeks_ahead != 3:  # Solo agregar si es diferente al valor por defecto
                    query_parts.append(f"search_weeks_ahead={search_weeks_ahead}")
                
                self.logger.info(f"🔍 Filtros aplicados: exclude_holidays={exclude_holidays}, search_weeks_ahead={search_weeks_ahead}")
            
            calendar_query = "|".join(query_parts)
            
            # Preparar estado mockup para calendar_tool
            mock_state = {
                "project": project,
                "user_id": user_id,
                "project_id": project_id
            }
            
            # Ejecutar búsqueda con timeout y retry
            result = await self._execute_calendar_operation_with_retry(
                google_calendar_tool.invoke,
                {"query": calendar_query, "state": mock_state}
            )
            
            # Parsear resultado
            if isinstance(result, str):
                if "Error" in result or "❌" in result:
                    raise_calendar_error(
                        f"Error buscando slots disponibles: {result}",
                        ErrorCategory.CALENDAR_API,
                        ErrorSeverity.HIGH,
                        "SLOTS_SEARCH_FAILED"
                    )
                
                # Parsear slots del resultado de texto
                slots = self._parse_available_slots(result)
                
                # Devolver todos los slots disponibles encontrados
                self.logger.info(f"Se encontraron {len(slots)} slots disponibles para '{title}'")
                return slots
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error en find_available_slots: {str(e)}")
            raise_calendar_error(
                f"Error buscando horarios disponibles: {str(e)}",
                ErrorCategory.CALENDAR_API,
                ErrorSeverity.HIGH,
                "FIND_SLOTS_ERROR",
                project_id=project_id,
                user_id=user_id
            )
    
    async def check_conflicts(self, 
                            start_time: str, 
                            end_time: Optional[str] = None,
                            project_id: str = "unknown",
                            project: Any = None) -> List[Dict[str, Any]]:
        """
        Verifica conflictos en el horario especificado.
        
        Args:
            start_time: Hora de inicio (ISO format)
            end_time: Hora de fin (ISO format, opcional)
            project_id: ID del proyecto
            
        Returns:
            Lista de eventos en conflicto
        """
        try:
            # Si no hay end_time, usar duración por defecto de 1 hora
            if not end_time:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = start_dt + timedelta(hours=1)
                end_time = end_dt.isoformat()
            
            # Construir query para verificar disponibilidad
            calendar_query = f"check_availability|start={start_time}|end={end_time}"
            
            # Preparar estado con configuración de agenda en lugar de proyecto
            mock_state = {
                "project_id": project_id
            }
            
            # Si se proporciona proyecto, pasar también para compatibilidad temporal
            if project:
                mock_state["project"] = project
            
            # Ejecutar verificación con timeout y retry
            result = await self._execute_calendar_operation_with_retry(
                google_calendar_tool.invoke,
                {"query": calendar_query, "state": mock_state}
            )
            
            # Parsear conflictos
            if isinstance(result, str):
                if "conflicto" in result.lower() or "conflict" in result.lower():
                    return self._parse_conflicts(result)
                elif "disponible" in result.lower() or "available" in result.lower():
                    return []
                elif "error" in result.lower() or "❌" in result:
                    raise_calendar_error(
                        f"Error verificando conflictos: {result}",
                        ErrorCategory.CALENDAR_API,
                        ErrorSeverity.HIGH,
                        "CONFLICT_CHECK_ERROR"
                    )
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error verificando conflictos: {str(e)}")
            # Invalidar cache en caso de error
            conflict_cache.invalidate_time_range(project_id, start_time, end_time or start_time)
            raise
    
    async def create_event(self,
                         title: str,
                         start_datetime: str,
                         end_datetime: Optional[str] = None,
                         attendee_email: str = "",
                         description: str = "",
                         include_meet: bool = True,
                         force_create: bool = False,
                         project_id: str = "unknown",
                         project: Any = None) -> Dict[str, Any]:
        """
        Crea un evento en Google Calendar.
        
        Args:
            title: Título del evento
            start_datetime: Fecha/hora de inicio
            end_datetime: Fecha/hora de fin (opcional)
            attendee_email: Email del asistente
            description: Descripción del evento
            include_meet: Incluir Google Meet
            project_id: ID del proyecto
            
        Returns:
            Resultado de la creación del evento
        """
        try:
            # Construir query para crear evento
            query_parts = [
                "create_event",
                f"title={title}",
                f"start={start_datetime}"
            ]
            
            if end_datetime:
                query_parts.append(f"end={end_datetime}")
            
            if attendee_email:
                query_parts.append(f"attendees={attendee_email}")
            
            if description:
                query_parts.append(f"description={description}")
            
            if include_meet:
                query_parts.append("meet=true")
            
            if force_create:
                query_parts.append("force_create=true")
            
            calendar_query = "|".join(query_parts)
            
            # Preparar estado con configuración de agenda en lugar de proyecto
            mock_state = {
                "project_id": project_id
            }
            
            # Si se proporciona proyecto, pasar también para compatibilidad temporal
            if project:
                mock_state["project"] = project
            
            # Ejecutar creación con timeout y retry
            result = await self._execute_calendar_operation_with_retry(
                google_calendar_tool.invoke,
                {"query": calendar_query, "state": mock_state}
            )
            
            # Invalidar cache después de crear evento
            end_time_for_cache = end_datetime or start_datetime
            conflict_cache.invalidate_time_range(project_id, start_datetime, end_time_for_cache)
            
            # Parsear resultado
            if isinstance(result, str):
                if "exitosamente" in result or "successfully" in result:
                    event_data = self._parse_event_creation_result(result, {
                        'title': title,
                        'start_datetime': start_datetime,
                        'end_datetime': end_datetime,
                        'description': description,
                        'attendee_email': attendee_email
                    })
                    return {
                        'success': True,
                        'event_id': event_data.get('event_id'),
                        'event_url': event_data.get('event_url'),
                        'meet_url': event_data.get('meet_url'),
                        'event_data': event_data
                    }
                elif "error" in result.lower() or "❌" in result:
                    return {
                        'success': False,
                        'error': result
                    }
            
            return {
                'success': False,
                'error': 'Respuesta inesperada del calendario'
            }
            
        except Exception as e:
            self.logger.error(f"Error creando evento: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_event(self,
                         event_id: str,
                         updates: Dict[str, Any],
                         project_id: str = "unknown") -> Dict[str, Any]:
        """
        Actualiza un evento existente.
        
        Args:
            event_id: ID del evento
            updates: Campos a actualizar
            project_id: ID del proyecto
            
        Returns:
            Resultado de la actualización
        """
        try:
            # Construir query de actualización
            query_parts = ["update_event", f"event_id={event_id}"]
            
            for key, value in updates.items():
                if key not in ['event_id'] and value is not None:
                    query_parts.append(f"{key}={value}")
            
            calendar_query = "|".join(query_parts)
            
            # Preparar estado
            mock_state = {"project_id": project_id}
            
            # Ejecutar actualización
            result = await asyncio.to_thread(
                google_calendar_tool.invoke,
                {"query": calendar_query, "state": mock_state}
            )
            
            # Invalidar cache (usar fechas del update si están disponibles)
            if 'start_datetime' in updates:
                start_time = updates['start_datetime']
                end_time = updates.get('end_datetime', start_time)
                conflict_cache.invalidate_time_range(project_id, start_time, end_time)
            
            # Parsear resultado
            if isinstance(result, str):
                if "exitosamente" in result or "successfully" in result:
                    return {
                        'success': True,
                        'event_data': self._parse_event_data(result)
                    }
                elif "error" in result.lower() or "❌" in result:
                    return {
                        'success': False,
                        'error': result
                    }
            
            return {
                'success': False,
                'error': 'Respuesta inesperada del calendario'
            }
            
        except Exception as e:
            self.logger.error(f"Error actualizando evento: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_event(self, event_id: str, project_id: str = "unknown") -> Dict[str, Any]:
        """
        Elimina un evento del calendario.
        
        Args:
            event_id: ID del evento a eliminar
            project_id: ID del proyecto
            
        Returns:
            Resultado de la eliminación
        """
        try:
            # Obtener datos del evento antes de eliminar (para invalidar cache)
            event_data = await self.get_event(event_id, project_id)
            
            # Construir query de eliminación
            calendar_query = f"delete_event|event_id={event_id}"
            
            # Preparar estado
            mock_state = {"project_id": project_id}
            
            # Ejecutar eliminación
            result = await asyncio.to_thread(
                google_calendar_tool.invoke,
                {"query": calendar_query, "state": mock_state}
            )
            
            # Invalidar cache usando datos del evento eliminado
            if event_data and 'start_time' in event_data:
                start_time = event_data['start_time']
                end_time = event_data.get('end_time', start_time)
                conflict_cache.invalidate_time_range(project_id, start_time, end_time)
            
            # Parsear resultado
            if isinstance(result, str):
                if "exitosamente" in result or "successfully" in result:
                    return {
                        'success': True,
                        'deleted_event_data': event_data
                    }
                elif "error" in result.lower() or "❌" in result:
                    return {
                        'success': False,
                        'error': result
                    }
            
            return {
                'success': False,
                'error': 'Respuesta inesperada del calendario'
            }
            
        except Exception as e:
            self.logger.error(f"Error eliminando evento: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_event(self, event_id: str, project_id: str = "unknown") -> Dict[str, Any]:
        """
        Obtiene información de un evento específico.
        
        Args:
            event_id: ID del evento
            project_id: ID del proyecto
            
        Returns:
            Datos del evento
        """
        try:
            # Construir query
            calendar_query = f"get_event|event_id={event_id}"
            
            # Preparar estado
            mock_state = {"project_id": project_id}
            
            # Ejecutar consulta
            result = await asyncio.to_thread(
                google_calendar_tool.invoke,
                {"query": calendar_query, "state": mock_state}
            )
            
            # Parsear resultado
            if isinstance(result, str):
                if "error" in result.lower() or "❌" in result:
                    raise_calendar_error(
                        f"Error obteniendo evento: {result}",
                        ErrorCategory.CALENDAR_API,
                        ErrorSeverity.MEDIUM,
                        "GET_EVENT_ERROR"
                    )
                
                return self._parse_event_data(result)
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Error obteniendo evento: {str(e)}")
            raise
    
    def _parse_available_slots(self, result_text: str) -> List[Dict[str, Any]]:
        """Parsea slots disponibles del resultado de texto."""
        slots = []
        
        try:
            # Buscar diferentes formatos de respuesta del calendar_tool
            lines = result_text.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Formato 1: "1. Lunes 14 De Julio De 2025 a las 09:00 horas"
                # Formato 2: "Lunes 14 De Julio De 2025 a las 09:00 horas" (sin número)
                # Formato 3: Líneas que contienen horarios directamente
                
                # Filtrar líneas de encabezado que no son slots reales
                if any(header_word in line.lower() for header_word in ['**horarios disponibles', 'verificados en calendario', '**próximas fechas']):
                    continue  # Saltar encabezados
                
                # Detectar líneas con números y fechas/horarios
                if (line and (line[0].isdigit() or any(day in line.lower() for day in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'])) 
                    and any(time_word in line.lower() for time_word in ['horas', 'am', 'pm', ':'])):
                    
                    # Limpiar el número del inicio si existe
                    time_text = line
                    if line and line[0].isdigit() and '. ' in line:
                        time_text = line.split('. ', 1)[1] if '. ' in line else line
                    
                    slots.append({
                        'time_text': time_text,
                        'available': True
                    })
                    
                # También detectar formatos más simples de horarios (pero no encabezados)
                elif (any(time_marker in line for time_marker in [':', 'AM', 'PM', 'hrs']) and len(line) > 5 
                      and not any(header_word in line.lower() for header_word in ['**horarios disponibles', 'verificados en calendario', '**próximas fechas'])):
                    slots.append({
                        'time_text': line,
                        'available': True
                    })
            
            self.logger.info(f"CalendarService parseó {len(slots)} slots del resultado del calendar_tool")
            for i, slot in enumerate(slots):
                self.logger.info(f"  Slot {i+1}: {slot['time_text']}")
            
        except Exception as e:
            self.logger.error(f"Error parseando slots disponibles: {str(e)}")
            self.logger.error(f"Texto a parsear: {result_text[:500]}...")
        
        return slots
    
    def _parse_conflicts(self, result_text: str) -> List[Dict[str, Any]]:
        """Parsea conflictos del resultado de texto."""
        conflicts = []
        
        # Implementar parsing de conflictos
        if "conflicto" in result_text.lower():
            conflicts.append({
                'conflict_detected': True,
                'details': result_text
            })
        
        return conflicts
    
    def _parse_event_creation_result(self, result_text: str, original_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Parsea resultado de creación de evento."""
        event_data = {}
        
        # Incluir parámetros originales si están disponibles
        if original_params:
            event_data.update({
                'title': original_params.get('title', ''),
                'start_time': original_params.get('start_datetime', ''),
                'end_time': original_params.get('end_datetime', ''),
                'description': original_params.get('description', ''),
                'attendee_email': original_params.get('attendee_email', '')
            })
        
        # Extraer event_id directamente de la respuesta (método preferido)
        if "ID del evento:" in result_text:
            import re
            id_match = re.search(r'ID del evento:\s*(\S+)', result_text)
            if id_match:
                event_data['event_id'] = id_match.group(1)
        
        # Extraer URL del evento
        if "http" in result_text:
            import re
            urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', result_text)
            if urls:
                event_data['event_url'] = urls[0]
                
                # Extraer event_id de la URL como método de respaldo
                if 'calendar.google.com' in urls[0] and not event_data.get('event_id'):
                    parts = urls[0].split('/')
                    if len(parts) > 6:
                        event_data['event_id'] = parts[6].split('?')[0]
        
        # Extraer Meet URL
        if "meet.google.com" in result_text:
            import re
            meet_urls = re.findall(r'https://meet\.google\.com/[a-z-]+', result_text)
            if meet_urls:
                event_data['meet_url'] = meet_urls[0]
        
        return event_data
    
    def _parse_event_data(self, result_text: str) -> Dict[str, Any]:
        """Parsea datos generales de evento."""
        event_data = {}
        
        # Implementar parsing básico de datos de evento
        lines = result_text.split('\n')
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                event_data[key] = value
        
        return event_data
    
    async def _execute_calendar_operation_with_retry(self, operation_func, *args, **kwargs) -> Any:
        """
        Ejecuta operación de calendario con retry automático y timeout.
        
        Args:
            operation_func: Función de operación de calendario
            *args: Argumentos posicionales
            **kwargs: Argumentos con nombre
            
        Returns:
            Resultado de la operación
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                # Ejecutar operación con timeout
                result = await asyncio.wait_for(
                    asyncio.to_thread(operation_func, *args, **kwargs),
                    timeout=self.calendar_operation_timeout
                )
                
                return result
                
            except asyncio.TimeoutError as e:
                last_exception = e
                
                if attempt < self.max_retries - 1:
                    wait_time = self.base_delay * (2 ** attempt)
                    self.logger.warning(
                        f"Timeout en operación de calendario (intento {attempt + 1}/{self.max_retries}), "
                        f"reintentando en {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"Operación de calendario falló por timeout después de {self.max_retries} intentos")
                    raise_calendar_error(
                        f"Timeout en operación de calendario después de {self.max_retries} intentos",
                        ErrorCategory.CALENDAR_API,
                        ErrorSeverity.HIGH,
                        "CALENDAR_TIMEOUT_ERROR"
                    )
            
            except Exception as e:
                last_exception = e
                
                # Si es un error de API recoverable, reintentar
                if any(recoverable_error in str(e).lower() for recoverable_error in 
                       ['network', 'timeout', 'connection', 'temporarily unavailable']):
                    
                    if attempt < self.max_retries - 1:
                        wait_time = self.base_delay * (2 ** attempt)
                        self.logger.warning(
                            f"Error recuperable en calendario (intento {attempt + 1}/{self.max_retries}): {str(e)}, "
                            f"reintentando en {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                
                # Error no recuperable, lanzar inmediatamente
                self.logger.error(f"Error no recuperable en operación de calendario: {str(e)}")
                raise
        
        # Si llegamos aquí, se agotaron los reintentos
        raise last_exception
    
    async def add_attendee_to_event(self, 
                                  event_id: str, 
                                  attendee_email: str, 
                                  project_id: str,
                                  project: Any = None) -> Dict[str, Any]:
        """
        Agrega un asistente a un evento existente en Google Calendar.
        
        Args:
            event_id: ID del evento
            attendee_email: Email del asistente a agregar
            project_id: ID del proyecto
            project: Objeto proyecto (opcional)
            
        Returns:
            Resultado de la operación
        """
        try:
            # Construir query para agregar asistente
            query_parts = [
                "add_attendee",
                f"event_id={event_id}",
                f"attendee_email={attendee_email}"
            ]
            
            calendar_query = "|".join(query_parts)
            
            # Preparar estado
            mock_state = {
                "project_id": project_id
            }
            
            # Si se proporciona proyecto, pasar también para compatibilidad
            if project:
                mock_state["project"] = project
            
            # Ejecutar operación con timeout y retry
            result = await self._execute_calendar_operation_with_retry(
                google_calendar_tool.invoke,
                {"query": calendar_query, "state": mock_state}
            )
            
            # Parsear resultado
            if isinstance(result, str):
                if "exitosamente" in result or "successfully" in result or "added" in result.lower():
                    return {
                        'success': True,
                        'message': result
                    }
                elif "error" in result.lower() or "❌" in result:
                    return {
                        'success': False,
                        'error': result
                    }
            
            return {
                'success': False,
                'error': 'Respuesta inesperada al agregar asistente'
            }
            
        except Exception as e:
            self.logger.error(f"Error agregando asistente al evento {event_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    
