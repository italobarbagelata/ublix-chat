from langchain.tools import tool

from app.controler.chat.core.tools.api_tool import create_api_tools
from app.controler.chat.core.tools.unified_search_tool import unified_search_tool
from app.controler.chat.core.tools.datetime_tool import current_datetime_tool, week_info_tool
from app.controler.chat.core.tools.chile_holidays_tool import check_chile_holiday_tool, next_chile_holidays_tool
from app.controler.chat.core.tools.contact_tool import SaveContactTool
from app.controler.chat.core.tools.agenda_tool import AgendaTool

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List
from app.controler.chat.store.persistence import Project


async def agent_tools(project_id: str, user_id: str, name: str, number_phone_agent: str, unique_id: str, project: Project) -> List:
    """Versión simplificada de la función que retorna las tools para el agente"""
    
    logging.info(f"Inicializando tools para project_id: {project_id}, user_id: {user_id}")
    logging.info(f"Herramientas habilitadas: {project.enabled_tools}")
    
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=3)

    # Ejecutar operaciones paralelas solo para herramientas habilitadas
    tasks = []
    
    # Solo cargar API tools si están habilitadas
    if "api" in project.enabled_tools:
        logging.info(f"{unique_id} API tools habilitadas, iniciando carga...")
        tasks.append(loop.run_in_executor(executor, create_api_tools, project_id, unique_id))

    # Esperar los resultados de las tareas paralelas
    results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []
    
    # Construir la lista final de tools
    tools = []
    
    # Agregar API tools si están disponibles
    if results and not isinstance(results[0], Exception):
        api_tools = results[0]
        tools.extend(tool(api_tool) for api_tool in api_tools)
        logging.info(f"{unique_id} API tools agregadas: {len(api_tools)}")
    
    # Agregar herramientas habilitadas según configuración
    if "unified_search" in project.enabled_tools:
        tools.append(unified_search_tool)
        logging.info("Herramienta habilitada: unified_search")
    
    if "agenda_tool" in project.enabled_tools:
        tools.append(AgendaTool(project_id, project, user_id))
        logging.info("Herramienta habilitada: agenda_tool")
    
    # Solo agregar herramientas esenciales siempre disponibles
    tools.extend([
        current_datetime_tool,
        SaveContactTool(project_id, user_id)
    ])

    logging.info(f"Se inicializaron las tools: {[getattr(tool, 'name', getattr(tool, '__name__', str(tool))) for tool in tools]}")
    logging.info(f"Total de tools creadas: {len(tools)}")
    
    return tools