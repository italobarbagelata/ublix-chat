"""
Factory para crear herramientas MCP dinámicamente.
Permite la creación y gestión de herramientas MCP de forma escalable.
"""

import logging
from typing import Dict, List, Any, Optional
from langchain_core.tools import BaseTool

from .mcp_client import MCPManager
# Google Calendar MCP tool removed - keeping infrastructure for future MCP integrations
from app.controler.chat.config.mcp_config import get_mcp_server_config, get_available_mcp_servers


class MCPToolFactory:
    """
    Factory para crear y gestionar herramientas MCP.
    Centraliza la creación de herramientas MCP y maneja sus ciclos de vida.
    """
    
    def __init__(self):
        self.mcp_manager = MCPManager()
        self.logger = logging.getLogger(__name__)
        self.created_tools: Dict[str, BaseTool] = {}
        
    async def create_mcp_tool(self, tool_type: str, project_id: str) -> Optional[BaseTool]:
        """
        Crea una herramienta MCP del tipo especificado.
        
        Args:
            tool_type: Tipo de herramienta MCP ('google_calendar', etc.)
            project_id: ID del proyecto para configuración específica
            
        Returns:
            Instancia de la herramienta MCP o None si hay error
        """
        try:
            if tool_type in self.created_tools:
                return self.created_tools[tool_type]
            
            # Placeholder for future MCP tools
            # Example: if tool_type == "github":
            #     tool = await self._create_github_tool(project_id)
            #     if tool:
            #         self.created_tools[tool_type] = tool
            #     return tool
            
            self.logger.warning(f"Tipo de herramienta MCP no soportado: {tool_type}")
            return None
                
        except Exception as e:
            self.logger.error(f"Error creando herramienta MCP {tool_type}: {str(e)}")
            return None
    
    # Google Calendar MCP tool creation method removed
    # Keep this as template for future MCP tools:
    #
    # async def _create_future_tool(self, project_id: str) -> Optional[FutureMCPTool]:
    #     """
    #     Crea una herramienta MCP futura.
    #     
    #     Args:
    #         project_id: ID del proyecto
    #         
    #     Returns:
    #         Instancia de FutureMCPTool
    #     """
    #     try:
    #         server_config = get_mcp_server_config("future_tool")
    #         if not server_config:
    #             self.logger.error("No se encontró configuración para Future MCP")
    #             return None
    #         
    #         if "future_tool" not in self.mcp_manager.clients:
    #             success = await self.mcp_manager.add_server("future_tool", server_config)
    #             if not success:
    #                 self.logger.error("No se pudo conectar al servidor Future MCP")
    #                 return None
    #         
    #         tool = FutureMCPTool()
    #         self.logger.info(f"Herramienta Future MCP creada para proyecto {project_id}")
    #         return tool
    #         
    #     except Exception as e:
    #         self.logger.error(f"Error creando Future MCP tool: {str(e)}")
    #         return None
    
    async def get_available_tools(self) -> List[str]:
        """
        Obtiene la lista de herramientas MCP disponibles.
        
        Returns:
            Lista de tipos de herramientas MCP disponibles
        """
        available_tools = []
        
        # Placeholder for future MCP tools
        # Example: if get_mcp_server_config("github"):
        #     available_tools.append("github")
        
        return available_tools
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica el estado de salud de las herramientas MCP.
        
        Returns:
            Diccionario con el estado de cada herramienta MCP
        """
        health_status = {}
        
        for tool_name, client in self.mcp_manager.clients.items():
            health_status[tool_name] = {
                "connected": client.is_connected,
                "tools_available": len(client.get_available_tools())
            }
        
        return health_status
    
    async def cleanup(self):
        """Limpia recursos y desconecta clientes MCP."""
        try:
            await self.mcp_manager.disconnect_all()
            self.created_tools.clear()
            self.logger.info("Cleanup de herramientas MCP completado")
        except Exception as e:
            self.logger.error(f"Error en cleanup de herramientas MCP: {str(e)}")


# Instancia global del factory (singleton)
_mcp_tool_factory = None

def get_mcp_tool_factory() -> MCPToolFactory:
    """
    Obtiene la instancia singleton del factory de herramientas MCP.
    
    Returns:
        Instancia del MCPToolFactory
    """
    global _mcp_tool_factory
    if _mcp_tool_factory is None:
        _mcp_tool_factory = MCPToolFactory()
    return _mcp_tool_factory


async def create_mcp_tools_for_project(project_id: str, enabled_mcp_tools: List[str]) -> List[BaseTool]:
    """
    Crea herramientas MCP para un proyecto específico.
    
    Args:
        project_id: ID del proyecto
        enabled_mcp_tools: Lista de herramientas MCP habilitadas
        
    Returns:
        Lista de herramientas MCP creadas
    """
    factory = get_mcp_tool_factory()
    tools = []
    
    for tool_type in enabled_mcp_tools:
        tool = await factory.create_mcp_tool(tool_type, project_id)
        if tool:
            tools.append(tool)
    
    return tools