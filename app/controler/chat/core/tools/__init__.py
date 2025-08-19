from langchain.tools import tool

from app.controler.chat.core.tools.api_tool import create_api_tools
from app.controler.chat.core.tools.unified_search_tool import unified_search_tool
from app.controler.chat.core.tools.datetime_tool import current_datetime_tool, week_info_tool
from app.controler.chat.core.tools.chile_holidays_tool import check_chile_holiday_tool, next_chile_holidays_tool
from app.controler.chat.core.tools.contact_tool import SaveContactTool
from app.controler.chat.core.tools.agenda_tool import AgendaTool
from app.controler.chat.core.tools.email_tool import EmailTool
from app.controler.chat.core.tools.image_processor_tool import ImageProcessorTool

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List
from app.controler.chat.store.persistence import Project


async def agent_tools(project_id: str, user_id: str, name: str, number_phone_agent: str, unique_id: str, project: Project) -> List:
    """
    Función mejorada que retorna las herramientas para el agente.
    Carga todas las herramientas habilitadas sin usar caché.
    """
    
    logging.info(f"Inicializando tools para project_id: {project_id}, user_id: {user_id}")
    logging.info(f"Herramientas habilitadas: {project.enabled_tools}")
    
    # Lista para almacenar todas las herramientas
    tools = []
    
    # Verificar si project y enabled_tools existen
    if not project or not hasattr(project, 'enabled_tools'):
        logging.warning(f"Proyecto sin configuración de herramientas, usando herramientas por defecto")
        enabled_tools = []
    else:
        enabled_tools = project.enabled_tools or []
    
    # Cargar herramientas según configuración
    try:
        # API tools (carga asíncrona si está habilitada)
        if "api" in enabled_tools:
            try:
                logging.info(f"{unique_id} Cargando API tools...")
                loop = asyncio.get_event_loop()
                executor = ThreadPoolExecutor(max_workers=1)
                api_tools = await loop.run_in_executor(executor, create_api_tools, project_id, unique_id)
                if api_tools:
                    tools.extend(tool(api_tool) for api_tool in api_tools)
                    logging.info(f"{unique_id} API tools agregadas: {len(api_tools)}")
            except Exception as e:
                logging.error(f"Error cargando API tools: {str(e)}")
        
        # Herramienta de búsqueda unificada
        if "unified_search" in enabled_tools:
            tools.append(unified_search_tool)
            logging.info("Herramienta habilitada: unified_search")
        
        # Herramienta de agenda
        if "agenda_tool" in enabled_tools:
            tools.append(AgendaTool(project_id, project, user_id))
            logging.info("Herramienta habilitada: agenda_tool")
        
        # Herramienta de email (optimizada para no atrasar respuestas)
        if "email" in enabled_tools:
            try:
                email_tool = EmailTool()  # Versión optimizada con background
                tools.append(email_tool)
                logging.info("Herramienta habilitada: email (modo rápido)")
            except Exception as e:
                logging.error(f"Error cargando EmailTool: {str(e)}")
        
        # Herramientas de calendario/vacaciones
        if "holidays" in enabled_tools:
            tools.extend([check_chile_holiday_tool, next_chile_holidays_tool])
            logging.info("Herramientas de vacaciones chilenas habilitadas")
        
        # Herramienta de información de semana
        if "week_info" in enabled_tools:
            tools.append(week_info_tool)
            logging.info("Herramienta week_info habilitada")
        
        # Herramienta de procesamiento de imágenes
        if "image_processor" in enabled_tools:
            try:
                image_tool = ImageProcessorTool()
                tools.append(image_tool)
                logging.info("Herramienta image_processor habilitada")
            except Exception as e:
                logging.error(f"Error cargando ImageProcessorTool: {str(e)}")
        
    except Exception as e:
        logging.error(f"Error durante la carga de herramientas opcionales: {str(e)}")
    
    # Herramientas esenciales SIEMPRE disponibles (no dependen de configuración)
    essential_tools = [
        current_datetime_tool,
        SaveContactTool(project_id, user_id),
    ]
    tools.extend(essential_tools)
    logging.info(f"Herramientas esenciales agregadas: {len(essential_tools)}")
    
    # Log final con todas las herramientas cargadas
    tool_names = []
    for t in tools:
        try:
            tool_name = getattr(t, 'name', getattr(t, '__name__', str(type(t).__name__)))
            tool_names.append(tool_name)
        except:
            tool_names.append('unknown_tool')
    
    logging.info(f"✅ Tools inicializadas: {tool_names}")
    logging.info(f"✅ Total de tools creadas: {len(tools)}")
    
    return tools