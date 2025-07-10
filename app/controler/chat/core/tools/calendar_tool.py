import os
import logging
from datetime import datetime, timedelta
from typing_extensions import Annotated
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.controler.chat.store.persistence import Persist
from app.resources.constants import CALENDAR_INTEGRATIONS_TABLE
from .calendar_utils import (
    CHILE_TZ, DIAS_MAP, format_date_spanish, create_slot_dict,
    normalize_to_chile_timezone, get_day_name_spanish, parse_day_name_to_weekday
)

logger = logging.getLogger(__name__)

def get_project_calendar_config(project_id: str, agenda_data: dict = None) -> dict:
    """
    🚀 FUNCIÓN CENTRAL para obtener configuración de calendario del proyecto desde tabla agenda en Supabase.
    
    OPTIMIZADA para evitar consultas duplicadas usando cache desde agenda_tool.
    
    Args:
        project_id: ID del proyecto
        agenda_data: Datos de agenda desde cache (opcional, evita consulta duplicada)
        
    Returns:
        dict: Configuración completa del calendario con valores por defecto si no existe
    """
    try:
        if not project_id:
            logger.warning("No project_id proporcionado, usando configuración por defecto")
            return get_default_calendar_config()
        
        # ✅ PRIORIZAR CACHE - evitar consulta duplicada
        if agenda_data:
            logger.info("📅 ✅ Usando agenda_data desde cache (sin consulta duplicada)")
            response_data = [agenda_data]  # Simular formato de respuesta
        else:
            # ⚠️ FALLBACK - consulta directa solo si no hay cache
            logger.warning("📅 ⚠️ No hay cache disponible, realizando consulta directa")
            from app.controler.chat.store.supabase_client import SupabaseClient
            supabase_client = SupabaseClient()
            response = supabase_client.client.table("agenda").select("*").eq("project_id", project_id).execute()
            response_data = response.data
        
        logger.info(f"Configuración de agenda obtenida: {response_data}")
        
        if response_data and len(response_data) > 0:
            current_agenda_data = response_data[0]
            workflow_settings = current_agenda_data.get("workflow_settings", {})
            general_settings = current_agenda_data.get("general_settings", {})
            
            # Extraer configuración de calendario desde workflow_settings.AGENDA_COMPLETA
            agenda_settings = workflow_settings.get("AGENDA_COMPLETA", {})
            
            # Combinar configuración personalizada con valores por defecto
            config = get_default_calendar_config()
            
            # Procesar configuración granular de horarios
            schedule = agenda_settings.get("schedule", {})
            working_days = []
            earliest_hour = 24  # Inicializar con valor alto
            latest_hour = 0     # Inicializar con valor bajo
            
            if schedule:
                # Extraer días activos y calcular horas de trabajo
                for day_name, day_config in schedule.items():
                    if day_config.get("enabled", False):
                        working_days.append(day_name)
                        
                        # Analizar franjas horarias para encontrar horas extremas
                        time_slots = day_config.get("time_slots", [])
                        for slot in time_slots:
                            start_time = slot.get("start", "09:00")
                            end_time = slot.get("end", "18:00")
                            
                            # Convertir a enteros para comparación
                            try:
                                start_hour = int(start_time.split(":")[0])
                                end_hour = int(end_time.split(":")[0])
                                
                                earliest_hour = min(earliest_hour, start_hour)
                                latest_hour = max(latest_hour, end_hour)
                            except (ValueError, IndexError):
                                logger.warning(f"Formato de hora inválido en {day_name}: {start_time}-{end_time}")
                
                logger.info(f"📅 Configuración granular procesada:")
                logger.info(f"   - Días laborales: {working_days}")
                logger.info(f"   - Hora más temprana: {earliest_hour}:00")
                logger.info(f"   - Hora más tardía: {latest_hour}:00")
            
            # Actualizar configuración con valores extraídos o por defecto
            config.update({
                "default_duration": agenda_settings.get("default_duration_minutes", config["default_duration"] * 60) / 60,  # Convertir a horas
                "start_hour": earliest_hour if earliest_hour < 24 else config["start_hour"],
                "end_hour": latest_hour if latest_hour > 0 else config["end_hour"],
                "working_days": working_days if working_days else config["working_days"],
                "auto_include_meet": general_settings.get("auto_include_meet", config.get("auto_include_meet", True)),
                "buffer_minutes": agenda_settings.get("buffer_minutes", config["buffer_minutes"]),
                "timezone": general_settings.get("timezone", config["timezone"])
            })
            
            logger.info(f"✅ Configuración de calendario obtenida desde tabla agenda para proyecto {project_id}: {config}")
            return config
        else:
            logger.warning(f"No se encontró configuración de agenda para proyecto {project_id}, usando configuración por defecto")
            return get_default_calendar_config()
            
    except Exception as e:
        logger.error(f"Error obteniendo configuración de agenda para proyecto {project_id}: {str(e)}")
        return get_default_calendar_config()

def get_default_calendar_config() -> dict:
    """
    Configuración por defecto para el calendario cuando no hay configuración del proyecto.
    """
    return {
        "default_duration": 1.0,  # 1 hora
        "start_hour": 9,          # 9 AM
        "end_hour": 18,           # 6 PM
        "working_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "auto_include_meet": True,
        "buffer_minutes": 15,
        "timezone": "America/Santiago"
    }

# normalize_to_chile_timezone ahora se importa desde calendar_utils

@tool(parse_docstring=False)
def google_calendar_tool(query: str, state: Annotated[dict, InjectedState]) -> str:
    """Herramienta integral para gestión de calendario Google. Maneja todas las operaciones de calendario de forma autónoma.
    
    🎯 PROPÓSITO: Gestión completa de eventos en Google Calendar con configuración automática para zona horaria de Chile.
    
    📋 CASOS DE USO PRINCIPALES:
    - Buscar horarios disponibles para reuniones
    - Crear eventos con invitados y Google Meet automático
    - Consultar, actualizar y eliminar eventos existentes
    - Verificar disponibilidad en rangos de tiempo específicos
    
    🔧 FORMATO DE CONSULTA: [ACCIÓN]|[PARÁMETROS]
    
    📌 ACCIONES DISPONIBLES:
    
    🔍 BÚSQUEDA Y CONSULTA:
    - list_events|days=7: Lista eventos de los próximos N días
    - search_events|title=Reunión|date=2023-06-15: Busca eventos por título y/o fecha
    - get_event|event_id=abc123: Obtiene detalles de un evento específico
    - check_availability|start=2023-06-15T16:00:00|end=2023-06-15T17:00:00: Verifica disponibilidad
    
    🎯 BÚSQUEDA DE HORARIOS LIBRES:
    - find_available_slots: Encuentra próximos 3 horarios disponibles (configuración estándar: 60 min, horario laboral)
    - find_available_slots|duration=1.5|start_hour=10|end_hour=16: Búsqueda personalizada
    - find_available_slots|day=miércoles|duration=1: Busca en día específico de la semana
    - find_available_slots|specific_date=2025-07-09|duration=1: Busca en fecha específica (YYYY-MM-DD)
    
    ✨ GESTIÓN DE EVENTOS:
    - create_event|title=Reunión Cliente|start=2023-06-15T15:00:00|end=2023-06-15T16:00:00|description=Reunión|attendees=email@domain.com|meet=true
    - update_event|event_id=abc123|title=Nuevo Título|description=Nueva descripción
    - delete_event|event_id=abc123: Elimina evento
    
    ⚙️ CONFIGURACIÓN AUTOMÁTICA:
    - Zona horaria: Chile (America/Santiago) - conversión automática
    - Google Meet: Se agrega automáticamente cuando meet=true
    - Duración estándar: 60 minutos para nuevos eventos
    - Horario laboral: 09:00-18:00 para búsqueda de slots
    
    📧 INTEGRACIÓN CON CONTACTOS:
    - Requiere email del usuario para crear eventos con attendees
    - Se integra automáticamente con save_contact_tool para obtener emails
    - Los emails se validan antes de crear eventos
    
    🎌 CONSIDERACIONES ESPECIALES:
    - Verifica conflictos automáticamente antes de crear eventos
    - Maneja errores de integración de forma elegante
    
    💡 FLUJO RECOMENDADO PARA AGENDAR:
    1. Ejecutar find_available_slots para mostrar opciones al usuario
    2. Usuario selecciona o propone horario alternativo
    3. Verificar disponibilidad si es horario propuesto por usuario
    4. Confirmar con usuario antes de crear evento
    5. Crear evento con toda la información necesaria
    
    Args:
        query: Consulta estructurada con formato [ACCIÓN]|[PARÁMETROS]
        state: Estado inyectado que contiene configuración del proyecto
    
    Returns:
        str: Resultado de la operación de calendario, incluyendo detalles del evento o información de disponibilidad
        
    Ejemplos:
        - "find_available_slots" → Muestra próximos 3 horarios disponibles
        - "create_event|title=Reunión|start=2023-06-15T15:00:00|end=2023-06-15T16:00:00|attendees=usuario@email.com|meet=true"
        - "find_available_slots|day=viernes|duration=2" → Busca slots de 2 horas el viernes
    """
    try:
        # Extract project info
        project = state.get("project")
        if not project:
            return "Error: No project information found in the state"
        
        # Get project ID and configuration
        project_id = project.id if hasattr(project, 'id') else getattr(project, 'project_id', None)
        
        # 🚀 OBTENER CONFIGURACIÓN DEL PROYECTO UNA SOLA VEZ (optimizado con cache)
        agenda_config = state.get('agenda_config')
        cached_agenda_data = agenda_config.get('cached_agenda_data') if agenda_config else None
        
        project_config = get_project_calendar_config(project_id, cached_agenda_data)
        logger.info(f"🚀 Usando configuración del proyecto para calendario: {project_config}")
        
        # Parse the query
        parts = query.split('|')
        if len(parts) < 1:
            return "Error: Invalid query format. Use ACTION|PARAMETERS format"
        
        action = parts[0].strip().lower()
        
        # Get credentials from stored integration
        credentials = get_google_credentials(project_id)
        if not credentials:
            return "No Google Calendar integration found for this project. Please set up the integration first."
        
        # Build the Calendar API service
        service = build('calendar', 'v3', credentials=credentials)
        
        # Execute the requested action - 🚀 TODAS LAS FUNCIONES USAN project_config
        if action == 'list_events':
            return list_events(service, parts[1:] if len(parts) > 1 else [], project_config)
        elif action == 'search_events':
            return search_events(service, parts[1:] if len(parts) > 1 else [], project_config)
        elif action == 'create_event':
            return create_event(service, parts[1:] if len(parts) > 1 else [], state, project_config)
        elif action == 'get_event':
            return get_event(service, parts[1:] if len(parts) > 1 else [], project_config)
        elif action == 'update_event':
            return update_event(service, parts[1:] if len(parts) > 1 else [], project_config)
        elif action == 'delete_event':
            return delete_event(service, parts[1:] if len(parts) > 1 else [], project_config)
        elif action == 'check_availability':
            return check_availability(service, parts[1:] if len(parts) > 1 else [], project_config)
        elif action == 'find_available_slots':
            # Pasar project_id en project_config para búsqueda granular
            project_config_with_id = project_config.copy()
            project_config_with_id['project_id'] = project_id
            return find_next_available_slots(service, parts[1:] if len(parts) > 1 else [], project_config_with_id, state)
        else:
            return f"Unknown action: {action}. Supported actions are list_events, search_events, create_event, get_event, update_event, delete_event, check_availability, and find_available_slots."
            
    except Exception as e:
        logger.error(f"Error in Google Calendar tool: {str(e)}")
        return f"Error interacting with Google Calendar: {str(e)}"

def get_google_credentials(project_id):
    """
    Get stored Google Calendar credentials for the project using the Persist class.
    
    This function:
    1. Retrieves the stored credentials from the calendar_integrations table
    2. Creates and returns a Google Credentials object
    
    Returns None if no valid credentials are found
    """
    try:
        # Get the calendar integration for this project using Persist
        db = Persist()
        integration = db.find_one(CALENDAR_INTEGRATIONS_TABLE, {"project_id": project_id, "is_active": True})
        
        if not integration:
            logger.warning(f"No calendar integration found for project {project_id}")
            return None
        
        # Check if tokens have expired
        token_expiry = datetime.fromisoformat(integration["token_expiry"]) if integration.get("token_expiry") else None
        if token_expiry and token_expiry <= datetime.utcnow():
            logger.warning(f"Calendar integration tokens have expired for project {project_id}")
            # In a real implementation, you would add a token refresh mechanism here
            return None
        
        # Create Google credentials object
        credentials = Credentials(
            token=integration["access_token"],
            refresh_token=integration["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
        
        return credentials
    except Exception as e:
        logger.error(f"Error getting Google Calendar credentials: {str(e)}")
        return None

def list_events(service, params, project_config=None):
    """List upcoming events from the user's calendar"""
    try:
        # Parse parameters
        days = 7  # Default to 7 days
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                if key.strip().lower() == 'days':
                    try:
                        days = int(value.strip())
                    except ValueError:
                        return f"Invalid value for days: {value}. Must be an integer."
        
        # Calculate time range
        now = datetime.utcnow()
        end_time = now + timedelta(days=days)
        
        # Call the Calendar API
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            timeMax=end_time.isoformat() + 'Z',
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"No upcoming events found in the next {days} days."
            
        # Format the events for display
        response = f"Upcoming events for the next {days} days:\n\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            start_time = datetime.fromisoformat(start.replace('Z', '+00:00')) if 'T' in start else start
            summary = event.get('summary', 'Unnamed event')
            event_id = event.get('id', 'No ID')
            response += f"- {start_time}: {summary} (ID: {event_id})\n"
            
        return response
            
    except HttpError as error:
        return f"Error listing events: {error}"

def search_events(service, params, project_config=None):
    """Search for events by title or date"""
    try:
        # Parse parameters
        title = None
        date = None
        days = 365  # Default to searching a year ahead
        
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'title':
                    title = value
                elif key == 'date':
                    date = value
                elif key == 'days':
                    try:
                        days = int(value)
                    except ValueError:
                        return f"Invalid value for days: {value}. Must be an integer."
        
        if not title and not date:
            return "Error: You must specify at least 'title' or 'date' parameter"
        
        # Calculate time range
        now = datetime.utcnow()
        end_time = now + timedelta(days=days)
        
        # Call the Calendar API
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            timeMax=end_time.isoformat() + 'Z',
            maxResults=50,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Filter events based on title and/or date
        filtered_events = []
        for event in events:
            event_title = event.get('summary', '').lower()
            event_start = event['start'].get('dateTime', event['start'].get('date'))
            
            match_title = title is None or title.lower() in event_title
            match_date = date is None or date in event_start
            
            if match_title and match_date:
                filtered_events.append(event)
        
        if not filtered_events:
            return f"No events found matching the criteria."
            
        # Format the events for display
        response = f"Found {len(filtered_events)} matching events:\n\n"
        for event in filtered_events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            start_time = datetime.fromisoformat(start.replace('Z', '+00:00')) if 'T' in start else start
            summary = event.get('summary', 'Unnamed event')
            event_id = event.get('id', 'No ID')
            response += f"- {start_time}: {summary} (ID: {event_id})\n"
            
        return response
        
    except HttpError as error:
        return f"Error searching events: {error}"

def check_time_conflicts(service, start_time, end_time):
    """
    Verifica si hay eventos existentes que se solapan con el horario especificado
    MEJORADO: Incluye validación de conexión y debugging detallado
    
    Args:
        service: Google Calendar API service
        start_time: Hora de inicio del nuevo evento (formato ISO)
        end_time: Hora de fin del nuevo evento (formato ISO)
    
    Returns:
        Lista de eventos que se solapan con el horario especificado
    """
    try:
        # ✅ VALIDAR QUE EL SERVICE ESTÉ FUNCIONANDO
        if not service:
            logger.error("❌ Google Calendar service no disponible")
            raise Exception("Google Calendar service no disponible")
        
        # ✅ VALIDAR FORMATO DE FECHAS
        if not start_time or not end_time:
            logger.error(f"❌ Fechas inválidas: start='{start_time}', end='{end_time}'")
            raise Exception("Fechas de inicio y fin son requeridas")
        
        # Normalizar fechas a zona horaria de Chile para comparaciones consistentes
        start_time_normalized = normalize_to_chile_timezone(start_time)
        end_time_normalized = normalize_to_chile_timezone(end_time)
        
        # Convertir strings a datetime para comparaciones
        new_start = datetime.fromisoformat(start_time_normalized)
        new_end = datetime.fromisoformat(end_time_normalized)
        
        # ✅ VALIDAR QUE LA FECHA DE INICIO SEA ANTERIOR A LA DE FIN
        if new_start >= new_end:
            logger.error(f"❌ Fecha de inicio debe ser anterior a fecha de fin: {new_start} >= {new_end}")
            raise Exception("Fecha de inicio debe ser anterior a fecha de fin")
        
        # Buscar eventos en un rango más amplio (día completo) para verificar solapamientos
        day_start = new_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = new_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Asegurar que las fechas tengan formato correcto para Google Calendar API
        day_start_iso = day_start.isoformat()
        day_end_iso = day_end.isoformat()
        
        # ✅ VALIDAR FORMATO PARA GOOGLE CALENDAR API
        # Google Calendar API requiere fechas con zona horaria o UTC (con Z)
        # Pero NUNCA ambos: -03:00Z es inválido
        if day_start_iso.endswith('Z') and ('+' in day_start_iso[:-1] or '-' in day_start_iso[-10:-1]):
            logger.error(f"❌ Formato de fecha inválido para Google API: {day_start_iso}")
            raise Exception("Formato de fecha inválido para Google Calendar API")
        
        logger.debug(f"🔍 VERIFICANDO CONFLICTOS:")
        logger.debug(f"   📅 Horario solicitado: {start_time} to {end_time}")
        logger.debug(f"   🌎 Normalizado a Chile: {start_time_normalized} to {end_time_normalized}")
        logger.debug(f"   🔍 Buscando en rango: {day_start_iso} to {day_end_iso}")
        
                # ✅ INTENTAR CONEXIÓN CON GOOGLE CALENDAR API
        try:
                events_result = service.events().list(
                calendarId='primary',
                timeMin=day_start_iso,
                timeMax=day_end_iso,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
        except HttpError as api_error:
            logger.error(f"❌ Error de API de Google Calendar: {api_error}")
            # ✅ NO DEVOLVER LISTA VACÍA - PROPAGAR EL ERROR
            raise Exception(f"Error consultando Google Calendar: {api_error}")
        except Exception as conn_error:
            logger.error(f"❌ Error de conexión con Google Calendar: {conn_error}")
            raise Exception(f"Error de conexión con Google Calendar: {conn_error}")
        
        events = events_result.get('items', [])
        logger.debug(f"📊 EVENTOS ENCONTRADOS EN EL DÍA: {len(events)}")
        
        # ✅ LOG DETALLADO DE EVENTOS ENCONTRADOS (para debugging)
        if events:
            logger.debug("📋 EVENTOS EN EL CALENDARIO:")
            for i, event in enumerate(events):
                event_title = event.get('summary', 'Sin título')
                event_start = event['start'].get('dateTime', 'start' in event and event['start'].get('date'))
                event_end = event['end'].get('dateTime', 'end' in event and event['end'].get('date'))
                logger.debug(f"   {i+1}. '{event_title}': {event_start} - {event_end}")
        else:
            logger.debug("✅ NO HAY EVENTOS EN EL CALENDARIO PARA ESTE DÍA")
        
        conflicts = []
        for event in events:
            event_start_str = event['start'].get('dateTime', event['start'].get('date'))
            event_end_str = event['end'].get('dateTime', event['end'].get('date'))
            
            # ✅ SKIP EVENTOS DE DÍA COMPLETO CORRECTAMENTE
            if 'T' not in event_start_str:  # Es fecha completa (all-day event)
                logger.info(f"   ⏭️  Saltando evento de día completo: {event.get('summary', 'Sin título')}")
                continue
            
            # Convertir a datetime para comparar
            try:
                event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
            except Exception as date_error:
                logger.error(f"❌ Error parseando fechas del evento '{event.get('summary')}': {date_error}")
                continue
            
            # ✅ VERIFICAR SOLAPAMIENTO CON LÓGICA CLARA
            # Solapamiento ocurre si: (nuevo_inicio < evento_fin) AND (nuevo_fin > evento_inicio)
            has_overlap = (new_start < event_end and new_end > event_start)
            
            logger.debug(f"   🔍 Verificando '{event.get('summary', 'Sin título')}':")
            logger.debug(f"      📅 Evento: {event_start} - {event_end}")
            logger.debug(f"      📅 Nuevo:  {new_start} - {new_end}")
            logger.debug(f"      ⚡ ¿Conflicto? {has_overlap}")
            
            if has_overlap:
                conflicts.append({
                    'summary': event.get('summary', 'Evento sin título'),
                    'start': event_start_str,
                    'end': event_end_str,
                    'id': event.get('id')
                })
                logger.warning(f"❌ CONFLICTO DETECTADO: {event.get('summary')} desde {event_start_str} hasta {event_end_str}")
        
        logger.info(f"📊 RESUMEN DE VERIFICACIÓN:")
        logger.info(f"   📅 Horario solicitado: {start_time} - {end_time}")
        logger.info(f"   📋 Eventos en el día: {len(events)}")
        logger.info(f"   ❌ Conflictos encontrados: {len(conflicts)}")
        
        if conflicts:
            conflict_titles = [c['summary'] for c in conflicts]
            logger.warning(f"⚠️  HORARIO NO DISPONIBLE - Conflictos con: {', '.join(conflict_titles)}")
        else:
            logger.info(f"✅ HORARIO DISPONIBLE - Sin conflictos")
        
        return conflicts
        
    except Exception as e:
        logger.error(f"❌ ERROR CRÍTICO en check_time_conflicts: {str(e)}")
        # ✅ NO DEVOLVER LISTA VACÍA - PROPAGAR EL ERROR PARA MANEJO CORRECTO
        raise Exception(f"Error verificando disponibilidad en calendario: {str(e)}")

def create_event(service, params, state=None, project_config=None):
    """Create a new event on the calendar with conflict checking and attendee support"""
    try:
        # 🚀 USAR CONFIGURACIÓN DEL PROYECTO
        if not project_config:
            project_config = get_default_calendar_config()
        
        # Parse parameters - usar configuración del proyecto
        now_chile = datetime.now(CHILE_TZ)
        default_duration = project_config.get("default_duration", 1.0)
        default_start = now_chile + timedelta(hours=1)
        default_end = default_start + timedelta(hours=default_duration)
        
        event_data = {
            'summary': 'New Event',
            'description': '',
            'start': {
                'dateTime': default_start.isoformat(),
            },
            'end': {
                'dateTime': default_end.isoformat(),
            },
            'attendees': []
        }
        
        attendee_emails = []
        force_create = False  # Para forzar creación a pesar de conflictos
        add_meet = project_config.get("auto_include_meet", True)  # 🚀 Usar config del proyecto
        
        # Debug: Log all parameters received
        logger.info(f"Received parameters: {params}")
        
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                logger.info(f"Processing parameter: {key} = {value}")
                
                if key == 'title' or key == 'summary':
                    event_data['summary'] = value
                elif key == 'description':
                    event_data['description'] = value
                elif key == 'start':
                    event_data['start']['dateTime'] = normalize_to_chile_timezone(value)
                elif key == 'end':
                    event_data['end']['dateTime'] = normalize_to_chile_timezone(value)
                elif key == 'attendees' or key == 'guests' or key == 'emails':
                    # Soporte para múltiples emails separados por coma
                    attendee_emails = [email.strip() for email in value.split(',')]
                elif key == 'force_create' or key == 'force':
                    force_create = value.lower() in ['true', '1', 'yes', 'sí', 'si']
                    logger.info(f"force_create parameter found: {key} = {value} -> {force_create}")
                elif key == 'meet' or key == 'google_meet' or key == 'video_call':
                    add_meet = value.lower() in ['true', '1', 'yes', 'sí', 'si']
                    logger.info(f"add_meet parameter found: {key} = {value} -> {add_meet}")
        
        # Debug final state
        logger.info(f"Final force_create value: {force_create}")
        logger.info(f"Final add_meet value: {add_meet}")
        
        # Agregar Google Meet si se solicita
        if add_meet:
            event_data['conferenceData'] = {
                'createRequest': {
                    'requestId': f"meet-{int(datetime.now().timestamp())}",  # ID único para la solicitud
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'  # Especifica que queremos Google Meet
                    }
                }
            }
            logger.info("Google Meet conference added to event")
        
        # Agregar attendees al evento
        for email in attendee_emails:
            if email:  # Verificar que no esté vacío
                event_data['attendees'].append({
                    'email': email,
                    'responseStatus': 'needsAction'  # Marca que necesita respuesta del invitado
                })
        
        # Configuraciones adicionales para asegurar envío de correos
        if event_data['attendees']:
            event_data['guestsCanInviteOthers'] = False  # Los invitados no pueden invitar a otros
            event_data['guestsCanModify'] = False  # Los invitados no pueden modificar el evento
            event_data['guestsCanSeeOtherGuests'] = True  # Los invitados pueden ver otros invitados
            event_data['reminders'] = {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # Recordatorio por email 24 horas antes
                    {'method': 'popup', 'minutes': 10}  # Recordatorio popup 10 minutos antes
                ]
            }
        else:
            # Si no hay attendees, remover la clave para evitar errores
            del event_data['attendees']
        
        logger.info("*********")
        logger.info(f"Event data: {event_data}")
        
        # Verificar conflictos de horario (SIEMPRE se verifica)
        conflicts = check_time_conflicts(service, event_data['start']['dateTime'], event_data['end']['dateTime'])
        logger.info(f"Conflicts found: {len(conflicts)}, force_create: {force_create}")
        
        if conflicts and not force_create:
            conflict_list = "\n".join([f"- {conflict['summary']} ({conflict['start']} - {conflict['end']})" for conflict in conflicts])
            logger.info("BLOCKING event creation due to conflicts")
            return f"⚠️ CONFLICTO DETECTADO: Ya tienes eventos en este horario:\n{conflict_list}\n\n¿Deseas crear el evento de todas formas? Usa 'force_create=true' para crear el evento a pesar de los conflictos."
        
        if conflicts and force_create:
            logger.info("FORCING event creation despite conflicts")
        
        # Crear el evento - sendNotifications=True asegura que se envíen invitaciones por correo
        # Si se incluye Google Meet, necesitamos conferenceDataVersion=1
        insert_params = {
            'calendarId': 'primary',
            'body': event_data,
            'sendNotifications': True,  # Forzar envío de notificaciones por correo
            'sendUpdates': 'all'  # Enviar actualizaciones a todos los invitados
        }
        
        if add_meet:
            insert_params['conferenceDataVersion'] = 1  # Requerido para Google Meet
            
        event = service.events().insert(**insert_params).execute()
        
        # Preparar respuesta con información adicional
        response = f"✅ Evento creado exitosamente: {event.get('htmlLink')}\n"
        response += f"📅 Título: {event_data['summary']}\n"
        response += f"🕐 Inicio: {event_data['start']['dateTime']}\n"
        response += f"🕑 Fin: {event_data['end']['dateTime']}\n"
        
        if attendee_emails:
            response += f"👥 Invitados: {', '.join(attendee_emails)}\n"
            response += f"📧 Se han enviado invitaciones por correo automáticamente a todos los invitados.\n"
            response += f"🔔 Los invitados recibirán recordatorios por email 24 horas antes del evento.\n"
        
        # Información sobre Google Meet
        if add_meet and 'conferenceData' in event:
            meet_link = event['conferenceData'].get('entryPoints', [{}])[0].get('uri', 'No disponible')
            response += f"📹 Google Meet: {meet_link}\n"
            response += f"🔗 El enlace de Google Meet se incluye automáticamente en las invitaciones.\n"
        elif add_meet:
            response += f"📹 Google Meet solicitado (el enlace se generará momentáneamente)\n"
        
        # Si había conflictos pero se forzó la creación
        if conflicts and force_create:
            response += f"⚠️ Nota: Se creó el evento a pesar de tener {len(conflicts)} conflicto(s) de horario\n"
        
        return response
        
    except HttpError as error:
        return f"Error creating event: {error}"

def get_event(service, params, project_config=None):
    """Get details about a specific event"""
    try:
        # Parse parameters
        event_id = None
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                if key.strip().lower() == 'event_id':
                    event_id = value.strip()
        
        if not event_id:
            return "Error: event_id parameter is required"
        
        # Get the event
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        # Format the event details
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        response = f"Event details:\n"
        response += f"Title: {event.get('summary', 'Unnamed event')}\n"
        response += f"Start: {start}\n"
        response += f"End: {end}\n"
        response += f"Description: {event.get('description', '')}\n"
        
        return response
        
    except HttpError as error:
        return f"Error getting event: {error}"

def update_event(service, params, project_config=None):
    """Update an existing event's details"""
    try:
        # Parse parameters
        event_id = None
        update_data = {}
        
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'event_id':
                    event_id = value
                elif key == 'title' or key == 'summary':
                    update_data['summary'] = value
                elif key == 'description':
                    update_data['description'] = value
                elif key == 'start':
                    update_data['start'] = {'dateTime': value}
                elif key == 'end':
                    update_data['end'] = {'dateTime': value}
        
        if not event_id:
            return "Error: event_id parameter is required"
        
        if not update_data:
            return "Error: No update parameters provided. Specify at least one field to update."
        
        # First, get the current event
        current_event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        # Apply updates to the current event
        for key, value in update_data.items():
            current_event[key] = value
        
        # Update the event
        updated_event = service.events().update(
            calendarId='primary', 
            eventId=event_id, 
            body=current_event
        ).execute()
        
        return f"Event updated successfully: {updated_event.get('htmlLink')}"
        
    except HttpError as error:
        return f"Error updating event: {error}"

def delete_event(service, params, project_config=None):
    """Delete an event from the calendar"""
    try:
        # Parse parameters
        event_id = None
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                if key.strip().lower() == 'event_id':
                    event_id = value.strip()
        
        if not event_id:
            return "Error: event_id parameter is required. Use search_events|title=Event Title or list_events to find the event ID first."
        
        # Delete the event
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        
        return f"Event with ID {event_id} has been successfully deleted."
        
    except HttpError as error:
        if hasattr(error, 'resp') and error.resp.status == 404:
            return f"Error: Event with ID {event_id} was not found. The event might not exist or may have been already deleted. Use search_events|title=Event Title to find the correct event ID."
        return f"Error deleting event: {error}"

def check_availability(service, params, project_config=None):
    """Check if a specific time slot is available"""
    try:
        # Parse parameters
        start_time = None
        end_time = None
        
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'start':
                    start_time = normalize_to_chile_timezone(value)
                elif key == 'end':
                    end_time = normalize_to_chile_timezone(value)
        
        if not start_time:
            return "Error: 'start' parameter is required. Format: check_availability|start=2024-01-15T16:00:00|end=2024-01-15T17:00:00"
        
        # Si no se proporciona hora de fin, usar duración por defecto del proyecto
        if not end_time:
            if not project_config:
                project_config = get_default_calendar_config()
            default_duration = project_config.get("default_duration", 1.0)
            start_dt = datetime.fromisoformat(start_time)
            end_dt = start_dt + timedelta(hours=default_duration)
            end_time = end_dt.isoformat()
        
        # Verificar conflictos
        conflicts = check_time_conflicts(service, start_time, end_time)
        
        if not conflicts:
            return f"✅ DISPONIBLE: El horario del {start_time} al {end_time} está libre."
        else:
            conflict_list = "\n".join([f"- {conflict['summary']} ({conflict['start']} - {conflict['end']})" for conflict in conflicts])
            return f"❌ NO DISPONIBLE: Hay {len(conflicts)} evento(s) en conflicto:\n{conflict_list}"
        
    except HttpError as error:
        return f"Error checking availability: {error}"
    except Exception as e:
        return f"Error processing availability check: {e}"

def find_next_available_slots(service, params, project_config=None, state=None):
    """Find the next available time slots for meetings with granular schedule support"""
    try:
        # ✅ PASO 0: VALIDAR CONSISTENCIA DE FECHAS EN LOS PARÁMETROS
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                # Validar consistencia para parámetros que contienen fechas/días
                if key in ['day', 'title'] and value:
                    es_consistente, mensaje_validacion, fecha_corregida = validate_date_consistency(value)
                    if not es_consistente:
                        logger.warning(f"❌ Inconsistencia de fecha detectada en {key}: {mensaje_validacion}")
                        return mensaje_validacion

        # ✅ VALIDAR CONECTIVIDAD CON GOOGLE CALENDAR AL INICIO
        try:
            # Test de conectividad: intentar listar calendarios
            calendars_result = service.calendarList().list(maxResults=1).execute()
            logger.info(f"✅ CONEXIÓN CON GOOGLE CALENDAR VERIFICADA: {len(calendars_result.get('items', []))} calendario(s) accesible(s)")
        except Exception as conn_test_error:
            logger.error(f"❌ FALLO DE CONECTIVIDAD con Google Calendar: {conn_test_error}")
            return f"❌ **Error de conexión con Google Calendar**: No se puede acceder al calendario. Verifica que la integración esté configurada correctamente.\n\nDetalle del error: {str(conn_test_error)}"
        
        # 🚀 USAR CONFIGURACIÓN DEL PROYECTO
        if not project_config:
            project_config = get_default_calendar_config()
        
        duration_hours = project_config.get("default_duration", 1.0)
        preferred_start_hour = project_config.get("start_hour", 9)
        preferred_end_hour = project_config.get("end_hour", 18)
        working_days = project_config.get("working_days", ["monday", "tuesday", "wednesday", "thursday", "friday"])
        
        # 🚀 OBTENER max_slots_to_show desde configuración del proyecto
        max_slots_to_show = 5  # Valor por defecto
        
        # 🚀 OBTENER CONFIGURACIÓN GRANULAR DESDE STATE (evitar consulta duplicada)
        granular_schedule = None
        
        # Primero intentar obtener configuración desde el state (pasada por agenda_tool)
        agenda_config = None
        if state and hasattr(state, 'get'):
            agenda_config = state.get('agenda_config')
        elif state and isinstance(state, dict):
            agenda_config = state.get('agenda_config')
        
        if agenda_config:
            # Usar configuración pasada desde agenda_tool (evita consulta duplicada)
            granular_schedule = agenda_config.get('granular_schedule', {})
            config_max_slots = agenda_config.get('max_slots_to_show', 5)
            max_slots_to_show = config_max_slots
            logger.info(f"📅 ✅ Configuración granular obtenida desde agenda_tool (sin consulta duplicada): {len(granular_schedule)} días configurados")
            logger.info(f"📊 ✅ max_slots_to_show desde cache: {max_slots_to_show}")
        else:
            # Fallback: obtener configuración granular directamente (solo si no viene del state)
            project_id = project_config.get('project_id') if isinstance(project_config, dict) else None
            
            if project_id:
                try:
                    from app.controler.chat.store.supabase_client import SupabaseClient
                    supabase_client = SupabaseClient()
                    response = supabase_client.client.table("agenda").select("workflow_settings").eq("project_id", project_id).execute()
                    
                    if response.data and len(response.data) > 0:
                        workflow_settings = response.data[0].get("workflow_settings", {})
                        agenda_settings = workflow_settings.get("AGENDA_COMPLETA", {})
                        busqueda_settings = workflow_settings.get("BUSQUEDA_HORARIOS", {})
                        granular_schedule = agenda_settings.get("schedule", {})
                        
                        # Obtener max_slots_to_show desde configuración de agenda
                        config_max_slots = busqueda_settings.get("max_slots_to_show", 5)
                        max_slots_to_show = config_max_slots
                        
                        logger.warning(f"📅 ⚠️ Configuración granular cargada directamente (consulta adicional): {len(granular_schedule)} días configurados")
                        logger.warning(f"📊 ⚠️ max_slots_to_show desde consulta directa: {max_slots_to_show}")
                    else:
                        logger.warning(f"No se encontró configuración de agenda para project_id: {project_id}")
                except Exception as e:
                    logger.warning(f"Error cargando configuración granular: {str(e)}")
            else:
                logger.warning("No se proporcionó project_id ni configuración desde agenda_tool")
        
        # Parse parameters (pueden sobrescribir la configuración del proyecto)
        specific_day = None  # Para buscar en un día específico
        specific_date = None  # 🆕 Para buscar en una fecha específica (YYYY-MM-DD)
        week_offset = 0  # 🆕 Para comenzar búsqueda desde semana específica
        
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'duration':
                    duration_hours = float(value)
                elif key == 'start_hour':
                    preferred_start_hour = int(value)
                elif key == 'end_hour':
                    preferred_end_hour = int(value)
                elif key == 'day' or key == 'weekday':
                    specific_day = value.lower()
                elif key == 'specific_date':  # 🆕 NUEVO: Soporte para fechas específicas
                    specific_date = value
                    logger.info(f"🗓️ Fecha específica solicitada: {specific_date}")
                elif key == 'limit':
                    max_slots_to_show = int(value)
                elif key == 'week_offset':  # 🆕 Nuevo parámetro
                    week_offset = int(value)
                    logger.info(f"🗓️ Week offset configurado: {week_offset} semanas adelante")
        
        # Obtener la fecha y hora actual en Chile
        now_chile = datetime.now(CHILE_TZ)
        
        logger.info(f"🔍 INICIANDO BÚSQUEDA DE HORARIOS DISPONIBLES:")
        logger.info(f"   📅 Fecha actual: {now_chile.strftime('%Y-%m-%d %H:%M')} (Chile)")
        logger.info(f"   ⏱️  Duración: {duration_hours} horas")
        logger.info(f"   🕘 Horario laboral: {preferred_start_hour}:00 - {preferred_end_hour}:00")
        logger.info(f"   📊 Máximo slots a mostrar: {max_slots_to_show}")
        logger.info(f"   👤 Día específico solicitado: {specific_day or 'No especificado'}")
        
        # Función helper para obtener franjas horarias de un día específico
        def get_time_slots_for_day(day_name, granular_schedule):
            """Obtiene las franjas horarias disponibles para un día específico"""
            if not granular_schedule:
                # Fallback: usar horario general
                return [(preferred_start_hour, preferred_end_hour)]
            
            day_config = granular_schedule.get(day_name, {})
            if not day_config.get("enabled", False):
                return []  # Día no habilitado
            
            time_slots = day_config.get("time_slots", [])
            if not time_slots:
                return [(preferred_start_hour, preferred_end_hour)]  # Fallback
            
            # Convertir franjas horarias a tuplas de enteros
            converted_slots = []
            for slot in time_slots:
                try:
                    start_time = slot.get("start", "09:00")
                    end_time = slot.get("end", "18:00")
                    start_hour = int(start_time.split(":")[0])
                    end_hour = int(end_time.split(":")[0])
                    converted_slots.append((start_hour, end_hour))
                except (ValueError, IndexError):
                    logger.warning(f"Formato de hora inválido en {day_name}: {slot}")
                    continue
            
            return converted_slots if converted_slots else [(preferred_start_hour, preferred_end_hour)]
        
        # ✅ FUNCIÓN HELPER MEJORADA PARA VERIFICAR DISPONIBILIDAD
        def check_slot_availability_safe(slot_start, slot_end):
            """Verifica disponibilidad de un slot con manejo de errores mejorado y caché"""
            try:
                # 🆕 OPTIMIZACIÓN: Verificar si el slot está en el pasado
                if slot_start <= now_chile:
                    logger.debug(f"         ⏰ {slot_start.strftime('%H:%M')} - Slot en el pasado, saltando")
                    return False, []
                
                # 🆕 OPTIMIZACIÓN: Caché simple para evitar verificaciones duplicadas
                slot_key = f"{slot_start.isoformat()}_{slot_end.isoformat()}"
                if not hasattr(check_slot_availability_safe, '_cache'):
                    check_slot_availability_safe._cache = {}
                
                if slot_key in check_slot_availability_safe._cache:
                    cached_result = check_slot_availability_safe._cache[slot_key]
                    logger.debug(f"         📋 {slot_start.strftime('%H:%M')} - Usando resultado en caché: {'Disponible' if cached_result[0] else 'No disponible'}")
                    return cached_result
                
                # Verificar conflictos reales
                conflicts = check_time_conflicts(service, slot_start.isoformat(), slot_end.isoformat())
                result = (len(conflicts) == 0, conflicts)
                
                # Guardar en caché
                check_slot_availability_safe._cache[slot_key] = result
                
                return result
                
            except Exception as check_error:
                logger.error(f"❌ Error verificando disponibilidad para {slot_start}: {check_error}")
                # ✅ RETORNAR FALSE (no disponible) si hay error de verificación
                return False, [{'error': str(check_error)}]
        
        # Lista para almacenar las fechas disponibles
        available_slots = []
        
        # Inicializar variables de tracking para todas las rutas de código
        days_checked = 0
        slots_found = 0
        
        # Usar mapeo centralizado desde utilidades
        
        # 🆕 NUEVA LÓGICA: Si se especifica una fecha específica, buscar solo en esa fecha
        if specific_date:
            try:
                # Parsear la fecha específica - soportar múltiples formatos
                if 'T' in specific_date:
                    # Formato ISO datetime: 2025-07-21T09:00:00
                    target_date = datetime.fromisoformat(specific_date.replace('T', ' ').split('.')[0]).date()
                else:
                    # Formato simple: 2025-07-21
                    target_date = datetime.strptime(specific_date, "%Y-%m-%d").date()
                target_weekday = target_date.weekday()
                day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                target_day_name = day_names[target_weekday]
                
                logger.info(f"🔍 BÚSQUEDA ESPECÍFICA DE FECHA:")
                logger.info(f"   📅 Fecha objetivo: {target_weekday} (0=Lunes, 6=Domingo)")
                logger.info(f"   📅 Fecha actual: {get_day_name_spanish(now_chile.weekday())} {now_chile.strftime('%Y-%m-%d %H:%M')} (weekday={now_chile.weekday()})")
                logger.info(f"   ⏱️  Duración: {duration_hours} horas")
                logger.info(f"   🕘 Horario preferido: {preferred_start_hour}:00 - {preferred_end_hour}:00")
                
                # Verificar si la fecha está en el pasado
                if target_date < now_chile.date():
                    return f"❌ La fecha {specific_date} ya pasó. Por favor elige una fecha futura."
                
                # Verificar si es día laboral
                if target_day_name not in working_days:
                    working_days_esp = {
                        "monday": "lunes", "tuesday": "martes", "wednesday": "miércoles", 
                        "thursday": "jueves", "friday": "viernes", "saturday": "sábado", "sunday": "domingo"
                    }
                    target_day_esp = working_days_esp[target_day_name]
                    dias_disponibles = [working_days_esp[day] for day in working_days]
                    return f"❌ Lo siento, no tengo horarios disponibles los {target_day_esp}s. Mis días laborales son: {', '.join(dias_disponibles)}. ¿Te gustaría ver opciones para alguno de estos días?"
                
                # Obtener franjas horarias para este día
                time_slots = get_time_slots_for_day(target_day_name, granular_schedule)
                
                # Actualizar contador de días verificados
                days_checked = 1
                
                # Buscar slots en la fecha específica
                for start_hour, end_hour in time_slots:
                    # 🆕 INTERSECCIÓN: Respetar el horario preferido por el usuario (ej. tarde)
                    effective_start_hour = max(start_hour, preferred_start_hour)
                    effective_end_hour = min(end_hour, preferred_end_hour)
                    
                    logger.debug(f"      🕒 Verificando franja {start_hour}:00-{end_hour}:00, ajustada a preferencia: {effective_start_hour}:00-{effective_end_hour}:00")

                    # Iterar sobre la franja ajustada
                    for hour in range(effective_start_hour, effective_end_hour - int(duration_hours) + 1):
                        # Si es hoy, no buscar horarios que ya pasaron
                        is_today = target_date == now_chile.date()
                        if is_today and hour <= now_chile.hour:
                            logger.debug(f"         ⏰ {hour}:00 - Ya pasó (hora actual: {now_chile.hour}:00)")
                            continue
                        
                        # Crear datetime para el slot
                        slot_start = datetime.combine(target_date, datetime.min.time().replace(hour=hour))
                        slot_start = slot_start.replace(tzinfo=CHILE_TZ)
                        slot_end = slot_start + timedelta(hours=duration_hours)
                        
                        # Verificar que el slot termine dentro de la franja horaria
                        if slot_end.hour > effective_end_hour or (slot_end.hour == effective_end_hour and slot_end.minute > 0):
                            logger.debug(f"         ❌ {hour}:00 - Slot excede franja horaria (termina a las {slot_end.strftime('%H:%M')})")
                            continue
                        
                        logger.debug(f"         🔍 Verificando disponibilidad para {hour}:00...")
                        is_available, conflicts_or_error = check_slot_availability_safe(slot_start, slot_end)
                        
                        if is_available:
                            slot_dict = create_slot_dict(slot_start, slot_end, duration_hours)
                            available_slots.append(slot_dict)
                            slots_found += 1
                            logger.info(f"         ✅ {hour}:00 DISPONIBLE - Slot #{slots_found}")
                            
                            # Si encontramos max_slots_to_show slots, paramos
                            if len(available_slots) >= max_slots_to_show:
                                break
                        else:
                            # Log detallado de por qué no está disponible
                            if conflicts_or_error and isinstance(conflicts_or_error, list) and len(conflicts_or_error) > 0:
                                if 'error' in conflicts_or_error[0]:
                                    logger.error(f"         ❌ {hour}:00 - Error verificando: {conflicts_or_error[0]['error']}")
                                else:
                                    conflict_titles = [c.get('summary', 'Evento sin título') for c in conflicts_or_error]
                                    logger.debug(f"         📅 {hour}:00 - No disponible, conflictos: {', '.join(conflict_titles)}")
                    
                    # Si ya encontramos suficientes slots, salir del loop de franjas
                    if len(available_slots) >= max_slots_to_show:
                        break
                
                if not available_slots:
                    return f"❌ No hay horarios disponibles para el {specific_date}. ¿Te gustaría ver opciones para otro día?"
                    
            except ValueError:
                return f"❌ Formato de fecha inválido: {specific_date}. Usa el formato YYYY-MM-DD (ejemplo: 2025-07-09)"
            except Exception as e:
                logger.error(f"Error procesando fecha específica {specific_date}: {str(e)}")
                return f"❌ Error procesando la fecha {specific_date}: {str(e)}"
        
        # Si se especifica un día, buscar solo en ese día
        elif specific_day:
            target_weekday = parse_day_name_to_weekday(specific_day)
            if target_weekday == -1:
                return f"❌ Día no reconocido: {specific_day}. Usa: lunes, martes, miércoles, jueves, viernes, sábado, domingo"
            
            day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            target_day_name = day_names[target_weekday]
            
            if target_day_name not in working_days:
                working_days_esp = {
                    "monday": "lunes", "tuesday": "martes", "wednesday": "miércoles", 
                    "thursday": "jueves", "friday": "viernes", "saturday": "sábado", "sunday": "domingo"
                }
                dias_disponibles = [working_days_esp[day] for day in working_days]
                return f"❌ Lo siento, no tengo horarios disponibles los {specific_day}s. Mis días laborales son: {', '.join(dias_disponibles)}. ¿Te gustaría ver opciones para alguno de estos días?"

            first_week_skipped = False
            first_week_date = None
            
            logger.info(f"🔍 BÚSQUEDA ESPECÍFICA DE DÍA: {target_day_name}")

            for week_offset_day in range(4):
                days_ahead = target_weekday - now_chile.weekday() + (week_offset_day * 7)
                
                if days_ahead < 0:
                    continue
                    
                current_date = now_chile.date() + timedelta(days=days_ahead)
                
                day_slots = []
                time_slots_for_day = get_time_slots_for_day(target_day_name, granular_schedule)

                for start_h, end_h in time_slots_for_day:
                    # 🆕 INTERSECCIÓN: Respetar el horario preferido por el usuario (ej. tarde)
                    effective_start_hour = max(start_h, preferred_start_hour)
                    effective_end_hour = min(end_h, preferred_end_hour)

                    logger.debug(f"      🕒 Verificando franja {start_h}:00-{end_h}:00, ajustada a preferencia: {effective_start_hour}:00-{effective_end_hour}:00")
                    
                    for hour in range(effective_start_hour, effective_end_hour - int(duration_hours) + 1):
                        slot_start = datetime.combine(current_date, datetime.min.time().replace(hour=hour))
                        slot_start = slot_start.replace(tzinfo=CHILE_TZ)
                        slot_end = slot_start + timedelta(hours=duration_hours)

                        is_available, _ = check_slot_availability_safe(slot_start, slot_end)
                        
                        if is_available:
                            day_slots.append(create_slot_dict(slot_start, slot_end, duration_hours))
                            if len(day_slots) >= max_slots_to_show:
                                break
                    if len(day_slots) >= max_slots_to_show:
                        break
                
                if day_slots:
                    available_slots.extend(day_slots)
                    break
                else:
                    if week_offset_day == 0:
                        first_week_skipped = True
                        first_week_date = current_date
            
            if not available_slots:
                logger.info(f"🔄 {specific_day} no disponible, buscando siguiente día hábil...")
                
                for day_offset in range(1, 14):
                    current_date = now_chile.date() + timedelta(days=day_offset)
                    current_day_name = day_names[current_date.weekday()]
                    
                    if current_day_name not in working_days:
                        continue
                    
                    time_slots = get_time_slots_for_day(current_day_name, granular_schedule)
                    
                    day_slots = []
                    for start_hour, end_hour in time_slots:
                        # 🆕 INTERSECCIÓN: Respetar el horario preferido por el usuario (ej. tarde)
                        effective_start_hour = max(start_hour, preferred_start_hour)
                        effective_end_hour = min(end_hour, preferred_end_hour)

                        logger.debug(f"      🕒 Verificando franja {start_hour}:00-{end_hour}:00, ajustada a preferencia: {effective_start_hour}:00-{effective_end_hour}:00")

                        for hour in range(effective_start_hour, effective_end_hour - int(duration_hours) + 1):
                            slot_start = datetime.combine(current_date, datetime.min.time().replace(hour=hour))
                            slot_start = slot_start.replace(tzinfo=CHILE_TZ)
                            slot_end = slot_start + timedelta(hours=duration_hours)
                            
                            is_available, _ = check_slot_availability_safe(slot_start, slot_end)
                            
                            if is_available:
                                day_slots.append(create_slot_dict(slot_start, slot_end, duration_hours))
                                if len(day_slots) >= max_slots_to_show:
                                    break
                        if len(day_slots) >= max_slots_to_show:
                            break
                    
                    if day_slots:
                        available_slots = day_slots
                        specific_day = get_day_name_spanish(current_date.weekday())
                        break
                
                if not available_slots:
                    return f"❌ No hay horarios disponibles en los próximos 14 días hábiles después de verificar el calendario real."
        else:
            start_day_offset = week_offset * 7
            end_day_offset = start_day_offset + 14
            
            logger.info(f"🔍 Buscando desde día {start_day_offset} hasta día {end_day_offset} (week_offset: {week_offset})...")
            days_checked = 0
            slots_found = 0
            
            for day_offset in range(start_day_offset, end_day_offset):
                current_date = now_chile.date() + timedelta(days=day_offset)
                
                day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                current_day_name = day_names[current_date.weekday()]
                
                # 1. Verificar si es día laboral
                if current_day_name not in working_days:
                    logger.info(f"   ⏭️  Saltando {current_date} ({current_day_name}) - No es día laboral")
                    continue
                
                # Si pasa las validaciones, contamos como día verificado
                days_checked += 1
                logger.debug(f"   📅 Verificando día {days_checked}: {current_date} ({current_day_name})")
                
                # Obtener franjas horarias
                time_slots = get_time_slots_for_day(current_day_name, granular_schedule)
                
                day_found_slot = False
                for start_hour, end_hour in time_slots:
                    # 🆕 INTERSECCIÓN: Respetar el horario preferido por el usuario (ej. tarde)
                    effective_start_hour = max(start_hour, preferred_start_hour)
                    effective_end_hour = min(end_hour, preferred_end_hour)
                    
                    logger.debug(f"      🕒 Verificando franja {start_hour}:00-{end_hour}:00, ajustada a preferencia: {effective_start_hour}:00-{effective_end_hour}:00")
                    
                    for hour in range(effective_start_hour, effective_end_hour - int(duration_hours) + 1):
                        # Saltar horarios pasados
                        if week_offset == 0 and day_offset == 0 and hour <= now_chile.hour:
                            continue
                        
                        slot_start = datetime.combine(current_date, datetime.min.time().replace(hour=hour))
                        slot_start = slot_start.replace(tzinfo=CHILE_TZ)
                        slot_end = slot_start + timedelta(hours=duration_hours)
                        
                        # Verificar disponibilidad
                        is_available, conflicts_or_error = check_slot_availability_safe(slot_start, slot_end)
                        
                        if is_available:
                            available_slots.append(create_slot_dict(slot_start, slot_end, duration_hours))
                            day_found_slot = True
                            slots_found += 1
                            logger.info(f"         ✅ {hour}:00 DISPONIBLE - Slot #{slots_found} encontrado")
                            if len(available_slots) >= max_slots_to_show:
                                break
                        else:
                            # ... (código de logging para no disponibles) ...
                            pass
                    
                    if day_found_slot:
                        break
                
                if len(available_slots) >= max_slots_to_show:
                    logger.info(f"✅ Se alcanzó el límite de {max_slots_to_show} slots, finalizando búsqueda")
                    break
                
                if days_checked >= 10:
                    logger.warning(f"⚠️ Límite de seguridad alcanzado: {days_checked} días verificados, finalizando búsqueda")
                    break
        
        logger.info(f"📊 RESUMEN FINAL DE BÚSQUEDA:")
        logger.info(f"   📅 Días verificados: {days_checked if not (specific_day or specific_date) else 'N/A (fecha específica)'}")
        logger.info(f"   ✅ Slots encontrados: {len(available_slots)}")
        logger.info(f"   🎯 Límite solicitado: {max_slots_to_show}")
        
        if not available_slots:
            if specific_date:
                return f"❌ No se encontraron horarios disponibles para el {specific_date} después de verificar el calendario real."
            elif specific_day:
                return f"❌ No se encontraron horarios disponibles para {specific_day} en las próximas 4 semanas después de verificar el calendario real."
            else:
                return "❌ No se encontraron horarios disponibles en los próximos 14 días hábiles después de verificar el calendario real."
        
        # Formatear respuesta
        if specific_date:
            # Formatear la fecha específica para mostrar en español
            try:
                target_date_obj = datetime.strptime(specific_date, "%Y-%m-%d")
                dias_semana = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
                dia_esp = dias_semana[target_date_obj.weekday()]
                mes_esp = meses[target_date_obj.month - 1]
                fecha_legible = f"{dia_esp} {target_date_obj.day} de {mes_esp}"
                response = f"📅 **Horarios disponibles para {fecha_legible} (verificados en calendario real):**\n\n"
            except:
                response = f"📅 **Horarios disponibles para {specific_date} (verificados en calendario real):**\n\n"
        elif specific_day:
            # Si se saltó la primera semana, explicar por qué
            if first_week_skipped and first_week_date:
                dias_semana = {'Monday': 'lunes', 'Tuesday': 'martes', 'Wednesday': 'miércoles', 
                              'Thursday': 'jueves', 'Friday': 'viernes', 'Saturday': 'sábado', 'Sunday': 'domingo'}
                meses = {'January': 'enero', 'February': 'febrero', 'March': 'marzo', 'April': 'abril',
                        'May': 'mayo', 'June': 'junio', 'July': 'julio', 'August': 'agosto',
                        'September': 'septiembre', 'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'}
                
                fecha_bloqueada = first_week_date.strftime("%A %d de %B")
                for eng, esp in dias_semana.items():
                    fecha_bloqueada = fecha_bloqueada.replace(eng, esp)
                for eng, esp in meses.items():
                    fecha_bloqueada = fecha_bloqueada.replace(eng, esp)
                
                response = f"⚠️ El {fecha_bloqueada} no está disponible por compromisos previos (verificado en calendario real).\n\n"
                response += f"📅 **Horarios disponibles para el próximo {specific_day}:**\n\n"
            else:
                # Verificar si encontramos el día solicitado originalmente o el siguiente día hábil
                original_day = params[0].split('=')[1] if len(params) > 0 and '=' in params[0] and 'day=' in params[0] else None
                if original_day and original_day != specific_day:
                    response = f"🔄 El {original_day} no está disponible (verificado en calendario real). Te muestro el siguiente día hábil:\n\n"
                    response += f"📅 **Horarios disponibles para {specific_day}:**\n\n"
                else:
                    response = f"📅 **Horarios disponibles para {specific_day} (verificados en calendario real):**\n\n"
        else:
            response = "📅 **Próximas fechas disponibles para reunión (verificadas en calendario real de Google):**\n\n"
        
        dias_semana = {
            'Monday': 'lunes', 'Tuesday': 'martes', 'Wednesday': 'miércoles', 
            'Thursday': 'jueves', 'Friday': 'viernes', 'Saturday': 'sábado', 'Sunday': 'domingo'
        }
        
        meses = {
            'January': 'enero', 'February': 'febrero', 'March': 'marzo', 'April': 'abril',
            'May': 'mayo', 'June': 'junio', 'July': 'julio', 'August': 'agosto',
            'September': 'septiembre', 'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
        }
        
        # Formatear cada slot con numeración manual para asegurar correcta enumeración
        for index, slot in enumerate(available_slots):
            numero = index + 1  # Asegurar que el número sea correcto
            
            # Debug: log the slot start datetime
            logger.debug(f"🔍 DEBUG SLOT {index}: slot['start'] = {slot['start']}")
            logger.debug(f"🔍 DEBUG SLOT {index}: slot['start'].weekday() = {slot['start'].weekday()}")
            logger.debug(f"🔍 DEBUG SLOT {index}: slot['start'].month = {slot['start'].month}")
            logger.debug(f"🔍 DEBUG SLOT {index}: slot['start'].day = {slot['start'].day}")
            
            # Usar date_str que ya está en español o formatear correctamente
            if 'date_str' in slot:
                fecha_esp = slot['date_str']
                logger.debug(f"🔍 DEBUG SLOT {index}: usando date_str = {fecha_esp}")
            else:
                # Usar utilidades centralizadas para formateo de fechas
                fecha_esp = format_date_spanish(slot['start'], include_year=True)
                logger.debug(f"🔍 DEBUG SLOT {index}: calculado fecha_esp = {fecha_esp}")
            
            # Debug: log the final values
            logger.debug(f"🔍 DEBUG SLOT {index}: numero={numero} - fecha_esp: {fecha_esp}")
            logger.debug(f"🔍 DEBUG SLOT {index}: year: {slot['start'].year}")
            logger.debug(f"🔍 DEBUG SLOT {index}: time: {slot['start'].strftime('%H:%M')}")
            
            response += f"{numero}. {fecha_esp.title()} a las {slot['start'].strftime('%H:%M')} horas\n"
        
        response += f"\n✅ **Horarios verificados contra tu calendario real de Google**\n"
        
        if specific_date:
            response += f"¿Alguno de estos horarios te acomoda? Solo dime el número o propón otra fecha."
        elif specific_day:
            response += f"¿Alguno de estos horarios para {specific_day} te acomoda? Solo dime el número o propón otra fecha."
        else:
            response += f"¿Cuál de estas fechas te acomoda más? Solo dime el número o propón otra fecha."
        
        return response
        
    except Exception as e:
        logger.error(f"❌ ERROR CRÍTICO en find_next_available_slots: {str(e)}")
        return f"❌ Error buscando horarios disponibles: {str(e)}\n\nPor favor verifica que la integración con Google Calendar esté configurada correctamente." 

def test_google_calendar_connection(service):
    """
    Función de diagnóstico para probar la conectividad real con Google Calendar
    
    Args:
        service: Google Calendar API service
        
    Returns:
        dict: Resultado del test con detalles de conectividad
    """
    try:
        logger.info("🔍 INICIANDO TEST DE CONECTIVIDAD CON GOOGLE CALENDAR...")
        
        # Test 1: Listar calendarios disponibles
        try:
            calendars_result = service.calendarList().list().execute()
            calendars = calendars_result.get('items', [])
            logger.info(f"✅ Test 1 PASADO: {len(calendars)} calendario(s) accesible(s)")
        except Exception as test1_error:
            logger.error(f"❌ Test 1 FALLIDO: Error listando calendarios - {test1_error}")
            return {
                'success': False,
                'error': f"No se pueden listar calendarios: {test1_error}",
                'test_details': {
                    'calendars_test': False,
                    'events_test': False,
                    'create_test': False
                }
            }
        
        # Test 2: Listar eventos del calendario principal
        try:
            now = datetime.now(CHILE_TZ)
            tomorrow = now + timedelta(days=1)
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now.isoformat(),
                timeMax=tomorrow.isoformat(),
                maxResults=5,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.info(f"✅ Test 2 PASADO: {len(events)} evento(s) encontrado(s) para hoy/mañana")
        except Exception as test2_error:
            logger.error(f"❌ Test 2 FALLIDO: Error listando eventos - {test2_error}")
            return {
                'success': False,
                'error': f"No se pueden listar eventos: {test2_error}",
                'test_details': {
                    'calendars_test': True,
                    'events_test': False,
                    'create_test': False
                }
            }
        
        # Test 3: Verificar permisos de escritura (crear evento de prueba y eliminarlo)
        try:
            test_start = now + timedelta(hours=1)
            test_end = test_start + timedelta(minutes=1)
            
            test_event = {
                'summary': '[TEST] Prueba de conectividad - ELIMINAR',
                'description': 'Evento de prueba creado automáticamente para verificar conectividad. Se eliminará inmediatamente.',
                'start': {'dateTime': test_start.isoformat()},
                'end': {'dateTime': test_end.isoformat()}
            }
            
            # Crear evento de prueba
            created_event = service.events().insert(calendarId='primary', body=test_event).execute()
            test_event_id = created_event.get('id')
            logger.info(f"✅ Test 3a PASADO: Evento de prueba creado con ID {test_event_id}")
            
            # Eliminar evento de prueba inmediatamente
            service.events().delete(calendarId='primary', eventId=test_event_id).execute()
            logger.info(f"✅ Test 3b PASADO: Evento de prueba eliminado correctamente")
            
        except Exception as test3_error:
            logger.error(f"❌ Test 3 FALLIDO: Error creando/eliminando evento de prueba - {test3_error}")
            return {
                'success': False,
                'error': f"No se pueden crear/eliminar eventos: {test3_error}",
                'test_details': {
                    'calendars_test': True,
                    'events_test': True,
                    'create_test': False
                }
            }
        
        logger.info("🎉 TODOS LOS TESTS DE CONECTIVIDAD PASARON")
        return {
            'success': True,
            'message': "Conectividad con Google Calendar verificada exitosamente",
            'test_details': {
                'calendars_test': True,
                'events_test': True,
                'create_test': True
            },
            'calendar_count': len(calendars),
            'events_today_tomorrow': len(events)
        }
        
    except Exception as e:
        logger.error(f"❌ ERROR CRÍTICO en test de conectividad: {str(e)}")
        return {
            'success': False,
            'error': f"Error crítico: {str(e)}",
            'test_details': {
                'calendars_test': False,
                'events_test': False,
                'create_test': False
            }
        }

@tool(parse_docstring=False)
def test_calendar_connectivity(query: str, state: Annotated[dict, InjectedState]) -> str:
    """Herramienta de diagnóstico para probar la conectividad real con Google Calendar.
    
    🎯 PROPÓSITO: Verificar que la integración con Google Calendar esté funcionando correctamente.
    
    Esta herramienta ejecuta una serie de tests para validar:
    1. Conexión con la API de Google Calendar
    2. Permisos de lectura (listar calendarios y eventos)  
    3. Permisos de escritura (crear y eliminar eventos de prueba)
    4. Formato correcto de fechas y zona horaria
    
    📋 CASOS DE USO:
    - Diagnosticar problemas de conectividad antes de agendar
    - Verificar que las credenciales estén funcionando
    - Confirmar que los permisos estén correctamente configurados
    - Debug de problemas de integración
    
    Args:
        query: Texto libre (no se usa, puede estar vacío)
        state: Estado inyectado que contiene configuración del proyecto
    
    Returns:
        str: Resultado detallado del test de conectividad
        
    Ejemplos de uso:
        - "test_calendar_connectivity" → Ejecuta todos los tests de conectividad
        - "probar calendario" → Ejecuta todos los tests de conectividad
    """
    try:
        # Extract project info
        project = state.get("project")
        if not project:
            return "❌ Error: No se encontró información del proyecto en el estado"
        
        # Get project ID
        project_id = project.id if hasattr(project, 'id') else getattr(project, 'project_id', None)
        if not project_id:
            return "❌ Error: No se pudo obtener el ID del proyecto"
        
        logger.info(f"🔍 INICIANDO TEST DE CONECTIVIDAD para proyecto {project_id}")
        
        # Get credentials
        credentials = get_google_credentials(project_id)
        if not credentials:
            return f"""❌ **Error de configuración**: No se encontró integración con Google Calendar para este proyecto.

🔧 **Para solucionarlo:**
1. Ve a la configuración del proyecto
2. Configura la integración con Google Calendar
3. Autoriza los permisos necesarios
4. Prueba nuevamente

💡 **Proyecto ID**: {project_id}"""
        
        # Build the Calendar API service
        try:
            service = build('calendar', 'v3', credentials=credentials)
            logger.info("✅ Servicio de Google Calendar creado exitosamente")
        except Exception as service_error:
            return f"❌ Error creando servicio de Google Calendar: {str(service_error)}"
        
        # Ejecutar tests de conectividad
        test_result = test_google_calendar_connection(service)
        
        if test_result['success']:
            calendar_count = test_result.get('calendar_count', 0)
            events_count = test_result.get('events_today_tomorrow', 0)
            
            return f"""✅ **CONECTIVIDAD CON GOOGLE CALENDAR VERIFICADA**

🎉 **Todos los tests pasaron exitosamente:**
• ✅ Conexión con API establecida
• ✅ Permisos de lectura confirmados
• ✅ Permisos de escritura confirmados
• ✅ Zona horaria configurada correctamente

📊 **Información del calendario:**
• 📅 Calendarios accesibles: {calendar_count}
• 📋 Eventos hoy/mañana: {events_count}
• 🌎 Zona horaria: Chile (America/Santiago)

🚀 **¡El sistema está listo para agendar reuniones!**"""
        else:
            test_details = test_result.get('test_details', {})
            error_msg = test_result.get('error', 'Error desconocido')
            
            status_tests = []
            status_tests.append(f"• {'✅' if test_details.get('calendars_test', False) else '❌'} Test de calendarios")
            status_tests.append(f"• {'✅' if test_details.get('events_test', False) else '❌'} Test de eventos")  
            status_tests.append(f"• {'✅' if test_details.get('create_test', False) else '❌'} Test de creación/eliminación")
            
            return f"""❌ **PROBLEMA DE CONECTIVIDAD DETECTADO**

🔍 **Resultado de los tests:**
{chr(10).join(status_tests)}

❌ **Error específico:** {error_msg}

🔧 **Posibles soluciones:**
1. Verificar que la integración con Google Calendar esté activa
2. Revisar que los permisos no hayan expirado
3. Reautorizar la conexión con Google Calendar
4. Contactar al administrador del sistema

💡 **Proyecto ID**: {project_id}"""
            
    except Exception as e:
        logger.error(f"❌ Error en test_calendar_connectivity: {str(e)}")
        return f"❌ Error ejecutando test de conectividad: {str(e)}"

def validate_date_consistency(text: str) -> tuple:
    """
    Valida la consistencia entre día de la semana mencionado y fecha específica
    
    Args:
        text: Texto del usuario que puede contener día y fecha
        
    Returns:
        Tupla (es_consistente, mensaje_validacion, fecha_corregida)
    """
    try:
        import re
        
        if not text:
            return True, "", None
            
        text_lower = text.lower()
        logger.info(f"🔍 VALIDANDO CONSISTENCIA DE FECHA en calendar_tool: '{text}'")
        
        # Mapeo de días en español
        dias_map = {
            'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2,
            'jueves': 3, 'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6
        }
        
        # Mapeo de meses en español
        meses_map = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }
        
        # Detectar si hay un día de la semana mencionado
        dia_mencionado = None
        dia_weekday = None
        for dia, weekday in dias_map.items():
            if dia in text_lower:
                dia_mencionado = dia
                dia_weekday = weekday
                break
        
        # Detectar si hay una fecha específica mencionada
        # Patrón: "X de mes" o "X de mes de año"
        fecha_pattern = r'(\d{1,2})\s+de\s+([a-záéíóúñ]+)(?:\s+de\s+(\d{4}))?'
        fecha_match = re.search(fecha_pattern, text_lower)
        
        if dia_mencionado and fecha_match:
            logger.info(f"   📅 Día detectado: {dia_mencionado} (weekday {dia_weekday})")
            logger.info(f"   📅 Fecha detectada: {fecha_match.group(0)}")
            
            # Extraer componentes de la fecha
            dia_numero = int(fecha_match.group(1))
            mes_nombre = fecha_match.group(2)
            año = int(fecha_match.group(3)) if fecha_match.group(3) else datetime.now().year
            
            # Validar que el mes sea válido
            if mes_nombre not in meses_map:
                return False, f"❌ Mes no reconocido: {mes_nombre}", None
            
            mes_numero = meses_map[mes_nombre]
            
            try:
                # Crear el objeto datetime para la fecha específica
                fecha_especifica = datetime(año, mes_numero, dia_numero)
                fecha_weekday = fecha_especifica.weekday()
                
                logger.info(f"   📊 COMPARACIÓN:")
                logger.info(f"      🗣️  Usuario dijo: {dia_mencionado} (weekday {dia_weekday})")
                # Usar mapeo correcto para mostrar el día real en el log
                dias_weekday_to_name = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                dia_real_log = dias_weekday_to_name[fecha_weekday]
                logger.info(f"      📅 Fecha real: {fecha_especifica.strftime('%Y-%m-%d')} es {dia_real_log} (weekday {fecha_weekday})")
                
                # Verificar consistencia
                if dia_weekday == fecha_weekday:
                    logger.info(f"   ✅ CONSISTENCIA VÁLIDA: {dia_mencionado} {dia_numero} de {mes_nombre} de {año}")
                    return True, f"✅ Fecha válida", fecha_especifica.strftime('%Y-%m-%d')
                else:
                    # Inconsistencia detectada - usar mapeo correcto de weekday a nombre
                    dias_weekday_to_name = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                    dia_real = dias_weekday_to_name[fecha_weekday]
                    
                    meses_esp = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                               'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
                    
                    fecha_legible = f"{dia_numero} de {meses_esp[mes_numero]} de {año}"
                    
                    logger.warning(f"   ❌ INCONSISTENCIA DETECTADA:")
                    logger.warning(f"      🗣️  Usuario dijo: '{dia_mencionado} {fecha_legible}'")
                    logger.warning(f"      📅 Pero el {fecha_legible} es {dia_real}, no {dia_mencionado}")
                    
                    mensaje_error = f"""❌ **Error en la fecha**: 

🗣️ **Dijiste:** "{dia_mencionado} {fecha_legible}"
📅 **Pero:** El {fecha_legible} es **{dia_real}**, no {dia_mencionado}

🤔 **¿Qué querías decir?**
1. **{dia_real} {fecha_legible}** (corregir el día)
2. **Próximo {dia_mencionado}** (buscar el siguiente {dia_mencionado})

💡 Por favor aclara cuál era tu intención."""
                    
                    return False, mensaje_error, fecha_especifica.strftime('%Y-%m-%d')
                    
            except ValueError as date_error:
                logger.error(f"   ❌ Fecha inválida: {dia_numero}/{mes_numero}/{año} - {date_error}")
                return False, f"❌ La fecha {dia_numero} de {mes_nombre} de {año} no es válida", None
        
        # Si no hay conflicto o solo hay una parte (día o fecha), es válido
        logger.info(f"   ✅ Sin inconsistencias detectadas")
        return True, "", None
        
    except Exception as e:
        logger.error(f"❌ Error validando consistencia de fecha: {str(e)}")
        return True, "", None  # En caso de error, permitir continuar