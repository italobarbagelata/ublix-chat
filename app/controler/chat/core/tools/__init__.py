from langchain.tools import tool

from app.controler.chat.core.tools.api_tool import create_api_tools
#from app.controler.chat.core.tools.mongo_tool import mongo_db_tool
from app.controler.chat.core.tools.retriever_tool import retriever
from app.controler.chat.core.tools.products_tool import search_products
import logging

# Import calendar tool safely
try:
    from app.controler.chat.core.tools.calendar_tool import google_calendar_tool
    CALENDAR_TOOL_AVAILABLE = True
except ImportError:
    logging.warning("Google Calendar tool not available. Missing dependencies. Run 'pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib'")
    CALENDAR_TOOL_AVAILABLE = False

# Import internal calendar tool
# Esta herramienta permite interactuar con el calendario interno de la aplicación
# Soporta consultas en lenguaje natural como "Agenda una reunión el lunes a las 3 PM"
# así como comandos estructurados para operaciones más avanzadas
#from app.controler.chat.core.tools.internal_calendar_tool import internal_calendar_tool

def agent_tools(project_id, user_id, name, number_phone_agent, project=None):
    """ This function returns the tools that the agent will use to interact with the user"""
    tools = []
    
    # Si no se proporciona el proyecto, cargarlo
    if project is None:
        from app.controler.chat.store.persistence import Persist
        project = Persist().find_project(project_id)
    
    # Verificar si el proyecto tiene herramientas habilitadas
    if not hasattr(project, 'enabled_tools') or not project.enabled_tools:
        logging.warning(f"No hay herramientas habilitadas para el proyecto {project_id}")
        return tools
    
    # Mapeo de nombres de herramientas a funciones
    tool_mapping = {
        "api": create_api_tools,
        "retriever": lambda *args: [retriever],
        "products_search": lambda *args: [search_products],
        "calendar": lambda *args: [google_calendar_tool] if CALENDAR_TOOL_AVAILABLE else []
    }
    
    # Cargar solo las herramientas habilitadas
    for tool_name in project.enabled_tools:
        if tool_name in tool_mapping:
            try:
                tool_func = tool_mapping[tool_name]
                if tool_name == "api":
                    tools.extend([tool(api_tool) for api_tool in tool_func(project_id)])
                else:
                    tools.extend(tool_func(project_id, user_id, name, number_phone_agent))
            except Exception as e:
                logging.error(f"Error loading tool {tool_name}: {str(e)}")
                continue

    logging.info(f"Se inicializaron las tools: {[tool.name for tool in tools]}")
    return tools