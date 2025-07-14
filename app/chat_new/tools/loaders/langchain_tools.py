"""
Cargador de Herramientas LangChain para el Sistema Mejorado

Este módulo se encarga de importar y adaptar todas las herramientas 
LangChain del sistema original para su uso en el sistema mejorado.
"""

import logging
import asyncio
from typing import List, Any, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

from ...core.state import EnhancedState
from ..registry import get_tool_registry, ToolMetadata, ToolType, ToolStatus
from ..adapters.langchain import create_langchain_adapter

# Importar herramientas del sistema original
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
from app.controler.chat.core.tools.calendar_tool import google_calendar_tool, test_calendar_connectivity
from app.controler.chat.core.tools.agenda_tool_refactored import AgendaToolRefactored


class LangChainToolsLoader:
    """
    Cargador de herramientas LangChain para el sistema mejorado.
    
    Se encarga de:
    - Cargar herramientas del sistema original
    - Adaptarlas al nuevo sistema
    - Registrarlas en el registro de herramientas
    - Manejar dependencias y errores
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.loaded_tools = {}
        self.failed_tools = {}
    
    async def load_all_tools(
        self, 
        project_id: str, 
        user_id: str, 
        name: str, 
        number_phone_agent: str, 
        unique_id: str, 
        project: Any,
        enabled_tools: List[str]
    ) -> Dict[str, Any]:
        """
        Carga todas las herramientas LangChain disponibles.
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario
            name: Nombre del usuario
            number_phone_agent: Número de teléfono del agente
            unique_id: ID único de la sesión
            project: Objeto del proyecto
            enabled_tools: Lista de herramientas habilitadas
            
        Returns:
            Dict con estadísticas de carga
        """
        
        self.logger.info(f"{unique_id} Iniciando carga de herramientas LangChain")
        self.logger.info(f"{unique_id} Herramientas habilitadas: {enabled_tools}")
        
        registry = get_tool_registry()
        
        # Cargar herramientas siempre disponibles
        await self._load_always_available_tools()
        
        # Cargar herramientas condicionales según enabled_tools
        await self._load_conditional_tools(
            project_id, user_id, name, number_phone_agent, 
            unique_id, project, enabled_tools
        )
        
        # Cargar herramientas API si están habilitadas
        if "api" in enabled_tools:
            await self._load_api_tools(project_id, unique_id)
        
        # Estadísticas de carga
        stats = {
            "loaded_count": len(self.loaded_tools),
            "failed_count": len(self.failed_tools),
            "loaded_tools": list(self.loaded_tools.keys()),
            "failed_tools": list(self.failed_tools.keys()),
            "total_requested": len(enabled_tools)
        }
        
        self.logger.info(
            f"{unique_id} Carga completada: {stats['loaded_count']} exitosas, "
            f"{stats['failed_count']} fallidas"
        )
        
        return stats
    
    async def _load_always_available_tools(self):
        """Carga herramientas que siempre están disponibles"""
        
        always_available = [
            current_datetime_tool,
            week_info_tool,
            check_chile_holiday_tool,
            next_chile_holidays_tool,
            test_calendar_connectivity,
        ]
        
        for tool in always_available:
            await self._register_tool(tool, create_tool_metadata(tool))
    
    async def _load_conditional_tools(
        self, 
        project_id: str, 
        user_id: str, 
        name: str, 
        number_phone_agent: str, 
        unique_id: str, 
        project: Any,
        enabled_tools: List[str]
    ):
        """Carga herramientas condicionales según enabled_tools"""
        
        # Mapeo de herramientas opcionales
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
        
        # Cargar herramientas opcionales
        for tool_name, tool_list in optional_tools.items():
            if tool_name in enabled_tools:
                for tool in tool_list:
                    await self._register_tool(tool, create_tool_metadata(tool))
                    self.logger.info(f"Herramienta habilitada: {tool_name}")
        
        # Herramientas que requieren instanciación
        if "image_processor" in enabled_tools:
            tool = ImageProcessorTool()
            await self._register_tool(tool, create_tool_metadata(tool))
            self.logger.info("Herramienta habilitada: image_processor")
        
        if "email" in enabled_tools:
            tool = EmailTool()
            await self._register_tool(tool, create_tool_metadata(tool))
            self.logger.info("Herramienta habilitada: email")
        
        if "agenda_tool" in enabled_tools:
            tool = AgendaToolRefactored(project_id, project, user_id)
            await self._register_tool(tool, create_tool_metadata(tool))
            self.logger.info("Herramienta habilitada: agenda_tool")
        
        # SaveContactTool siempre se incluye pero requiere parámetros
        tool = SaveContactTool(project_id, user_id)
        await self._register_tool(tool, create_tool_metadata(tool))
    
    async def _load_api_tools(self, project_id: str, unique_id: str):
        """Carga herramientas API de forma asíncrona"""
        
        try:
            self.logger.info(f"{unique_id} Cargando herramientas API...")
            
            # Intentar carga asíncrona primero
            loop = asyncio.get_event_loop()
            executor = ThreadPoolExecutor(max_workers=3)
            
            try:
                api_tools = await loop.run_in_executor(
                    executor, create_api_tools, project_id, unique_id
                )
                
                if api_tools:
                    for tool in api_tools:
                        await self._register_tool(tool, create_tool_metadata(tool))
                    
                    self.logger.info(f"{unique_id} API tools cargadas: {len(api_tools)}")
                else:
                    self.logger.warning(f"{unique_id} No se obtuvieron API tools")
                    
            except Exception as async_error:
                self.logger.error(f"{unique_id} Error carga asíncrona API: {async_error}")
                
                # Fallback a carga síncrona
                try:
                    self.logger.info(f"{unique_id} Intentando carga síncrona de APIs...")
                    api_tools = create_api_tools(project_id, unique_id)
                    
                    if api_tools:
                        for tool in api_tools:
                            await self._register_tool(tool, create_tool_metadata(tool))
                        
                        self.logger.info(f"{unique_id} API tools síncronas cargadas: {len(api_tools)}")
                    
                except Exception as sync_error:
                    self.logger.error(f"{unique_id} Error carga síncrona también: {sync_error}")
                    self.failed_tools["api_tools"] = str(sync_error)
                    
        except Exception as e:
            self.logger.error(f"{unique_id} Error general cargando API tools: {e}")
            self.failed_tools["api_tools"] = str(e)
    
    async def _register_tool(self, tool: Any, metadata: ToolMetadata) -> bool:
        """Registra una herramienta individual en el sistema mejorado"""
        
        try:
            registry = get_tool_registry()
            
            # Verificar si es una herramienta LangChain y configurar adaptador
            if hasattr(tool, 'name') and hasattr(tool, 'description'):
                # Es una herramienta LangChain, actualizar metadata
                metadata.tool_type = ToolType.LANGCHAIN
                
                # CRÍTICO: Registrar el adaptador LangChain en el registry
                langchain_adapter = create_langchain_adapter()
                registry.register_adapter(ToolType.LANGCHAIN, langchain_adapter)
                self.logger.info(f"✅ Registrado adaptador LangChain para {metadata.name}")
            
            # Verificar si la herramienta ya existe
            tool_name = metadata.name
            if tool_name in registry.tools:
                # La herramienta ya está registrada, asegurar que esté activa
                registry.tools[tool_name].metadata.status = ToolStatus.ACTIVE
                self.loaded_tools[tool_name] = tool
                self.logger.debug(f"Herramienta ya registrada (reutilizando y activando): {tool_name}")
                return True
            
            success = registry.register_tool(tool, metadata)
            
            if success:
                # Marcar herramienta como activa después del registro exitoso
                if tool_name in registry.tools:
                    registry.tools[tool_name].metadata.status = ToolStatus.ACTIVE
                
                self.loaded_tools[tool_name] = tool
                self.logger.debug(f"Herramienta registrada y activada: {tool_name}")
                return True
            else:
                self.failed_tools[tool_name] = "Registration failed"
                self.logger.error(f"Falló registro de herramienta: {tool_name}")
                return False
                
        except Exception as e:
            tool_name = getattr(tool, 'name', str(tool))
            self.failed_tools[tool_name] = str(e)
            self.logger.error(f"Error registrando herramienta {tool_name}: {e}")
            return False


def create_tool_metadata(tool: Any) -> ToolMetadata:
    """
    Crea metadatos para una herramienta.
    
    Args:
        tool: Herramienta a analizar
        
    Returns:
        ToolMetadata: Metadatos de la herramienta
    """
    
    # Extraer información básica
    name = getattr(tool, 'name', getattr(tool, '__name__', str(tool)))
    description = getattr(tool, 'description', f'Tool: {name}')
    
    # Detectar tipo de herramienta
    tool_type = ToolType.CUSTOM
    if hasattr(tool, 'name') and hasattr(tool, 'description'):
        tool_type = ToolType.LANGCHAIN
    
    # Extraer tags
    tags = []
    if hasattr(tool, '_arun'):
        tags.append("async_supported")
    if hasattr(tool, 'handle_tool_error'):
        tags.append("error_handling")
    
    # Detectar dependencias
    dependencies = []
    if hasattr(tool, 'dependencies'):
        dependencies = tool.dependencies
    
    return ToolMetadata(
        name=name,
        tool_type=tool_type,
        description=description,
        tags=tags,
        dependencies=dependencies,
        status=ToolStatus.LOADING,
        config={}
    )


async def load_langchain_tools_for_project(
    project_id: str,
    user_id: str, 
    name: str,
    number_phone_agent: str,
    unique_id: str,
    project: Any,
    enabled_tools: List[str]
) -> Dict[str, Any]:
    """
    Función principal para cargar herramientas LangChain en el sistema mejorado.
    
    Args:
        project_id: ID del proyecto
        user_id: ID del usuario
        name: Nombre del usuario  
        number_phone_agent: Número de teléfono del agente
        unique_id: ID único de la sesión
        project: Objeto del proyecto
        enabled_tools: Lista de herramientas habilitadas
        
    Returns:
        Dict con estadísticas de carga
    """
    
    loader = LangChainToolsLoader()
    return await loader.load_all_tools(
        project_id, user_id, name, number_phone_agent, 
        unique_id, project, enabled_tools
    )