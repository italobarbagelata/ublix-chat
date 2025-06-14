from langchain.tools import tool

from app.controler.chat.core.tools.api_tool import create_api_tools
from app.controler.chat.core.tools.retriever_tool import document_retriever
from app.controler.chat.core.tools.products_fallback_tool import search_products_unified
from app.controler.chat.core.tools.openai_vector_tool import openai_vector_search
from app.controler.chat.core.tools.chile_holidays_tool import check_chile_holiday_tool, next_chile_holidays_tool
from app.controler.chat.core.tools.datetime_tool import current_datetime_tool, week_info_tool
from app.controler.chat.core.tools.simple_vector_search import buscar_en_vector_openai
from app.controler.chat.core.tools.tienda_tool import buscar_productos_tienda, consultar_info_tienda, gestionar_carrito
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List
from app.controler.chat.store.persistence import Project
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

async def agent_tools(project_id: str, user_id: str, name: str, number_phone_agent: str, unique_id: str, project: Project) -> List:
    """ This function returns the tools that the agent will use to interact with the user"""
    tools = []
    
    # Agregar logging para debugear el project_id
    logging.info(f"agent_tools llamado con project_id: {project_id}, user_id: {user_id}")
    
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
        "datetime": lambda *args: [current_datetime_tool],
        "openai_product_search": lambda *args: [buscar_en_vector_openai],
        "tienda": lambda *args: [buscar_productos_tienda, consultar_info_tienda, gestionar_carrito]
    }
    
    # Preparar tareas para paralelización
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=5)
    tasks = []
    tool_names_to_load = []
    
    # Cargar solo las herramientas habilitadas de forma paralela
    for tool_name in project.enabled_tools:
        if tool_name in tool_mapping:
            tool_names_to_load.append(tool_name)
            tool_func = tool_mapping[tool_name]
            if tool_name == "api":
                tasks.append(loop.run_in_executor(executor, tool_func, project_id, unique_id))
            else:
                tasks.append(loop.run_in_executor(executor, tool_func))
    
    # Ejecutar todas las tareas en paralelo
    if tasks:
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Procesar resultados
            for i, result in enumerate(results):
                tool_name = tool_names_to_load[i]
                if isinstance(result, Exception):
                    logging.error(f"Error loading tool {tool_name}: {str(result)}")
                    continue
                
                if tool_name == "api":
                    logging.info(f"Cargando herramientas API para project_id: {project_id}")
                    logging.info(f"API tools devueltas: {type(result)}, cantidad: {len(result) if result else 0}")
                    if result:
                        tools.extend([tool(api_tool) for api_tool in result])
                else:
                    if result:
                        tools.extend(result)
        except Exception as e:
            logging.error(f"Error in parallel tool loading: {str(e)}")

    # Siempre agregamos la herramienta datetime al final
    tools.append(current_datetime_tool)
    
    logging.info(f"Se inicializaron las tools: {[tool.name for tool in tools]}")
    return tools