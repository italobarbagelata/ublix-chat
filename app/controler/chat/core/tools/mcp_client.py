"""
Cliente MCP (Model Context Protocol) para integración con servidores MCP externos.
Este cliente permite conectar el sistema con servidores MCP como Google Calendar.
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """
    Cliente MCP para conectar con servidores externos.
    Maneja la comunicación con servidores MCP y expone sus herramientas como tools de LangChain.
    """
    
    def __init__(self, server_config: Dict[str, Any]):
        """
        Inicializa el cliente MCP.
        
        Args:
            server_config: Configuración del servidor MCP
                - name: Nombre del servidor
                - command: Comando para ejecutar el servidor
                - args: Argumentos del comando
                - env: Variables de entorno (opcional)
        """
        self.server_config = server_config
        self.session: Optional[ClientSession] = None
        self.logger = logging.getLogger(__name__)
        self.tools_cache: Dict[str, Any] = {}
        self.is_connected = False
        
    async def connect(self) -> bool:
        """
        Conecta al servidor MCP.
        
        Returns:
            True si la conexión fue exitosa, False en caso contrario
        """
        try:
            server_params = StdioServerParameters(
                command=self.server_config["command"],
                args=self.server_config.get("args", []),
                env=self.server_config.get("env", {})
            )
            
            self.logger.info(f"Conectando al servidor MCP: {self.server_config['name']}")
            
            async with stdio_client(server_params) as (read, write):
                self.session = ClientSession(read, write)
                await self.session.initialize()
                
                # Obtener herramientas disponibles
                await self._load_tools()
                self.is_connected = True
                
                self.logger.info(f"Conectado exitosamente al servidor MCP: {self.server_config['name']}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error conectando al servidor MCP {self.server_config['name']}: {str(e)}")
            self.is_connected = False
            return False
    
    async def _load_tools(self):
        """Carga las herramientas disponibles del servidor MCP."""
        try:
            if not self.session:
                raise Exception("No hay sesión activa")
                
            # Listar herramientas disponibles
            result = await self.session.list_tools()
            
            for tool in result.tools:
                self.tools_cache[tool.name] = {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
                
            self.logger.info(f"Cargadas {len(self.tools_cache)} herramientas del servidor MCP")
            
        except Exception as e:
            self.logger.error(f"Error cargando herramientas MCP: {str(e)}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Ejecuta una herramienta en el servidor MCP.
        
        Args:
            tool_name: Nombre de la herramienta
            arguments: Argumentos para la herramienta
            
        Returns:
            Resultado de la ejecución de la herramienta
        """
        try:
            if not self.session or not self.is_connected:
                raise Exception("No hay conexión activa al servidor MCP")
                
            if tool_name not in self.tools_cache:
                raise Exception(f"Herramienta '{tool_name}' no encontrada")
            
            self.logger.info(f"Ejecutando herramienta MCP: {tool_name}")
            
            result = await self.session.call_tool(tool_name, arguments)
            
            return result.content
            
        except Exception as e:
            self.logger.error(f"Error ejecutando herramienta MCP '{tool_name}': {str(e)}")
            raise
    
    def get_available_tools(self) -> List[str]:
        """
        Obtiene la lista de herramientas disponibles.
        
        Returns:
            Lista de nombres de herramientas disponibles
        """
        return list(self.tools_cache.keys())
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información de una herramienta específica.
        
        Args:
            tool_name: Nombre de la herramienta
            
        Returns:
            Información de la herramienta o None si no existe
        """
        return self.tools_cache.get(tool_name)
    
    async def disconnect(self):
        """Desconecta del servidor MCP."""
        if self.session:
            try:
                await self.session.close()
                self.is_connected = False
                self.logger.info(f"Desconectado del servidor MCP: {self.server_config['name']}")
            except Exception as e:
                self.logger.error(f"Error desconectando del servidor MCP: {str(e)}")


class MCPManager:
    """
    Gestor de múltiples clientes MCP.
    Permite manejar conexiones a múltiples servidores MCP simultáneamente.
    """
    
    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
        self.logger = logging.getLogger(__name__)
    
    async def add_server(self, server_name: str, server_config: Dict[str, Any]) -> bool:
        """
        Agrega y conecta un servidor MCP.
        
        Args:
            server_name: Nombre único del servidor
            server_config: Configuración del servidor
            
        Returns:
            True si el servidor se agregó y conectó exitosamente
        """
        try:
            client = MCPClient(server_config)
            success = await client.connect()
            
            if success:
                self.clients[server_name] = client
                self.logger.info(f"Servidor MCP '{server_name}' agregado exitosamente")
                return True
            else:
                self.logger.error(f"No se pudo conectar al servidor MCP '{server_name}'")
                return False
                
        except Exception as e:
            self.logger.error(f"Error agregando servidor MCP '{server_name}': {str(e)}")
            return False
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Ejecuta una herramienta en un servidor MCP específico.
        
        Args:
            server_name: Nombre del servidor
            tool_name: Nombre de la herramienta
            arguments: Argumentos para la herramienta
            
        Returns:
            Resultado de la ejecución
        """
        if server_name not in self.clients:
            raise Exception(f"Servidor MCP '{server_name}' no encontrado")
        
        return await self.clients[server_name].call_tool(tool_name, arguments)
    
    def get_all_tools(self) -> Dict[str, List[str]]:
        """
        Obtiene todas las herramientas disponibles de todos los servidores.
        
        Returns:
            Diccionario con servidor -> lista de herramientas
        """
        return {
            server_name: client.get_available_tools()
            for server_name, client in self.clients.items()
        }
    
    async def disconnect_all(self):
        """Desconecta todos los servidores MCP."""
        for client in self.clients.values():
            await client.disconnect()
        self.clients.clear()