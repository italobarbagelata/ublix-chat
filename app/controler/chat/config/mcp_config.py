"""
Configuración para servidores MCP (Model Context Protocol).
Define las configuraciones de servidores MCP disponibles para el sistema.
"""

from typing import Dict, Any
import os

# Configuraciones de servidores MCP disponibles
MCP_SERVERS_CONFIG = {
    # Google Calendar MCP removed - using native calendar_tool.py instead
    # Template for future MCP servers:
    # "server_name": {
    #     "name": "server-name",
    #     "command": "command_to_run",
    #     "args": ["arg1", "arg2"],
    #     "env": {},
    #     "description": "Description of the server",
    #     "tools": ["tool1", "tool2"]
    # },
    
    # Aquí se pueden agregar más servidores MCP en el futuro
    "example_future_server": {
        "name": "example-mcp-server",
        "command": "python",
        "args": ["-m", "example_mcp_server"],
        "env": {},
        "description": "Ejemplo de configuración para futuros servidores MCP",
        "tools": []
    }
}

def get_mcp_server_config(server_name: str) -> Dict[str, Any]:
    """
    Obtiene la configuración de un servidor MCP específico.
    
    Args:
        server_name: Nombre del servidor MCP
        
    Returns:
        Configuración del servidor o None si no existe
    """
    return MCP_SERVERS_CONFIG.get(server_name)

def get_available_mcp_servers() -> list[str]:
    """
    Obtiene la lista de servidores MCP disponibles.
    
    Returns:
        Lista de nombres de servidores MCP disponibles
    """
    return list(MCP_SERVERS_CONFIG.keys())

def validate_mcp_config(server_name: str) -> bool:
    """
    Valida que la configuración de un servidor MCP esté completa.
    
    Args:
        server_name: Nombre del servidor MCP
        
    Returns:
        True si la configuración es válida, False en caso contrario
    """
    config = get_mcp_server_config(server_name)
    if not config:
        return False
    
    # Verificar campos obligatorios
    required_fields = ["name", "command", "args"]
    return all(field in config for field in required_fields)

# Configuration templates for future MCP servers
# Example:
# FUTURE_MCP_CONFIG = {
#     "specific_setting": "value",
#     "another_setting": "another_value"
# }