import os
import logging
from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("root")

class SupabaseClient:
    """Client for interacting with Supabase database."""
    
    def __init__(self):
        """Initialize Supabase client with environment variables."""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            logger.error("Supabase URL or key not found in environment variables")
            raise ValueError("Supabase URL or key not found in environment variables")
        
        self.client: Client = create_client(supabase_url, supabase_key)
        logger.info("Supabase client initialized")
    
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