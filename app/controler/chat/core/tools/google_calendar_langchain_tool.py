import logging
import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from langchain.tools import BaseTool
import pytz

try:
    from langchain_google_community import CalendarToolkit
    from langchain_google_community.calendar.utils import (
        build_resource_service,
        get_google_credentials,
    )
    from langchain_google_community.calendar.create_event import CalendarCreateEvent
    from langchain_google_community.calendar.search_events import CalendarSearchEvents
    from langchain_google_community.calendar.update_event import CalendarUpdateEvent
    from langchain_google_community.calendar.delete_event import CalendarDeleteEvent
    LANGCHAIN_GOOGLE_AVAILABLE = True
except ImportError:
    LANGCHAIN_GOOGLE_AVAILABLE = False
    logging.warning("langchain-google-community no está disponible. Instalar con: pip install langchain-google-community[calendar]")

from app.controler.chat.store.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)

class GoogleCalendarLangChainTool(BaseTool):
    name: str = "google_calendar_langchain"
    description: str = """
    🗓️ HERRAMIENTA GOOGLE CALENDAR TOOLKIT (LANGCHAIN) 🗓️
    
    Herramienta profesional de calendario basada en CalendarToolkit de LangChain.
    Proporciona acceso completo a Google Calendar API con autenticación automática.
    
    FUNCIONALIDADES PRINCIPALES:
    ✅ Crear eventos con invitados y Google Meet
    ✅ Buscar eventos por título, fecha o rango
    ✅ Actualizar eventos existentes
    ✅ Eliminar eventos
    ✅ Obtener información de calendarios
    ✅ Verificar disponibilidad en tiempo real
    
    ACCIONES DISPONIBLES:
    
    📅 CREAR EVENTO:
    google_calendar_langchain(
        action="create_event",
        summary="Reunión Cliente",
        start_datetime="2024-01-15T15:00:00",
        end_datetime="2024-01-15T16:00:00",
        timezone="America/Santiago",
        location="Oficina Principal",
        description="Reunión estratégica",
        attendees=["cliente@email.com"],
        reminders=[{"method": "popup", "minutes": 30}],
        include_meet=True,
        color_id="2"
    )
    
    🔍 BUSCAR EVENTOS:
    google_calendar_langchain(
        action="search_events",
        query="reunión",
        start_date="2024-01-15",
        end_date="2024-01-20",
        max_results=10
    )
    
    ✏️ ACTUALIZAR EVENTO:
    google_calendar_langchain(
        action="update_event",
        event_id="abc123def456",
        summary="Nuevo título",
        description="Nueva descripción"
    )
    
    🗑️ ELIMINAR EVENTO:
    google_calendar_langchain(
        action="delete_event",
        event_id="abc123def456"
    )
    
    📋 LISTAR CALENDARIOS:
    google_calendar_langchain(
        action="get_calendars_info"
    )
    
    🕐 FECHA ACTUAL:
    google_calendar_langchain(
        action="get_current_datetime"
    )
    
    CONFIGURACIÓN:
    - Zona horaria por defecto: America/Santiago (Chile)
    - Autenticación: credentials.json y token.json
    - Google Meet automático en eventos
    - Notificaciones por email y popup
    
    PARÁMETROS COMUNES:
    - action: Acción a realizar (obligatorio)
    - summary/title: Título del evento
    - start_datetime: Fecha/hora inicio (ISO format)
    - end_datetime: Fecha/hora fin (ISO format)
    - timezone: Zona horaria (default: America/Santiago)
    - description: Descripción del evento
    - location: Ubicación del evento
    - attendees: Lista de emails de invitados
    - include_meet: Incluir Google Meet (true/false)
    - color_id: ID de color del evento (1-11)
    """
    
    def __init__(self, project_id: str = None, **kwargs):
        super().__init__(**kwargs)
        self._project_id = project_id
        self._supabase_client = SupabaseClient()
        self._toolkit = None
        self._tools_cache = {}
        
        # Verificar disponibilidad de dependencias
        if not LANGCHAIN_GOOGLE_AVAILABLE:
            logger.error("❌ langchain-google-community no está disponible")
            self._available = False
        else:
            self._available = True
            
    @property
    def project_id(self):
        return getattr(self, '_project_id', None)
        
    @property
    def supabase_client(self):
        return getattr(self, '_supabase_client', None)
        
    class Config:
        arbitrary_types_allowed = True
    
    def _init_toolkit(self) -> bool:
        """Inicializa el CalendarToolkit de LangChain"""
        try:
            if not self._available:
                logger.error("❌ langchain-google-community no disponible")
                return False
                
            if self._toolkit:
                return True
                
            # Verificar archivos de credenciales
            credentials_file = "credentials.json"
            token_file = "token.json"
            
            if not os.path.exists(credentials_file):
                logger.error(f"❌ Archivo de credenciales no encontrado: {credentials_file}")
                return False
            
            try:
                # Obtener credenciales con los scopes necesarios
                credentials = get_google_credentials(
                    token_file=token_file,
                    scopes=["https://www.googleapis.com/auth/calendar"],
                    client_secrets_file=credentials_file,
                )
                
                # Construir el servicio de API
                api_resource = build_resource_service(credentials=credentials)
                
                # Inicializar el toolkit
                self._toolkit = CalendarToolkit(api_resource=api_resource)
                
                # Cachear las herramientas individuales
                tools = self._toolkit.get_tools()
                for tool in tools:
                    tool_name = tool.__class__.__name__
                    self._tools_cache[tool_name] = tool
                    
                logger.info(f"✅ CalendarToolkit inicializado con {len(tools)} herramientas")
                return True
                
            except Exception as auth_error:
                logger.error(f"❌ Error de autenticación: {str(auth_error)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error inicializando CalendarToolkit: {str(e)}")
            return False
    
    def _get_project_timezone(self) -> str:
        """Obtiene la zona horaria del proyecto desde configuración"""
        try:
            if not self.project_id:
                return "America/Santiago"
                
            response = self.supabase_client.client.table("agenda").select("general_settings").eq("project_id", self.project_id).execute()
            
            if response.data and len(response.data) > 0:
                general_settings = response.data[0].get("general_settings", {})
                timezone = general_settings.get("timezone", "America/Santiago")
                logger.info(f"🌍 Zona horaria del proyecto: {timezone}")
                return timezone
            else:
                logger.warning(f"⚠️ No se encontró configuración para project_id: {self.project_id}")
                return "America/Santiago"
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo zona horaria: {str(e)}")
            return "America/Santiago"
    
    def _create_event(self, **kwargs) -> str:
        """Crea un evento usando CalendarCreateEvent"""
        try:
            tool = self._tools_cache.get("CalendarCreateEvent")
            if not tool:
                logger.error("❌ CalendarCreateEvent no disponible")
                return "❌ Error: Herramienta de creación no disponible"
            
            # Preparar parámetros con valores por defecto
            timezone = kwargs.get("timezone", self._get_project_timezone())
            include_meet = kwargs.get("include_meet", True)
            
            params = {
                "summary": kwargs.get("summary", kwargs.get("title", "Evento sin título")),
                "start_datetime": kwargs["start_datetime"],
                "end_datetime": kwargs["end_datetime"],
                "timezone": timezone,
                "description": kwargs.get("description", ""),
                "location": kwargs.get("location", ""),
                "conference_data": include_meet,
            }
            
            # Agregar attendees si se proporcionan
            attendees = kwargs.get("attendees", [])
            if attendees:
                if isinstance(attendees, str):
                    attendees = [attendees]
                params["attendees"] = attendees
            
            # Agregar recordatorios
            reminders = kwargs.get("reminders", [{"method": "popup", "minutes": 30}])
            params["reminders"] = reminders
            
            # Agregar color si se especifica
            color_id = kwargs.get("color_id")
            if color_id:
                params["color_id"] = str(color_id)
            
            logger.info(f"📅 Creando evento con parámetros: {params}")
            result = tool.invoke(params)
            
            logger.info(f"✅ Evento creado exitosamente: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error creando evento: {str(e)}")
            return f"❌ Error creando evento: {str(e)}"
    
    def _search_events(self, **kwargs) -> str:
        """Busca eventos usando CalendarSearchEvents"""
        try:
            tool = self._tools_cache.get("CalendarSearchEvents")
            if not tool:
                logger.error("❌ CalendarSearchEvents no disponible")
                return "❌ Error: Herramienta de búsqueda no disponible"
            
            params = {}
            
            # Agregar query de búsqueda
            if "query" in kwargs:
                params["query"] = kwargs["query"]
            
            # Agregar rango de fechas
            if "start_date" in kwargs:
                params["start_date"] = kwargs["start_date"]
            if "end_date" in kwargs:
                params["end_date"] = kwargs["end_date"]
                
            # Número máximo de resultados
            params["max_results"] = kwargs.get("max_results", 10)
            
            logger.info(f"🔍 Buscando eventos con parámetros: {params}")
            result = tool.invoke(params)
            
            logger.info(f"✅ Búsqueda completada")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error buscando eventos: {str(e)}")
            return f"❌ Error buscando eventos: {str(e)}"
    
    def _update_event(self, **kwargs) -> str:
        """Actualiza un evento usando CalendarUpdateEvent"""
        try:
            tool = self._tools_cache.get("CalendarUpdateEvent")
            if not tool:
                logger.error("❌ CalendarUpdateEvent no disponible")
                return "❌ Error: Herramienta de actualización no disponible"
            
            event_id = kwargs.get("event_id")
            if not event_id:
                return "❌ Error: event_id es requerido para actualizar evento"
            
            params = {"event_id": event_id}
            
            # Agregar campos a actualizar
            if "summary" in kwargs or "title" in kwargs:
                params["summary"] = kwargs.get("summary", kwargs.get("title"))
            if "description" in kwargs:
                params["description"] = kwargs["description"]
            if "start_datetime" in kwargs:
                params["start_datetime"] = kwargs["start_datetime"]
            if "end_datetime" in kwargs:
                params["end_datetime"] = kwargs["end_datetime"]
            if "location" in kwargs:
                params["location"] = kwargs["location"]
                
            logger.info(f"✏️ Actualizando evento {event_id} con parámetros: {params}")
            result = tool.invoke(params)
            
            logger.info(f"✅ Evento actualizado exitosamente")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error actualizando evento: {str(e)}")
            return f"❌ Error actualizando evento: {str(e)}"
    
    def _delete_event(self, **kwargs) -> str:
        """Elimina un evento usando CalendarDeleteEvent"""
        try:
            tool = self._tools_cache.get("CalendarDeleteEvent")
            if not tool:
                logger.error("❌ CalendarDeleteEvent no disponible")
                return "❌ Error: Herramienta de eliminación no disponible"
            
            event_id = kwargs.get("event_id")
            if not event_id:
                return "❌ Error: event_id es requerido para eliminar evento"
            
            params = {"event_id": event_id}
            
            logger.info(f"🗑️ Eliminando evento {event_id}")
            result = tool.invoke(params)
            
            logger.info(f"✅ Evento eliminado exitosamente")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error eliminando evento: {str(e)}")
            return f"❌ Error eliminando evento: {str(e)}"
    
    def _get_calendars_info(self, **kwargs) -> str:
        """Obtiene información de calendarios usando GetCalendarsInfo"""
        try:
            tool = self._tools_cache.get("GetCalendarsInfo")
            if not tool:
                logger.error("❌ GetCalendarsInfo no disponible")
                return "❌ Error: Herramienta de información de calendarios no disponible"
            
            logger.info("📋 Obteniendo información de calendarios")
            result = tool.invoke({})
            
            logger.info("✅ Información de calendarios obtenida")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo información de calendarios: {str(e)}")
            return f"❌ Error obteniendo información de calendarios: {str(e)}"
    
    def _get_current_datetime(self, **kwargs) -> str:
        """Obtiene la fecha/hora actual usando GetCurrentDatetime"""
        try:
            tool = self._tools_cache.get("GetCurrentDatetime")
            if not tool:
                # Fallback manual si la herramienta no está disponible
                timezone = self._get_project_timezone()
                tz = pytz.timezone(timezone)
                now = datetime.now(tz)
                return f"Fecha y hora actual: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            
            logger.info("🕐 Obteniendo fecha/hora actual")
            result = tool.invoke({})
            
            logger.info("✅ Fecha/hora actual obtenida")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo fecha/hora actual: {str(e)}")
            # Fallback en caso de error
            timezone = self._get_project_timezone()
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            return f"Fecha y hora actual: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    
    def _run(self, action: str, **kwargs) -> str:
        """Ejecuta la acción especificada"""
        try:
            # Verificar disponibilidad
            if not self._available:
                return "❌ Error: langchain-google-community no está disponible. Instalar con: pip install langchain-google-community[calendar]"
            
            # Inicializar toolkit si es necesario
            if not self._init_toolkit():
                return "❌ Error: No se pudo inicializar el CalendarToolkit. Verificar credenciales de Google."
            
            # Mapeo de acciones
            action_map = {
                "create_event": self._create_event,
                "search_events": self._search_events,
                "update_event": self._update_event,
                "delete_event": self._delete_event,
                "get_calendars_info": self._get_calendars_info,
                "get_current_datetime": self._get_current_datetime,
            }
            
            if action not in action_map:
                available_actions = ", ".join(action_map.keys())
                return f"❌ Error: Acción '{action}' no reconocida. Acciones disponibles: {available_actions}"
            
            # Ejecutar acción
            logger.info(f"🚀 Ejecutando acción: {action}")
            return action_map[action](**kwargs)
            
        except Exception as e:
            logger.error(f"❌ Error ejecutando acción {action}: {str(e)}")
            return f"❌ Error ejecutando acción {action}: {str(e)}"

# Función auxiliar para usar como tool de LangChain
def google_calendar_langchain_tool(project_id: str = None):
    """Factory function para crear la herramienta"""
    return GoogleCalendarLangChainTool(project_id=project_id)

# Instancia global por defecto
google_calendar_langchain = GoogleCalendarLangChainTool() 