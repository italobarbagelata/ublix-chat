"""
EventPersistenceService - Servicio para persistir eventos localmente.
Actúa como capa de abstracción entre la lógica de negocio y la base de datos.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

from app.controler.chat.store.supabase_client import SupabaseClient

from app.models.calendar import (
    CalendarEventLocalCreate,
    CalendarEventLocalUpdate,
    CalendarEventLocalResponse,
    CalendarEventListResponse
)


logger = logging.getLogger(__name__)

class EventPersistenceService:
    """
    Servicio para persistir eventos localmente.
    
    Responsabilidades:
    - Gestionar CRUD de eventos con validación
    - Mapear entre modelos Pydantic y datos de BD
    - Manejar errores de persistencia
    - Proporcionar métodos de búsqueda avanzada
    """
    
    def __init__(self):
        """Inicializa el servicio con cliente de Supabase."""
        self.supabase_client = SupabaseClient()
        logger.info("EventPersistenceService inicializado")
    
    async def save_event(self, event_data: CalendarEventLocalCreate) -> Optional[CalendarEventLocalResponse]:
        """
        Guarda un nuevo evento en la base de datos.
        
        Args:
            event_data: Datos del evento a crear
            
        Returns:
            Evento creado o None si hay error
        """
        try:
            # Convertir modelo Pydantic a diccionario
            event_dict = event_data.model_dump()
            
            # Convertir fechas a string ISO
            if isinstance(event_dict.get('start_datetime'), datetime):
                event_dict['start_datetime'] = event_dict['start_datetime'].isoformat()
            if isinstance(event_dict.get('end_datetime'), datetime):
                event_dict['end_datetime'] = event_dict['end_datetime'].isoformat()
            
            # Convertir UUID a string
            if isinstance(event_dict.get('project_id'), UUID):
                event_dict['project_id'] = str(event_dict['project_id'])
            
            logger.info(f"Guardando evento: {event_dict.get('title', 'Sin título')}")
            
            # Guardar en BD
            result = self.supabase_client.create_calendar_event(event_dict)
            
            if result:
                # Convertir resultado a modelo de respuesta
                return CalendarEventLocalResponse(**result)
            
            logger.error("No se pudo crear el evento en la base de datos")
            return None
            
        except Exception as e:
            logger.error(f"Error guardando evento: {str(e)}")
            return None
    
    async def update_event(self, event_id: str, update_data: CalendarEventLocalUpdate) -> Optional[CalendarEventLocalResponse]:
        """
        Actualiza un evento existente.
        
        Args:
            event_id: ID del evento a actualizar
            update_data: Datos a actualizar
            
        Returns:
            Evento actualizado o None si hay error
        """
        try:
            # Convertir modelo Pydantic a diccionario, excluyendo None
            update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
            
            if not update_dict:
                logger.warning(f"No hay datos para actualizar en evento {event_id}")
                return None
            
            # Convertir fechas a string ISO
            for field in ['start_datetime', 'end_datetime']:
                if field in update_dict and isinstance(update_dict[field], datetime):
                    update_dict[field] = update_dict[field].isoformat()
            
            logger.info(f"Actualizando evento {event_id} con campos: {list(update_dict.keys())}")
            
            # Actualizar en BD
            result = self.supabase_client.update_calendar_event(event_id, update_dict)
            
            if result:
                return CalendarEventLocalResponse(**result)
            
            logger.error(f"No se pudo actualizar el evento {event_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error actualizando evento {event_id}: {str(e)}")
            return None
    
    async def get_event(self, event_id: str) -> Optional[CalendarEventLocalResponse]:
        """
        Obtiene un evento por su ID.
        
        Args:
            event_id: ID del evento
            
        Returns:
            Evento o None si no se encuentra
        """
        try:
            result = self.supabase_client.get_calendar_event(event_id)
            
            if result:
                return CalendarEventLocalResponse(**result)
            
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo evento {event_id}: {str(e)}")
            return None
    
    async def get_event_by_google_id(self, google_event_id: str) -> Optional[CalendarEventLocalResponse]:
        """
        Obtiene un evento por su ID de Google Calendar.
        
        Args:
            google_event_id: ID del evento en Google Calendar
            
        Returns:
            Evento o None si no se encuentra
        """
        try:
            result = self.supabase_client.get_calendar_event_by_google_id(google_event_id)
            
            if result:
                return CalendarEventLocalResponse(**result)
            
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo evento por Google ID {google_event_id}: {str(e)}")
            return None
    
    async def get_events_by_project(self, 
                                  project_id: str,
                                  start_date: Optional[datetime] = None,
                                  end_date: Optional[datetime] = None,
                                  status: Optional[str] = None,
                                  page: int = 1,
                                  page_size: int = 50) -> CalendarEventListResponse:
        """
        Obtiene eventos de un proyecto con filtros.
        
        Args:
            project_id: ID del proyecto
            start_date: Fecha de inicio (opcional)
            end_date: Fecha de fin (opcional)
            status: Estado del evento (opcional)
            page: Página para paginación
            page_size: Tamaño de página
            
        Returns:
            Lista de eventos con metadatos de paginación
        """
        try:
            result = self.supabase_client.get_calendar_events_by_project(
                project_id=project_id,
                start_date=start_date,
                end_date=end_date,
                status=status,
                page=page,
                page_size=page_size
            )
            
            # Convertir eventos a modelos de respuesta
            events = [CalendarEventLocalResponse(**event) for event in result["events"]]
            
            return CalendarEventListResponse(
                events=events,
                total_count=result["total_count"],
                page=result["page"],
                page_size=result["page_size"]
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo eventos del proyecto {project_id}: {str(e)}")
            return CalendarEventListResponse(events=[], total_count=0, page=page, page_size=page_size)
    
    async def delete_event(self, event_id: str, soft_delete: bool = True) -> bool:
        """
        Elimina un evento (física o lógicamente).
        
        Args:
            event_id: ID del evento a eliminar
            soft_delete: Si True, marca como cancelado; si False, elimina físicamente
            
        Returns:
            True si se eliminó exitosamente, False en caso contrario
        """
        try:
            if soft_delete:
                result = self.supabase_client.soft_delete_calendar_event(event_id)
                success = result is not None
            else:
                success = self.supabase_client.delete_calendar_event(event_id)
            
            if success:
                action = "cancelado" if soft_delete else "eliminado"
                logger.info(f"Evento {action} exitosamente: {event_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error eliminando evento {event_id}: {str(e)}")
            return False
    
    async def get_events_by_attendee(self, attendee_email: str, project_id: Optional[str] = None) -> List[CalendarEventLocalResponse]:
        """
        Obtiene eventos por email del asistente.
        
        Args:
            attendee_email: Email del asistente
            project_id: ID del proyecto (opcional)
            
        Returns:
            Lista de eventos del asistente
        """
        try:
            results = self.supabase_client.get_events_by_attendee_email(attendee_email, project_id)
            
            return [CalendarEventLocalResponse(**event) for event in results]
            
        except Exception as e:
            logger.error(f"Error obteniendo eventos para {attendee_email}: {str(e)}")
            return []
    
    async def get_events_in_date_range(self, 
                                     project_id: str,
                                     start_datetime: datetime,
                                     end_datetime: datetime) -> List[CalendarEventLocalResponse]:
        """
        Obtiene eventos confirmados en un rango de fechas específico.
        Útil para verificar conflictos de horarios.
        
        Args:
            project_id: ID del proyecto
            start_datetime: Fecha/hora de inicio
            end_datetime: Fecha/hora de fin
            
        Returns:
            Lista de eventos en el rango
        """
        try:
            results = self.supabase_client.get_events_in_date_range(
                project_id=project_id,
                start_datetime=start_datetime,
                end_datetime=end_datetime
            )
            
            return [CalendarEventLocalResponse(**event) for event in results]
            
        except Exception as e:
            logger.error(f"Error obteniendo eventos en rango para proyecto {project_id}: {str(e)}")
            return []
    
    async def check_time_conflict(self, 
                                project_id: str,
                                start_datetime: datetime,
                                end_datetime: datetime,
                                exclude_event_id: Optional[str] = None) -> bool:
        """
        Verifica si existe conflicto de horarios.
        
        Args:
            project_id: ID del proyecto
            start_datetime: Fecha/hora de inicio propuesta
            end_datetime: Fecha/hora de fin propuesta
            exclude_event_id: ID de evento a excluir (para actualizaciones)
            
        Returns:
            True si hay conflicto, False si está libre
        """
        try:
            # Buscar eventos que se solapen con el horario propuesto
            conflicting_events = await self.get_events_in_date_range(
                project_id=project_id,
                start_datetime=start_datetime,
                end_datetime=end_datetime
            )
            
            # Filtrar eventos confirmados y excluir el evento actual si se proporciona
            for event in conflicting_events:
                if event.status == 'confirmed':
                    if exclude_event_id and str(event.id) == exclude_event_id:
                        continue
                    
                    # Verificar solapamiento
                    if (start_datetime < event.end_datetime and end_datetime > event.start_datetime):
                        logger.info(f"Conflicto detectado con evento {event.id}: {event.title}")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error verificando conflictos: {str(e)}")
            # En caso de error, asumir que hay conflicto por seguridad
            return True
    
    async def get_event_statistics(self, project_id: str, 
                                 start_date: Optional[datetime] = None,
                                 end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Obtiene estadísticas de eventos para un proyecto.
        
        Args:
            project_id: ID del proyecto
            start_date: Fecha de inicio (opcional)
            end_date: Fecha de fin (opcional)
            
        Returns:
            Diccionario con estadísticas
        """
        try:
            # Obtener todos los eventos del período
            events_response = await self.get_events_by_project(
                project_id=project_id,
                start_date=start_date,
                end_date=end_date,
                page_size=1000  # Obtener muchos eventos para estadísticas
            )
            
            events = events_response.events
            
            # Calcular estadísticas
            stats = {
                "total_events": len(events),
                "confirmed_events": len([e for e in events if e.status == 'confirmed']),
                "cancelled_events": len([e for e in events if e.status == 'cancelled']),
                "tentative_events": len([e for e in events if e.status == 'tentative']),
                "events_with_attendees": len([e for e in events if e.attendee_email]),
                "events_with_meet": len([e for e in events if e.google_meet_url]),
                "unique_attendees": len(set(e.attendee_email for e in events if e.attendee_email))
            }
            
            logger.info(f"Estadísticas calculadas para proyecto {project_id}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error calculando estadísticas para proyecto {project_id}: {str(e)}")
            return {
                "total_events": 0,
                "confirmed_events": 0,
                "cancelled_events": 0,
                "tentative_events": 0,
                "events_with_attendees": 0,
                "events_with_meet": 0,
                "unique_attendees": 0
            }