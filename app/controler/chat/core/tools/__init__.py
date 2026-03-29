from langchain_core.tools import tool

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
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from app.controler.chat.store.persistence import Project

# =============================================================================
# CACHE DE HERRAMIENTAS
# =============================================================================
# Caché thread-safe para herramientas por proyecto.
# Evita recrear herramientas en cada llamada al agente.
# TTL de 5 minutos para refrescar configuración de herramientas.
# =============================================================================

_tools_cache: Dict[str, Tuple[List, datetime]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = timedelta(minutes=5)


def _get_cache_key(project_id: str) -> str:
    """Genera la clave de caché para un proyecto."""
    return f"tools_{project_id}"


def get_cached_tools(project_id: str) -> Optional[List]:
    """
    Obtiene herramientas del caché si están disponibles y no expiraron.

    Args:
        project_id: ID del proyecto

    Returns:
        Lista de herramientas o None si no hay caché válido
    """
    cache_key = _get_cache_key(project_id)

    with _cache_lock:
        if cache_key in _tools_cache:
            tools, cached_at = _tools_cache[cache_key]
            if datetime.now() - cached_at < _CACHE_TTL:
                logging.debug(f"Herramientas obtenidas del caché para proyecto {project_id}")
                return tools
            else:
                # Caché expirado, eliminar
                del _tools_cache[cache_key]
                logging.debug(f"Caché de herramientas expirado para proyecto {project_id}")

    return None


def set_cached_tools(project_id: str, tools: List) -> None:
    """
    Guarda herramientas en el caché.

    Args:
        project_id: ID del proyecto
        tools: Lista de herramientas a cachear
    """
    cache_key = _get_cache_key(project_id)

    with _cache_lock:
        _tools_cache[cache_key] = (tools, datetime.now())
        logging.debug(f"Herramientas cacheadas para proyecto {project_id}")


def invalidate_tools_cache(project_id: str = None) -> None:
    """
    Invalida el caché de herramientas.

    Args:
        project_id: Si se especifica, solo invalida ese proyecto.
                   Si es None, invalida todo el caché.
    """
    with _cache_lock:
        if project_id:
            cache_key = _get_cache_key(project_id)
            if cache_key in _tools_cache:
                del _tools_cache[cache_key]
                logging.info(f"Caché invalidado para proyecto {project_id}")
        else:
            _tools_cache.clear()
            logging.info("Caché de herramientas completamente invalidado")


async def agent_tools(project_id: str, user_id: str, name: str, number_phone_agent: str, unique_id: str, project: Project, use_cache: bool = True) -> List:
    """
    Función mejorada que retorna las herramientas para el agente.
    Usa caché por proyecto para evitar recrear herramientas.

    Args:
        project_id: ID del proyecto
        user_id: ID del usuario
        name: Nombre del usuario
        number_phone_agent: Número de teléfono del agente
        unique_id: ID único de la conversación
        project: Objeto Project con configuración
        use_cache: Si True, usa caché de herramientas (default: True)

    Returns:
        Lista de herramientas configuradas
    """
    # Intentar obtener del caché primero
    if use_cache:
        cached = get_cached_tools(project_id)
        if cached is not None:
            return cached

    logging.debug(f"Creando herramientas para proyecto: {project_id}")
    
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
        
        # Herramienta de búsqueda unificada (SIEMPRE activa, movida a essential_tools)
        # Ya no se carga aquí, se agrega automáticamente al final

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
        unified_search_tool,  # Búsqueda unificada SIEMPRE activa para FAQs, docs y productos
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

    # Guardar en caché para próximas llamadas
    if use_cache:
        set_cached_tools(project_id, tools)

    return tools