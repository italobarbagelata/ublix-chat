from langchain.tools import tool

from app.controler.chat.core.tools.api_tool import create_api_tools
#from app.controler.chat.core.tools.mongo_tool import mongo_db_tool
from app.controler.chat.core.tools.retriever_tool import document_retriever
from app.controler.chat.core.tools.products_fallback_tool import search_products_unified
from app.controler.chat.core.tools.openai_vector_tool import openai_vector_search
from app.controler.chat.core.tools.chile_holidays_tool import check_chile_holiday_tool, next_chile_holidays_tool
from app.controler.chat.core.tools.datetime_tool import current_datetime_tool, week_info_tool
from app.controler.chat.core.tools.simple_vector_search import buscar_en_vector_openai
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
        "products_search": lambda *args: [search_products_unified],
        "calendar": lambda *args: [google_calendar_tool] if CALENDAR_TOOL_AVAILABLE else [],
        "openai_vector": lambda *args: [openai_vector_search],
        "retriever": lambda *args: [document_retriever],
        "chile_holidays": lambda *args: [check_chile_holiday_tool, next_chile_holidays_tool],
        "datetime": lambda *args: [current_datetime_tool, week_info_tool],
        "openai_product_search": lambda *args: [buscar_en_vector_openai]
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