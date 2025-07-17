from langchain.tools import tool

from app.controler.chat.core.tools.api_tool import create_api_tools
from app.controler.chat.core.tools.mongo_tool import mongo_db_tool
from app.controler.chat.core.tools.retriever_tool import document_retriever
from app.controler.chat.core.tools.faq_retriever_tool import faq_retriever
from app.controler.chat.core.tools.unified_search_tool import unified_search_tool
from app.controler.chat.core.tools.openai_vector_tool import openai_vector_search
from app.controler.chat.core.tools.chile_holidays_tool import check_chile_holiday_tool, next_chile_holidays_tool
from app.controler.chat.core.tools.datetime_tool import current_datetime_tool, week_info_tool
from app.controler.chat.core.tools.simple_vector_search import buscar_en_vector_openai
from app.controler.chat.core.tools.tienda_tool import buscar_productos_tienda, consultar_info_tienda, gestionar_carrito
from app.controler.chat.core.tools.contact_tool import SaveContactTool
from app.controler.chat.core.tools.email_tool import EmailTool
from app.controler.chat.core.tools.image_processor_tool import ImageProcessorTool
from app.controler.chat.core.tools.calendar_tool import google_calendar_tool
from app.controler.chat.core.tools.agenda_tool import AgendaTool
from app.controler.chat.core.tools.mcp_tool_factory import create_mcp_tools_for_project


import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List
from app.controler.chat.store.persistence import Project
from app.controler.chat.core.tools_cache import cached_tools

@cached_tools(ttl_hours=24)
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
    
    # Mejorar el manejo de resultados de API tools
    api_tools = []
    if results:
        if isinstance(results[0], Exception):
            logging.error(f"{unique_id} Error cargando API tools: {results[0]}")
            logging.error(f"{unique_id} Tipo de error: {type(results[0])}")
            # Intentar cargar las APIs de forma síncrona como último recurso
            try:
                logging.info(f"{unique_id} Intentando carga síncrona de APIs como último recurso...")
                api_tools = create_api_tools(project_id, unique_id)
                logging.info(f"{unique_id} Carga síncrona exitosa: {len(api_tools)} API tools")
            except Exception as sync_error:
                logging.error(f"{unique_id} Error en carga síncrona también: {sync_error}")
                api_tools = []
        else:
            api_tools = results[0] if results[0] else []
            logging.info(f"{unique_id} API tools cargadas exitosamente: {len(api_tools)}")

    # Construir la lista final de tools
    tools = []
    
    # Agregar API tools si están disponibles y habilitadas (estas ya vienen como herramientas listas)
    if "api" in project.enabled_tools and api_tools:
        for api_tool in api_tools:
            try:
                tool_name = getattr(api_tool, 'name', getattr(api_tool, '__name__', 'API_tool'))
                logging.info(f"{unique_id} Agregando API tool: {tool_name}")
                tools.append(api_tool)  # No envolver con tool() si ya son herramientas
            except Exception as e:
                logging.error(f"{unique_id} Error agregando API tool: {str(e)}")
                continue
    
    # Mapeo de herramientas opcionales (sin instanciar aquí)
    optional_tools = {
        "retriever": [document_retriever],
        "faq_retriever": [faq_retriever],
        "unified_search": [unified_search_tool],
        "openai_vector": [openai_vector_search],
        "calendar": [google_calendar_tool],
        "tienda": [buscar_productos_tienda, consultar_info_tienda, gestionar_carrito],
        "mongo_db": [mongo_db_tool],
        "buscar_en_vector_openai": [buscar_en_vector_openai]
    }
    
    # Agregar herramientas opcionales basadas en enabled_tools
    for tool_name, tool_list in optional_tools.items():
        if tool_name in project.enabled_tools:
            tools.extend(tool_list)
            logging.info(f"Herramienta habilitada: {tool_name}")
    
    # Herramientas que siempre están disponibles (independientes de enabled_tools)
    always_available_tools = [
        current_datetime_tool,
        week_info_tool,
        check_chile_holiday_tool,
        next_chile_holidays_tool,
        SaveContactTool(project_id, user_id),  # Esta necesita instanciación
    ]
    
    # Agregar herramientas condicionales que requieren instanciación
    if "image_processor" in project.enabled_tools:
        always_available_tools.append(ImageProcessorTool())
        logging.info("Herramienta habilitada: image_processor")
    
    if "email" in project.enabled_tools:
        always_available_tools.append(EmailTool())
        logging.info("Herramienta habilitada: email")
    
    if "agenda_tool" in project.enabled_tools:
        # Usar la herramienta de agenda con servicios especializados
        always_available_tools.append(AgendaTool(project_id, project, user_id))
        logging.info("Herramienta habilitada: agenda_tool")

    
    tools.extend(always_available_tools)
    
    # Agregar herramientas MCP si están habilitadas
    mcp_tools_enabled = [tool for tool in project.enabled_tools if tool.startswith("mcp_")]
    if mcp_tools_enabled:
        try:
            # Crear herramientas MCP de forma asíncrona
            mcp_tools = await create_mcp_tools_for_project(project_id, mcp_tools_enabled)
            tools.extend(mcp_tools)
            logging.info(f"Herramientas MCP habilitadas: {[tool.name for tool in mcp_tools]}")
        except Exception as e:
            logging.error(f"Error cargando herramientas MCP: {str(e)}")
            # Continuar sin herramientas MCP si hay error

    logging.info(f"Se inicializaron las tools: {[getattr(tool, 'name', str(tool)) for tool in tools]}")
    logging.info(f"Total de tools creadas: {len(tools)}")
    
    return tools