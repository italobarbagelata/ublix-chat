import os
import logging
from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from app.controler.chat.store.supabase_singleton import SupabaseSingleton

logger = logging.getLogger("root")


class SupabaseClient:
    """
    Client for interacting with Supabase database.

    OPTIMIZACIÓN: Usa el singleton interno para evitar múltiples conexiones.
    Todas las instancias de SupabaseClient comparten la misma conexión.
    """

    def __init__(self):
        """
        Initialize Supabase client using singleton pattern.
        La conexión real se crea una sola vez y se reutiliza.
        """
        # OPTIMIZACIÓN: Usar singleton en lugar de crear nueva conexión
        self.client: Client = SupabaseSingleton.get_client()
        # No logueamos cada inicialización para evitar spam en logs
        logger.debug("SupabaseClient usando conexión singleton")
    
    def get_apis_by_project_id(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get all APIs for a specific project.
        
        Args:
            project_id: The project ID to filter by
            
        Returns:
            List of API configurations
        """
        try:
            response = self.client.table("apis").select("*").eq("project_id", project_id).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error fetching APIs for project {project_id}: {str(e)}")
            return []
    
    def get_api_by_name(self, project_id: str, api_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific API by name within a project.
        
        Args:
            project_id: The project ID
            api_name: The API name to find
            
        Returns:
            API configuration or None if not found
        """
        try:
            response = self.client.table("apis").select("*").eq("project_id", project_id).eq("api_name", api_name).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching API {api_name} for project {project_id}: {str(e)}")
            return None
    
    def create_api(self, api_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a new API configuration.
        
        Args:
            api_data: The API data to insert
            
        Returns:
            Created API data or None if error
        """
        try:
            response = self.client.table("apis").insert(api_data).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creating API: {str(e)}")
            return None
    
    def update_api(self, api_id: str, api_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update an existing API configuration.
        
        Args:
            api_id: The API ID to update
            api_data: The updated API data
            
        Returns:
            Updated API data or None if error
        """
        try:
            response = self.client.table("apis").update(api_data).eq("id", api_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error updating API {api_id}: {str(e)}")
            return None
    
    def delete_api(self, api_id: str) -> bool:
        """
        Delete an API configuration.
        
        Args:
            api_id: The API ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.table("apis").delete().eq("id", api_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting API {api_id}: {str(e)}")
            return False

    # Calendar Integration Methods
    def get_calendar_integration(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the Google Calendar integration for a project.
        
        Args:
            project_id: The project ID
            
        Returns:
            Calendar integration or None if not found
        """
        try:
            response = self.client.table("calendar_integrations").select("*").eq("project_id", project_id).eq("is_active", True).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching calendar integration for project {project_id}: {str(e)}")
            return None
    
    def create_calendar_integration(self, integration_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a new calendar integration.
        
        Args:
            integration_data: The integration data to insert
            
        Returns:
            Created integration data or None if error
        """
        try:
            response = self.client.table("calendar_integrations").insert(integration_data).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creating calendar integration: {str(e)}")
            return None
    
    def update_calendar_integration(self, integration_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update an existing calendar integration.
        
        Args:
            integration_id: The ID of the integration to update
            update_data: The data to update
            
        Returns:
            Updated integration data or None if error
        """
        try:
            update_data["updated_at"] = datetime.utcnow().isoformat()
            response = self.client.table("calendar_integrations").update(update_data).eq("id", integration_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error updating calendar integration {integration_id}: {str(e)}")
            return None

    # Calendar Events CRUD Methods
    def create_calendar_event(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crea un nuevo evento en la tabla calendar_events.
        
        Args:
            event_data: Datos del evento a crear
            
        Returns:
            Evento creado o None si hay error
        """
        try:
            response = self.client.table("calendar_events").insert(event_data).execute()
            if response.data and len(response.data) > 0:
                logger.info(f"Evento creado exitosamente: {response.data[0]['id']}")
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creando evento: {str(e)}")
            return None
    
    def get_calendar_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un evento por su ID.
        
        Args:
            event_id: ID del evento
            
        Returns:
            Evento o None si no se encuentra
        """
        try:
            response = self.client.table("calendar_events").select("*").eq("id", event_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error obteniendo evento {event_id}: {str(e)}")
            return None
    
    def get_calendar_event_by_google_id(self, google_event_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un evento por su google_event_id.
        
        Args:
            google_event_id: ID del evento en Google Calendar
            
        Returns:
            Evento o None si no se encuentra
        """
        try:
            response = self.client.table("calendar_events").select("*").eq("google_event_id", google_event_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error obteniendo evento por Google ID {google_event_id}: {str(e)}")
            return None
    
    def get_calendar_events_by_project(self, 
                                     project_id: str, 
                                     start_date: Optional[datetime] = None,
                                     end_date: Optional[datetime] = None,
                                     status: Optional[str] = None,
                                     page: int = 1,
                                     page_size: int = 50) -> Dict[str, Any]:
        """
        Obtiene eventos de un proyecto con filtros opcionales.
        
        Args:
            project_id: ID del proyecto
            start_date: Fecha de inicio (opcional)
            end_date: Fecha de fin (opcional)
            status: Estado del evento (opcional)
            page: Página para paginación
            page_size: Tamaño de página
            
        Returns:
            Diccionario con eventos y metadatos de paginación
        """
        try:
            query = self.client.table("calendar_events").select("*", count="exact").eq("project_id", project_id)
            
            # Aplicar filtros
            if start_date:
                query = query.gte("start_datetime", start_date.isoformat())
            if end_date:
                query = query.lte("end_datetime", end_date.isoformat())
            if status:
                query = query.eq("status", status)
            
            # Ordenar por fecha de inicio
            query = query.order("start_datetime", desc=True)
            
            # Aplicar paginación
            offset = (page - 1) * page_size
            query = query.range(offset, offset + page_size - 1)
            
            response = query.execute()
            
            return {
                "events": response.data if response.data else [],
                "total_count": response.count if response.count else 0,
                "page": page,
                "page_size": page_size
            }
        except Exception as e:
            logger.error(f"Error obteniendo eventos del proyecto {project_id}: {str(e)}")
            return {"events": [], "total_count": 0, "page": page, "page_size": page_size}
    
    def update_calendar_event(self, event_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Actualiza un evento existente.
        
        Args:
            event_id: ID del evento a actualizar
            update_data: Datos a actualizar
            
        Returns:
            Evento actualizado o None si hay error
        """
        try:
            # El trigger se encarga de actualizar updated_at automáticamente
            response = self.client.table("calendar_events").update(update_data).eq("id", event_id).execute()
            if response.data and len(response.data) > 0:
                logger.info(f"Evento actualizado exitosamente: {event_id}")
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error actualizando evento {event_id}: {str(e)}")
            return None
    
    def delete_calendar_event(self, event_id: str) -> bool:
        """
        Elimina un evento (eliminación física).
        
        Args:
            event_id: ID del evento a eliminar
            
        Returns:
            True si se eliminó exitosamente, False en caso contrario
        """
        try:
            response = self.client.table("calendar_events").delete().eq("id", event_id).execute()
            logger.info(f"Evento eliminado exitosamente: {event_id}")
            return True
        except Exception as e:
            logger.error(f"Error eliminando evento {event_id}: {str(e)}")
            return False
    
    def soft_delete_calendar_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Marca un evento como cancelado (eliminación lógica).
        
        Args:
            event_id: ID del evento a cancelar
            
        Returns:
            Evento actualizado o None si hay error
        """
        try:
            update_data = {"status": "cancelled"}
            return self.update_calendar_event(event_id, update_data)
        except Exception as e:
            logger.error(f"Error cancelando evento {event_id}: {str(e)}")
            return None
    
    def get_events_by_attendee_email(self, attendee_email: str, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Obtiene eventos por email del asistente.
        
        Args:
            attendee_email: Email del asistente
            project_id: ID del proyecto (opcional)
            
        Returns:
            Lista de eventos
        """
        try:
            query = self.client.table("calendar_events").select("*").eq("attendee_email", attendee_email)
            
            if project_id:
                query = query.eq("project_id", project_id)
            
            query = query.order("start_datetime", desc=True)
            response = query.execute()
            
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error obteniendo eventos para {attendee_email}: {str(e)}")
            return []
    
    def get_events_in_date_range(self, 
                                project_id: str,
                                start_datetime: datetime,
                                end_datetime: datetime) -> List[Dict[str, Any]]:
        """
        Obtiene eventos en un rango de fechas específico.
        
        Args:
            project_id: ID del proyecto
            start_datetime: Fecha/hora de inicio
            end_datetime: Fecha/hora de fin
            
        Returns:
            Lista de eventos en el rango
        """
        try:
            response = (self.client.table("calendar_events")
                       .select("*")
                       .eq("project_id", project_id)
                       .gte("start_datetime", start_datetime.isoformat())
                       .lte("end_datetime", end_datetime.isoformat())
                       .eq("status", "confirmed")
                       .order("start_datetime")
                       .execute())
            
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error obteniendo eventos en rango para proyecto {project_id}: {str(e)}")
            return [] 