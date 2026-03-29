"""
Database client for table operations.
Now uses direct PostgreSQL via SQLAlchemy instead of Supabase.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.database import SyncDatabase

logger = logging.getLogger("root")


class SupabaseClient:
    """
    Client for interacting with PostgreSQL database.
    Drop-in replacement - all method signatures preserved.
    """

    def __init__(self):
        """Initialize database client."""
        self.client = SyncDatabase()
        logger.debug("SupabaseClient initialized (PostgreSQL direct)")

    def get_apis_by_project_id(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all APIs for a specific project."""
        try:
            response = self.client.table("apis").select("*").eq("project_id", project_id).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error fetching APIs for project {project_id}: {str(e)}")
            return []

    def get_api_by_name(self, project_id: str, api_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific API by name within a project."""
        try:
            response = self.client.table("apis").select("*").eq("project_id", project_id).eq("api_name", api_name).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching API {api_name} for project {project_id}: {str(e)}")
            return None

    def create_api(self, api_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new API configuration."""
        try:
            response = self.client.table("apis").insert(api_data).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creating API: {str(e)}")
            return None

    def update_api(self, api_id: str, api_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing API configuration."""
        try:
            response = self.client.table("apis").update(api_data).eq("id", api_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error updating API {api_id}: {str(e)}")
            return None

    def delete_api(self, api_id: str) -> bool:
        """Delete an API configuration."""
        try:
            self.client.table("apis").delete().eq("id", api_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting API {api_id}: {str(e)}")
            return False

    # Calendar Integration Methods
    def get_calendar_integration(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get the Google Calendar integration for a project."""
        try:
            response = self.client.table("calendar_integrations").select("*").eq("project_id", project_id).eq("is_active", True).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching calendar integration for project {project_id}: {str(e)}")
            return None

    def create_calendar_integration(self, integration_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new calendar integration."""
        try:
            response = self.client.table("calendar_integrations").insert(integration_data).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creating calendar integration: {str(e)}")
            return None

    def update_calendar_integration(self, integration_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing calendar integration."""
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
        """Crea un nuevo evento en la tabla calendar_events."""
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
        """Obtiene un evento por su ID."""
        try:
            response = self.client.table("calendar_events").select("*").eq("id", event_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error obteniendo evento {event_id}: {str(e)}")
            return None

    def get_calendar_event_by_google_id(self, google_event_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene un evento por su google_event_id."""
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
        """Obtiene eventos de un proyecto con filtros opcionales."""
        try:
            query = self.client.table("calendar_events").select("*", count="exact").eq("project_id", project_id)

            if start_date:
                query = query.gte("start_datetime", start_date.isoformat())
            if end_date:
                query = query.lte("end_datetime", end_date.isoformat())
            if status:
                query = query.eq("status", status)

            query = query.order("start_datetime", desc=True)

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
        """Actualiza un evento existente."""
        try:
            response = self.client.table("calendar_events").update(update_data).eq("id", event_id).execute()
            if response.data and len(response.data) > 0:
                logger.info(f"Evento actualizado exitosamente: {event_id}")
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error actualizando evento {event_id}: {str(e)}")
            return None

    def delete_calendar_event(self, event_id: str) -> bool:
        """Elimina un evento (eliminacion fisica)."""
        try:
            self.client.table("calendar_events").delete().eq("id", event_id).execute()
            logger.info(f"Evento eliminado exitosamente: {event_id}")
            return True
        except Exception as e:
            logger.error(f"Error eliminando evento {event_id}: {str(e)}")
            return False

    def soft_delete_calendar_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Marca un evento como cancelado (eliminacion logica)."""
        try:
            update_data = {"status": "cancelled"}
            return self.update_calendar_event(event_id, update_data)
        except Exception as e:
            logger.error(f"Error cancelando evento {event_id}: {str(e)}")
            return None

    def get_events_by_attendee_email(self, attendee_email: str, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene eventos por email del asistente."""
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
        """Obtiene eventos en un rango de fechas especifico."""
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
