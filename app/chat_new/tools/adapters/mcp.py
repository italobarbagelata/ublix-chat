"""
MCP (Model Context Protocol) Tool Adapter

Provides adaptation layer for MCP tools to work with the enhanced tool system.
Handles:
- MCP server communication and discovery
- Tool capability detection and registration
- Input/output protocol adaptation
- Resource management and cleanup
- Connection pooling and retry logic
"""

import logging
import asyncio
import json
from typing import Any, Dict, List, Optional, Union, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass

# Note: MCP is still emerging, so this is a simplified implementation
# that can be expanded when MCP becomes more standardized

from ..registry import ToolType, ToolMetadata


@dataclass
class MCPServerConfig:
    """Configuration for MCP server connection"""
    name: str
    command: List[str]
    args: List[str] = None
    env: Dict[str, str] = None
    timeout: int = 30
    retry_attempts: int = 3


@dataclass
class MCPTool:
    """Represents an MCP tool with its capabilities"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str
    tool_id: str


class MCPToolAdapter:
    """
    Adapter for MCP (Model Context Protocol) tools.
    
    Features:
    - MCP server discovery and connection management
    - Tool capability detection and registration
    - Protocol-compliant communication
    - Resource and connection lifecycle management
    - Error handling and retry logic
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.tool_type = ToolType.MCP
        
        # Server management
        self.servers: Dict[str, 'MCPServerConnection'] = {}
        self.tools: Dict[str, MCPTool] = {}
        
        # Connection pool
        self.max_connections = 10
        self.connection_timeout = 30
        
        self.logger.info("MCPToolAdapter initialized")
    
    async def discover_servers(self, config_path: Optional[str] = None) -> List[str]:
        """
        Discover available MCP servers.
        
        Args:
            config_path: Optional path to MCP configuration file
            
        Returns:
            List of discovered server names
        """
        try:
            # For now, return a simple list. In practice, this would:
            # 1. Read from MCP configuration files
            # 2. Scan for available servers
            # 3. Validate server capabilities
            
            discovered_servers = []
            
            # Example server configurations (would come from config)
            default_servers = [
                MCPServerConfig(
                    name="filesystem",
                    command=["mcp-server-filesystem"],
                    args=["--root", "/tmp"]
                ),
                MCPServerConfig(
                    name="database",
                    command=["mcp-server-database"],
                    args=["--connection", "sqlite:///app.db"]
                )
            ]
            
            for server_config in default_servers:
                try:
                    if await self._test_server_connection(server_config):
                        discovered_servers.append(server_config.name)
                        self.logger.info(f"Discovered MCP server: {server_config.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to connect to MCP server {server_config.name}: {str(e)}")
            
            return discovered_servers
            
        except Exception as e:
            self.logger.error(f"Server discovery failed: {str(e)}")
            return []
    
    async def connect_to_server(self, server_config: MCPServerConfig) -> bool:
        """
        Connect to an MCP server and register its tools.
        
        Args:
            server_config: Server configuration
            
        Returns:
            bool: True if connection successful
        """
        try:
            server_name = server_config.name
            
            if server_name in self.servers:
                self.logger.info(f"Already connected to MCP server: {server_name}")
                return True
            
            # Create server connection
            connection = MCPServerConnection(server_config, self)
            
            # Attempt connection
            if await connection.connect():
                self.servers[server_name] = connection
                
                # Discover and register tools from this server
                await self._register_server_tools(connection)
                
                self.logger.info(f"Successfully connected to MCP server: {server_name}")
                return True
            else:
                self.logger.error(f"Failed to connect to MCP server: {server_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error connecting to MCP server {server_config.name}: {str(e)}")
            return False
    
    async def disconnect_from_server(self, server_name: str) -> bool:
        """
        Disconnect from an MCP server and unregister its tools.
        
        Args:
            server_name: Name of server to disconnect from
            
        Returns:
            bool: True if disconnection successful
        """
        try:
            if server_name not in self.servers:
                return True
            
            connection = self.servers[server_name]
            
            # Unregister tools from this server
            tools_to_remove = [name for name, tool in self.tools.items() 
                             if tool.server_name == server_name]
            
            for tool_name in tools_to_remove:
                del self.tools[tool_name]
            
            # Disconnect
            await connection.disconnect()
            del self.servers[server_name]
            
            self.logger.info(f"Disconnected from MCP server: {server_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from MCP server {server_name}: {str(e)}")
            return False
    
    def adapt_tool(self, mcp_tool: MCPTool) -> 'AdaptedMCPTool':
        """
        Adapt an MCP tool to the enhanced interface.
        
        Args:
            mcp_tool: MCP tool to adapt
            
        Returns:
            AdaptedMCPTool: Wrapped tool with enhanced interface
        """
        return AdaptedMCPTool(mcp_tool, self)
    
    def extract_metadata(self, mcp_tool: MCPTool) -> ToolMetadata:
        """
        Extract metadata from an MCP tool.
        
        Args:
            mcp_tool: MCP tool instance
            
        Returns:
            ToolMetadata: Extracted metadata
        """
        
        tags = ["mcp", f"server:{mcp_tool.server_name}"]
        
        # Extract tags from schema
        if "tags" in mcp_tool.input_schema:
            tags.extend(mcp_tool.input_schema["tags"])
        
        return ToolMetadata(
            name=mcp_tool.name,
            tool_type=ToolType.MCP,
            description=mcp_tool.description,
            tags=tags,
            dependencies=[f"mcp_server:{mcp_tool.server_name}"],
            config={
                "server_name": mcp_tool.server_name,
                "tool_id": mcp_tool.tool_id,
                "input_schema": mcp_tool.input_schema
            }
        )
    
    async def execute_mcp_tool(
        self, 
        tool_name: str, 
        inputs: Dict[str, Any]
    ) -> Any:
        """
        Execute an MCP tool through its server connection.
        
        Args:
            tool_name: Name of the MCP tool
            inputs: Tool input parameters
            
        Returns:
            Tool execution result
        """
        if tool_name not in self.tools:
            raise ValueError(f"MCP tool not found: {tool_name}")
        
        mcp_tool = self.tools[tool_name]
        server_name = mcp_tool.server_name
        
        if server_name not in self.servers:
            raise ValueError(f"MCP server not connected: {server_name}")
        
        connection = self.servers[server_name]
        return await connection.execute_tool(mcp_tool.tool_id, inputs)
    
    def get_available_tools(self) -> List[str]:
        """Get list of available MCP tools."""
        return list(self.tools.keys())
    
    def get_server_status(self) -> Dict[str, Any]:
        """Get status of all MCP servers."""
        status = {}
        
        for server_name, connection in self.servers.items():
            status[server_name] = {
                "connected": connection.is_connected(),
                "tools_count": len([t for t in self.tools.values() if t.server_name == server_name]),
                "last_activity": connection.last_activity.isoformat() if connection.last_activity else None
            }
        
        return status
    
    async def _test_server_connection(self, server_config: MCPServerConfig) -> bool:
        """Test if we can connect to an MCP server."""
        try:
            # Simplified connection test
            # In practice, this would attempt to start the server process
            # and establish the MCP protocol connection
            
            # For now, just simulate success for known server types
            known_servers = ["filesystem", "database", "web", "api"]
            return any(known in server_config.name.lower() for known in known_servers)
            
        except Exception as e:
            self.logger.error(f"Server connection test failed: {str(e)}")
            return False
    
    async def _register_server_tools(self, connection: 'MCPServerConnection') -> None:
        """Register all tools from an MCP server."""
        try:
            tools = await connection.list_tools()
            
            for tool_info in tools:
                mcp_tool = MCPTool(
                    name=tool_info["name"],
                    description=tool_info.get("description", ""),
                    input_schema=tool_info.get("input_schema", {}),
                    server_name=connection.server_name,
                    tool_id=tool_info["id"]
                )
                
                self.tools[mcp_tool.name] = mcp_tool
                self.logger.info(f"Registered MCP tool: {mcp_tool.name}")
                
        except Exception as e:
            self.logger.error(f"Failed to register tools from server {connection.server_name}: {str(e)}")


class MCPServerConnection:
    """
    Manages connection to a single MCP server.
    
    Handles:
    - Server process lifecycle
    - Protocol communication
    - Tool discovery and execution
    - Connection health monitoring
    """
    
    def __init__(self, config: MCPServerConfig, adapter: MCPToolAdapter):
        self.config = config
        self.adapter = adapter
        self.logger = logging.getLogger(__name__)
        
        self.server_name = config.name
        self.process = None
        self.connected = False
        self.last_activity = None
        
        # Communication
        self.request_id = 0
        self.pending_requests = {}
    
    async def connect(self) -> bool:
        """Connect to the MCP server."""
        try:
            # In a real implementation, this would:
            # 1. Start the server process
            # 2. Establish stdio/socket communication
            # 3. Perform MCP handshake
            # 4. Negotiate capabilities
            
            # For now, simulate successful connection
            self.connected = True
            self.last_activity = datetime.now()
            
            self.logger.info(f"Connected to MCP server: {self.server_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to MCP server {self.server_name}: {str(e)}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        try:
            if self.process:
                self.process.terminate()
                await self.process.wait()
            
            self.connected = False
            self.logger.info(f"Disconnected from MCP server: {self.server_name}")
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from MCP server {self.server_name}: {str(e)}")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the server."""
        # Simulate tool discovery response
        simulated_tools = [
            {
                "id": f"{self.server_name}_tool_1",
                "name": f"{self.server_name}_reader",
                "description": f"Read data using {self.server_name}",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to read"}
                    },
                    "required": ["path"]
                }
            },
            {
                "id": f"{self.server_name}_tool_2", 
                "name": f"{self.server_name}_writer",
                "description": f"Write data using {self.server_name}",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to write"},
                        "content": {"type": "string", "description": "Content to write"}
                    },
                    "required": ["path", "content"]
                }
            }
        ]
        
        return simulated_tools
    
    async def execute_tool(self, tool_id: str, inputs: Dict[str, Any]) -> Any:
        """Execute a tool on the server."""
        try:
            self.last_activity = datetime.now()
            
            # In real implementation, this would send MCP tool execution request
            # For now, simulate execution
            
            if "reader" in tool_id:
                return {"status": "success", "data": f"Read from {inputs.get('path', 'unknown')}"}
            elif "writer" in tool_id:
                return {"status": "success", "message": f"Wrote to {inputs.get('path', 'unknown')}"}
            else:
                return {"status": "success", "result": f"Executed {tool_id} with {inputs}"}
                
        except Exception as e:
            self.logger.error(f"Tool execution failed: {str(e)}")
            raise
    
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self.connected


class AdaptedMCPTool:
    """
    Wrapper for MCP tools that provides enhanced interface.
    
    This wrapper:
    - Provides consistent async interface
    - Handles MCP protocol communication
    - Adds performance monitoring
    - Manages connection lifecycle
    """
    
    def __init__(self, mcp_tool: MCPTool, adapter: MCPToolAdapter):
        self.mcp_tool = mcp_tool
        self.adapter = adapter
        self.logger = logging.getLogger(__name__)
        
        # Extract tool properties
        self.name = mcp_tool.name
        self.description = mcp_tool.description
        self.args_schema = mcp_tool.input_schema
        
        # Performance tracking
        self.call_count = 0
        self.total_execution_time = 0.0
        self.last_execution_time = None
        
        # Error tracking
        self.error_count = 0
        self.last_error = None
    
    async def invoke(self, inputs: Dict[str, Any]) -> Any:
        """
        Invoke the MCP tool with enhanced error handling and monitoring.
        
        Args:
            inputs: Tool input parameters
            
        Returns:
            Tool execution result
        """
        start_time = datetime.now()
        
        try:
            self.call_count += 1
            
            # Validate inputs against schema
            validated_inputs = self._validate_inputs(inputs)
            
            # Execute through adapter
            result = await self.adapter.execute_mcp_tool(self.name, validated_inputs)
            
            # Update metrics
            execution_time = (datetime.now() - start_time).total_seconds()
            self.total_execution_time += execution_time
            self.last_execution_time = execution_time
            
            self.logger.debug(f"MCP tool {self.name} executed successfully in {execution_time:.3f}s")
            
            return result
            
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(
                f"MCP tool {self.name} failed after {execution_time:.3f}s: {str(e)}",
                extra={"tool_name": self.name, "inputs": inputs}
            )
            
            raise
    
    def _validate_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate inputs against MCP tool schema."""
        
        # Basic validation - in practice would use jsonschema
        required_fields = self.args_schema.get("required", [])
        
        for field in required_fields:
            if field not in inputs:
                raise ValueError(f"Required field '{field}' missing from inputs")
        
        return inputs
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for this MCP tool."""
        
        avg_execution_time = (
            self.total_execution_time / self.call_count 
            if self.call_count > 0 else 0.0
        )
        
        return {
            "name": self.name,
            "server": self.mcp_tool.server_name,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "success_rate": (self.call_count - self.error_count) / max(1, self.call_count),
            "avg_execution_time": avg_execution_time,
            "total_execution_time": self.total_execution_time,
            "last_execution_time": self.last_execution_time,
            "last_error": self.last_error
        }
    
    def __str__(self) -> str:
        return f"AdaptedMCPTool({self.name})"
    
    def __repr__(self) -> str:
        return f"AdaptedMCPTool(name='{self.name}', server='{self.mcp_tool.server_name}', calls={self.call_count})"


def create_mcp_adapter() -> MCPToolAdapter:
    """
    Factory function to create an MCP tool adapter.
    
    Returns:
        MCPToolAdapter: Configured adapter instance
    """
    return MCPToolAdapter()