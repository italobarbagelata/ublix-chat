import os
import logging
from datetime import datetime, timedelta
import pytz
from typing_extensions import Annotated
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.controler.chat.store.persistence import Persist
from app.resources.constants import CALENDAR_INTEGRATIONS_TABLE

logger = logging.getLogger(__name__)

# Zona horaria de Chile
CHILE_TZ = pytz.timezone('America/Santiago')

def normalize_to_chile_timezone(datetime_str):
    """
    Normaliza una fecha/hora a la zona horaria de Chile
    
    Args:
        datetime_str: String de fecha/hora en formato ISO
    
    Returns:
        String de fecha/hora normalizado a zona horaria de Chile
    """
    try:
        logger.info(f"Normalizing timezone for: {datetime_str}")
        
        # Si ya tiene zona horaria
        if datetime_str.endswith('Z'):
            # UTC -> Chile
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            dt_utc = pytz.UTC.localize(dt.replace(tzinfo=None))
            dt_chile = dt_utc.astimezone(CHILE_TZ)
        elif '+' in datetime_str[-6:] or '-' in datetime_str[-6:]:
            # Ya tiene zona horaria -> Chile
            dt = datetime.fromisoformat(datetime_str)
            dt_chile = dt.astimezone(CHILE_TZ)
        else:
            # Sin zona horaria -> asumir que es hora de Chile
            dt_naive = datetime.fromisoformat(datetime_str)
            dt_chile = CHILE_TZ.localize(dt_naive)
        
        result = dt_chile.isoformat()
        logger.info(f"Normalized result: {result}")
        
        # Verificar que el resultado no tenga formato inválido (zona horaria + Z)
        if result.endswith('Z') and ('+' in result[:-1] or '-' in result[-10:-1]):
            logger.error(f"Invalid format detected: {result}")
            # Remover la Z si ya tiene zona horaria
            result = result[:-1]
            logger.info(f"Fixed format: {result}")
        
        return result
    except Exception as e:
        logger.error(f"Error normalizing timezone for {datetime_str}: {e}")
        # Si falla, devolver original con zona horaria de Chile
        fallback = datetime_str + '-03:00' if 'T' in datetime_str and not any(x in datetime_str for x in ['Z', '+', '-03:00', '-04:00']) else datetime_str
        logger.info(f"Fallback result: {fallback}")
        return fallback

@tool(parse_docstring=False)
def google_calendar_tool(query: str, state: Annotated[dict, InjectedState]) -> str:
    """This tool interacts with Google Calendar to manage events and schedules.
    
    Args:
        query: A structured query with format: 
               [ACTION]|[PARAMETERS]
               where ACTION can be: list_events, search_events, create_event, get_event, update_event, delete_event, or check_availability
               and PARAMETERS depend on the action:
               - list_events|days=7 (lists events for next 7 days)
               - search_events|title=Meeting|date=2023-06-15 (searches for events with matching title and/or date)
               - create_event|title=Meeting with Client|start=2023-06-15T15:00:00|end=2023-06-15T16:00:00|description=Discuss project status|attendees=user1@email.com,user2@email.com|force_create=true
               Note: All times are automatically converted to Chile timezone (America/Santiago)
               - get_event|event_id=abc123
               - update_event|event_id=abc123|title=New Title|description=Updated description
               - delete_event|event_id=abc123
               - check_availability|start=2023-06-15T16:00:00|end=2023-06-15T17:00:00
        state: Injected state containing project configuration
    
    Returns:
        Information about the calendar operations performed
    """
    try:
        # Extract project info
        project = state.get("project")
        if not project:
            return "Error: No project information found in the state"
        
        # Check if we have Google Calendar integration for this project
        # This would need to be set up in your project's database
        project_id = project.id
        
        # Parse the query
        parts = query.split('|')
        if len(parts) < 1:
            return "Error: Invalid query format. Use ACTION|PARAMETERS format"
        
        action = parts[0].strip().lower()
        
        # Get credentials from stored integration
        # This is a placeholder - you would need to implement credential storage and retrieval
        credentials = get_google_credentials(project_id)
        if not credentials:
            return "No Google Calendar integration found for this project. Please set up the integration first."
        
        # Build the Calendar API service
        service = build('calendar', 'v3', credentials=credentials)
        
        # Execute the requested action
        if action == 'list_events':
            return list_events(service, parts[1:] if len(parts) > 1 else [])
        elif action == 'search_events':
            return search_events(service, parts[1:] if len(parts) > 1 else [])
        elif action == 'create_event':
            return create_event(service, parts[1:] if len(parts) > 1 else [])
        elif action == 'get_event':
            return get_event(service, parts[1:] if len(parts) > 1 else [])
        elif action == 'update_event':
            return update_event(service, parts[1:] if len(parts) > 1 else [])
        elif action == 'delete_event':
            return delete_event(service, parts[1:] if len(parts) > 1 else [])
        elif action == 'check_availability':
            return check_availability(service, parts[1:] if len(parts) > 1 else [])
        else:
            return f"Unknown action: {action}. Supported actions are list_events, search_events, create_event, get_event, update_event, delete_event, and check_availability."
            
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

def list_events(service, params):
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

def search_events(service, params):
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
    
    Args:
        service: Google Calendar API service
        start_time: Hora de inicio del nuevo evento (formato ISO)
        end_time: Hora de fin del nuevo evento (formato ISO)
    
    Returns:
        Lista de eventos que se solapan con el horario especificado
    """
    try:
        # Normalizar fechas a zona horaria de Chile para comparaciones consistentes
        start_time_normalized = normalize_to_chile_timezone(start_time)
        end_time_normalized = normalize_to_chile_timezone(end_time)
        
        # Convertir strings a datetime para comparaciones
        new_start = datetime.fromisoformat(start_time_normalized)
        new_end = datetime.fromisoformat(end_time_normalized)
        
        # Buscar eventos en un rango más amplio (día completo) para verificar solapamientos
        day_start = new_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = new_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Asegurar que las fechas tengan formato correcto para Google Calendar API
        day_start_iso = day_start.isoformat()
        day_end_iso = day_end.isoformat()
        
        # Google Calendar API requiere fechas con zona horaria o UTC (con Z)
        # Pero NUNCA ambos: -03:00Z es inválido
        # Las fechas ya vienen de normalize_to_chile_timezone con zona horaria correcta
        
        logger.info(f"Checking conflicts for: {start_time} to {end_time}")
        logger.info(f"Normalized to: {start_time_normalized} to {end_time_normalized}")
        logger.info(f"Searching in range: {day_start_iso} to {day_end_iso}")
        logger.info(f"Date formats valid: start={not day_start_iso.endswith('Z') or '+' not in day_start_iso}, end={not day_end_iso.endswith('Z') or '+' not in day_end_iso}")
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=day_start_iso,
            timeMax=day_end_iso,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        logger.info(f"Found {len(events)} events in the day")
        
        conflicts = []
        for event in events:
            event_start_str = event['start'].get('dateTime', event['start'].get('date'))
            event_end_str = event['end'].get('dateTime', event['end'].get('date'))
            
            # Convertir a datetime para comparar
            if 'T' in event_start_str:  # Es datetime
                event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
            else:  # Es fecha completa (all-day event)
                continue  # Saltamos eventos de día completo
            
            # Verificar si hay solapamiento
            # Solapamiento ocurre si: (nuevo_inicio < evento_fin) AND (nuevo_fin > evento_inicio)
            if new_start < event_end and new_end > event_start:
                conflicts.append({
                    'summary': event.get('summary', 'Evento sin título'),
                    'start': event_start_str,
                    'end': event_end_str,
                    'id': event.get('id')
                })
                logger.info(f"Conflict found: {event.get('summary')} from {event_start_str} to {event_end_str}")
        
        logger.info(f"Total conflicts found: {len(conflicts)}")
        return conflicts
        
    except HttpError as error:
        logger.error(f"Error checking time conflicts: {error}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in check_time_conflicts: {e}")
        return []

def create_event(service, params):
    """Create a new event on the calendar with conflict checking and attendee support"""
    try:
        # Parse parameters - usar zona horaria de Chile por defecto
        now_chile = datetime.now(CHILE_TZ)
        default_start = now_chile + timedelta(hours=1)
        default_end = now_chile + timedelta(hours=2)
        
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
        
        # Debug final state
        logger.info(f"Final force_create value: {force_create}")
        
        # Agregar attendees al evento
        for email in attendee_emails:
            if email:  # Verificar que no esté vacío
                event_data['attendees'].append({'email': email})
        
        # Si no hay attendees, remover la clave para evitar errores
        if not event_data['attendees']:
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
        
        # Crear el evento
        event = service.events().insert(calendarId='primary', body=event_data).execute()
        
        # Preparar respuesta con información adicional
        response = f"✅ Evento creado exitosamente: {event.get('htmlLink')}\n"
        response += f"📅 Título: {event_data['summary']}\n"
        response += f"🕐 Inicio: {event_data['start']['dateTime']}\n"
        response += f"🕑 Fin: {event_data['end']['dateTime']}\n"
        
        if attendee_emails:
            response += f"👥 Invitados: {', '.join(attendee_emails)}\n"
        
        # Si había conflictos pero se forzó la creación
        if conflicts and force_create:
            response += f"⚠️ Nota: Se creó el evento a pesar de tener {len(conflicts)} conflicto(s) de horario\n"
        
        return response
        
    except HttpError as error:
        return f"Error creating event: {error}"

def get_event(service, params):
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

def update_event(service, params):
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

def delete_event(service, params):
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

def check_availability(service, params):
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
        
        # Si no se proporciona hora de fin, asumir 1 hora
        if not end_time:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = start_dt + timedelta(hours=1)
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