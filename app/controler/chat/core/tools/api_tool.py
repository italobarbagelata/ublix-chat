import logging
from app.resources.constants import APIS_COLLECTION
from app.controler.chat.adapters.api_integration import create_api_function
import pickle
import logging

from app.controler.chat.store.persistence import Persist
from app.controler.chat.store.supabase_client import SupabaseClient


def create_api_tools(project_id):
    """Generate the API functions code to be executed, with Redis cache."""
    logger = logging.getLogger(f"root")
    cache_key = f"api_functions:{project_id}"

    logger.info("[API_TOOLS] Iniciando creación de herramientas API")
    
    # Use Supabase client to get APIs
    try:
        supabase = SupabaseClient()
        data = supabase.get_apis_by_project_id(project_id)
        logger.info(f"[API_TOOLS] Se recuperaron {len(data)} APIs de Supabase para el proyecto {project_id}")
    except Exception as e:
        logger.error(f"[API_TOOLS] Error al recuperar APIs de Supabase: {str(e)}")
        # Fallback to previous persistence method
        logger.info("[API_TOOLS] Cambiando al método de persistencia anterior")
        persist = Persist()
        data = list(persist.find(APIS_COLLECTION, {"project_id": project_id}))
        logger.info(f"[API_TOOLS] Se recuperaron {len(data)} APIs del método de persistencia anterior")
    
    # Debug: verificar estructura de datos
    logger.info(f"[API_TOOLS] Estructura de data: {type(data)}")
    logger.info(f"[API_TOOLS] Primer elemento (si existe): {data[0] if data else 'Lista vacía'}")
    
    api_functions = []
    for i, api_setting in enumerate(data):
        try:
            logger.info(f"[API_TOOLS] Procesando API {i+1}: {type(api_setting)}")
            api_function = create_api_function(api_setting)
            api_functions.append(api_function)
            logger.info(f"[API_TOOLS] API {i+1} procesada exitosamente")
        except Exception as e:
            logger.error(f"[API_TOOLS] Error procesando API {i+1}: {str(e)}")
            logger.error(f"[API_TOOLS] Datos de la API problemática: {api_setting}")
            continue
    
    logger.info(f"[API_TOOLS] Total de funciones API generadas: {len(api_functions)}")
    logger.debug(f"[API_TOOLS] Detalles de las funciones API: {api_functions}")
    
    return api_functions
