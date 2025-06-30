import logging
from app.resources.constants import APIS_COLLECTION
from app.controler.chat.adapters.api_integration import create_api_function

from app.controler.chat.store.persistence import Persist
from app.controler.chat.store.supabase_client import SupabaseClient


def create_api_tools(project_id, unique_id):
    """Generate the API functions code to be executed."""
    logging.info(f"{unique_id} Creating API tools...")

    # Use Supabase client to get APIs with better error handling
    data = []
    try:
        supabase = SupabaseClient()
        data = supabase.get_apis_by_project_id(project_id)
        logging.info(f"{unique_id} APIs found from Supabase: {len(data)}")
        
        # Validar que los datos no estén vacíos o corruptos
        if not data:
            logging.warning(f"{unique_id} No APIs found in Supabase, trying fallback...")
            raise ValueError("No APIs found in Supabase")
            
    except Exception as e:
        logging.error(f"{unique_id} Error getting APIs from Supabase: {str(e)}")
        logging.info(f"{unique_id} Attempting fallback to persistence method...")
        
        # Fallback to persistence method
        try:
            persist = Persist()
            data = list(persist.find(APIS_COLLECTION, {"project_id": project_id}))
            logging.info(f"{unique_id} APIs from fallback: {len(data)}")
        except Exception as fallback_error:
            logging.error(f"{unique_id} Fallback also failed: {str(fallback_error)}")
            return []

    # Crear funciones API con validación adicional
    api_functions = []
    for api_setting in data:
        try:
            if not api_setting:
                logging.warning(f"{unique_id} Skipping empty API setting")
                continue
                
            # Validar campos requeridos
            required_fields = ['api_name', 'api_endpoint', 'api_request_type']
            missing_fields = [field for field in required_fields if not api_setting.get(field)]
            
            if missing_fields:
                logging.error(f"{unique_id} API setting missing required fields: {missing_fields}")
                continue
                
            api_function = create_api_function(api_setting)
            api_functions.append(api_function)
            logging.info(f"{unique_id} Successfully created API function: {api_setting.get('api_name')}")
            
        except Exception as e:
            logging.error(f"{unique_id} Error creating API function for {api_setting.get('api_name', 'unknown')}: {str(e)}")
            continue

    logging.info(f"{unique_id} API functions created successfully: {len(api_functions)}")
    
    # Log adicional para debugging
    if len(data) != len(api_functions):
        logging.warning(f"{unique_id} Mismatch: {len(data)} API settings but {len(api_functions)} functions created")

    return api_functions
