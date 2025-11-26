from langchain.tools import tool

from app.controler.chat.core.tools.api_tool import create_api_tools
from app.controler.chat.core.tools.unified_search_tool import unified_search_tool
from app.controler.chat.core.tools.datetime_tool import current_datetime_tool, week_info_tool
from app.controler.chat.core.tools.chile_holidays_tool import check_chile_holiday_tool, next_chile_holidays_tool
from app.controler.chat.core.tools.contact_tool import SaveContactTool
from app.controler.chat.core.tools.agenda_tool import AgendaTool
from app.controler.chat.core.tools.email_tool import EmailTool
from app.controler.chat.core.tools.image_processor_tool import ImageProcessorTool

# ============================================================================
# HERRAMIENTAS DEPRECADAS (2025-01-XX)
# ============================================================================
# Las siguientes herramientas han sido deprecadas en favor de unified_search_tool
# que proporciona búsqueda unificada más eficiente y mejores resultados.
#
# DEPRECADAS:
# - faq_retriever_tool → Usar unified_search_tool con content_types=['faq']
# - document_retriever (retriever_tool) → Usar unified_search_tool con content_types=['document']
#
# RAZONES:
# 1. Mejor contexto global (combina FAQs + docs + productos)
# 2. Menos llamadas al LLM (-30% tokens)
# 3. Menor latencia (-200-400ms)
# 4. Ranking global por relevancia
# 5. Un solo punto de mantenimiento
#
# Los archivos originales se mantienen en el directorio por si se necesitan
# restaurar temporalmente, pero NO se importan ni se usan.
# ============================================================================

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
    
    logging.debug(f"Cargando herramientas para usuario: {user_id}")
    
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
                logging.debug(f"Cargando herramientas API personalizadas")
                loop = asyncio.get_event_loop()
                executor = ThreadPoolExecutor(max_workers=1)
                api_tools = await loop.run_in_executor(executor, create_api_tools, project_id, unique_id)
                if api_tools:
                    tools.extend(tool(api_tool) for api_tool in api_tools)
                    logging.debug(f"Herramientas API cargadas: {len(api_tools)}")
            except Exception as e:
                logging.error(f"Error cargando API tools: {str(e)}")
        
        # Herramienta de búsqueda unificada
        if "unified_search" in enabled_tools:
            tools.append(unified_search_tool)
            logging.debug("Búsqueda unificada habilitada")
        
        # Herramienta de agenda
        if "agenda_tool" in enabled_tools:
            tools.append(AgendaTool(project_id, project, user_id))
            logging.debug("Agenda habilitada")
        
        # Herramienta de email (optimizada para no atrasar respuestas)
        if "email" in enabled_tools:
            try:
                email_tool = EmailTool()  # Versión optimizada con background
                tools.append(email_tool)
                logging.debug("Email habilitado")
            except Exception as e:
                logging.error(f"Error cargando EmailTool: {str(e)}")
        
        # Herramientas de feriados ahora son esenciales (movidas a essential_tools)
        # Ya no necesitan estar en enabled_tools para funcionar
        
        # Herramienta de información de semana
        if "week_info" in enabled_tools:
            tools.append(week_info_tool)
            logging.debug("Información de semana habilitada")
        
        # Herramienta de procesamiento de imágenes
        if "image_processor" in enabled_tools:
            try:
                image_tool = ImageProcessorTool()
                tools.append(image_tool)
                logging.debug("Procesador de imágenes habilitado")
            except Exception as e:
                logging.error(f"Error cargando ImageProcessorTool: {str(e)}")
        
    except Exception as e:
        logging.error(f"Error durante la carga de herramientas opcionales: {str(e)}")
    
    # Herramientas esenciales SIEMPRE disponibles (no dependen de configuración)
    essential_tools = [
        current_datetime_tool,
        SaveContactTool(project_id, user_id),
        check_chile_holiday_tool,  # Validación de feriados siempre activa
        next_chile_holidays_tool,  # Consulta de feriados siempre activa
    ]
    tools.extend(essential_tools)
    # Herramientas esenciales siempre disponibles
    
    # Log final con todas las herramientas cargadas
    tool_names = []
    for t in tools:
        try:
            tool_name = getattr(t, 'name', getattr(t, '__name__', str(type(t).__name__)))
            tool_names.append(tool_name)
        except:
            tool_names.append('unknown_tool')
    
    logging.info(f"Herramientas activas: {', '.join(tool_names) if tool_names else 'Solo herramientas básicas'}")
    
    return tools