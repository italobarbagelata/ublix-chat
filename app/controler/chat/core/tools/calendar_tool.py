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

logger = logging.getLogger(__name__)

@tool(parse_docstring=False)
def google_calendar_tool(query: str, state: Annotated[dict, InjectedState]) -> str:
    """This tool interacts with Google Calendar to manage events and schedules.
    
    Args:
        query: A structured query with format: 
               [ACTION]|[PARAMETERS]
               where ACTION can be: list_events, search_events, create_event, get_event, update_event, or delete_event
               and PARAMETERS depend on the action:
               - list_events|days=7 (lists events for next 7 days)
               - search_events|title=Meeting|date=2023-06-15 (searches for events with matching title and/or date)
               - create_event|title=Meeting with Client|start=2023-06-15T15:00:00|end=2023-06-15T16:00:00|description=Discuss project status
               - get_event|event_id=abc123
               - update_event|event_id=abc123|title=New Title|description=Updated description
               - delete_event|event_id=abc123
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
        else:
            return f"Unknown action: {action}. Supported actions are list_events, search_events, create_event, get_event, update_event, and delete_event."
            
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

def create_event(service, params):
    """Create a new event on the calendar"""
    try:
        # Parse parameters
        event_data = {
            'summary': 'New Event',
            'description': '',
            'start': {
                'dateTime': (datetime.utcnow() + timedelta(hours=1)).isoformat() + 'Z',
            },
            'end': {
                'dateTime': (datetime.utcnow() + timedelta(hours=2)).isoformat() + 'Z',
            }
        }
        
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'title' or key == 'summary':
                    event_data['summary'] = value
                elif key == 'description':
                    event_data['description'] = value
                elif key == 'start':
                    event_data['start']['dateTime'] = value
                elif key == 'end':
                    event_data['end']['dateTime'] = value
        
        # Create the event
        event = service.events().insert(calendarId='primary', body=event_data).execute()
        
        return f"Event created: {event.get('htmlLink')}"
        
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