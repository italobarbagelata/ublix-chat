"""
Tool Registry - Advanced Tool Management System

The ToolRegistry provides:
1. Dynamic tool registration and discovery
2. Tool lifecycle management (load, unload, reload)
3. Tool metadata and status tracking
4. Circuit breaker pattern for failed tools
5. Tool caching and performance optimization
6. Middleware integration for cross-cutting concerns
7. Multi-adapter support (LangChain, MCP, Custom)

This registry acts as the central hub for all tool operations.
"""

import logging
import asyncio
import inspect
from typing import Dict, List, Optional, Any, Callable, Union, Type
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import weakref

from langchain.tools import BaseTool

from ..core.state import EnhancedState, ToolState, add_tool_result, add_error, ErrorSeverity


class ToolStatus(Enum):
    """Tool status enumeration"""
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"
    CIRCUIT_OPEN = "circuit_open"
    LOADING = "loading"
    UNLOADING = "unloading"


class ToolType(Enum):
    """Tool type enumeration"""
    LANGCHAIN = "langchain"
    MCP = "mcp"
    CUSTOM = "custom"
    BUILTIN = "builtin"


@dataclass
class ToolMetadata:
    """Metadata for tool registration and management"""
    name: str
    tool_type: ToolType
    description: str
    version: str = "1.0.0"
    status: ToolStatus = ToolStatus.ACTIVE
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Performance tracking
    call_count: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_execution_time: float = 0.0
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    
    # Circuit breaker
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: timedelta = timedelta(minutes=5)
    circuit_breaker_open_since: Optional[datetime] = None


@dataclass  
class ToolRegistration:
    """Complete tool registration with instance and metadata"""
    metadata: ToolMetadata
    tool_instance: Any
    adapter: Optional[Any] = None
    middleware_stack: List[Callable] = field(default_factory=list)


class ToolRegistry:
    """
    Advanced tool registry with lifecycle management and reliability patterns.
    
    Features:
    - Dynamic tool loading and unloading
    - Circuit breaker pattern for failed tools
    - Tool performance monitoring
    - Middleware integration
    - Multi-adapter support
    - Hot-reload capabilities
    - Dependency management
    """
    
    def __init__(self, max_workers: int = 3):
        self.logger = logging.getLogger(__name__)
        
        # Core registry storage
        self.tools: Dict[str, ToolRegistration] = {}
        self.tool_groups: Dict[str, List[str]] = {}  # Group tools by category
        
        # Adapter registry
        self.adapters: Dict[ToolType, Any] = {}
        
        # Middleware registry
        self.global_middleware: List[Callable] = []
        
        # Performance tracking
        self.execution_stats: Dict[str, List[float]] = {}
        
        # Circuit breaker state
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # Async execution
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Tool cache
        self.tool_cache: Dict[str, Any] = {}
        self.cache_ttl = timedelta(minutes=5)
        
        # Dependency graph
        self.dependency_graph: Dict[str, List[str]] = {}
        
        # Initialize default adapters
        self._initialize_default_adapters()
        
        self.logger.info("ToolRegistry initialized")
    
    def register_adapter(self, tool_type: ToolType, adapter_class: Type) -> None:
        """
        Register a tool adapter for a specific tool type.
        
        Args:
            tool_type: Type of tools this adapter handles
            adapter_class: Adapter class to instantiate
        """
        try:
            self.adapters[tool_type] = adapter_class()
            self.logger.info(f"Registered adapter for {tool_type.value}")
        except Exception as e:
            self.logger.error(f"Failed to register adapter for {tool_type.value}: {str(e)}")
    
    def register_middleware(self, middleware: Callable, global_scope: bool = True) -> None:
        """
        Register middleware for tool execution.
        
        Args:
            middleware: Middleware function
            global_scope: Whether to apply to all tools or specific ones
        """
        if global_scope:
            self.global_middleware.append(middleware)
            self.logger.info(f"Registered global middleware: {middleware.__name__}")
        
    def register_tool(
        self,
        tool: Any,
        metadata: Optional[ToolMetadata] = None,
        force: bool = False
    ) -> bool:
        """
        Register a tool with the registry.
        
        Args:
            tool: Tool instance to register
            metadata: Optional tool metadata
            force: Force registration even if tool exists
            
        Returns:
            bool: True if registration successful
        """
        try:
            # Generate metadata if not provided
            if metadata is None:
                metadata = self._generate_tool_metadata(tool)
            
            tool_name = metadata.name
            
            # Check if tool already exists
            if tool_name in self.tools and not force:
                self.logger.warning(f"Tool {tool_name} already registered")
                return False
            
            # Determine tool type and get adapter
            tool_type = metadata.tool_type
            adapter = self.adapters.get(tool_type)
            
            self.logger.info(f"🔍 Tool {tool_name}: type={tool_type.value}, adapter={'found' if adapter else 'NOT FOUND'}")
            
            if tool_type != ToolType.BUILTIN and adapter is None:
                self.logger.error(f"No adapter found for tool type {tool_type.value}")
                return False
            
            # Create registration
            registration = ToolRegistration(
                metadata=metadata,
                tool_instance=tool,
                adapter=adapter,
                middleware_stack=self.global_middleware.copy()
            )
            
            # Validate tool
            if not self._validate_tool(tool, metadata):
                self.logger.error(f"Tool validation failed for {tool_name}")
                return False
            
            # Register tool
            self.tools[tool_name] = registration
            
            # Initialize circuit breaker
            self._init_circuit_breaker(tool_name)
            
            # Add to dependency graph
            self._update_dependency_graph(tool_name, metadata.dependencies)
            
            self.logger.info(f"Successfully registered tool: {tool_name} ({tool_type.value})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register tool: {str(e)}", exc_info=True)
            return False
    
    def unregister_tool(self, tool_name: str) -> bool:
        """
        Unregister a tool from the registry.
        
        Args:
            tool_name: Name of tool to unregister
            
        Returns:
            bool: True if unregistration successful
        """
        try:
            if tool_name not in self.tools:
                self.logger.warning(f"Tool {tool_name} not found for unregistration")
                return False
            
            # Check dependencies
            dependent_tools = self._get_dependent_tools(tool_name)
            if dependent_tools:
                self.logger.error(f"Cannot unregister {tool_name}: has dependents {dependent_tools}")
                return False
            
            # Update status
            self.tools[tool_name].metadata.status = ToolStatus.UNLOADING
            
            # Cleanup
            self._cleanup_tool(tool_name)
            
            # Remove from registry
            del self.tools[tool_name]
            
            self.logger.info(f"Successfully unregistered tool: {tool_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unregister tool {tool_name}: {str(e)}")
            return False
    
    async def execute_tool(
        self,
        tool_name: str,
        state: EnhancedState,
        **kwargs
    ) -> Any:
        """
        Execute a tool with full middleware stack and error handling.
        
        Args:
            tool_name: Name of tool to execute
            state: Current enhanced state
            **kwargs: Tool arguments
            
        Returns:
            Tool execution result
        """
        start_time = datetime.now()
        
        try:
            # Check if tool exists and is available
            if not self._is_tool_available(tool_name):
                error_msg = f"Tool {tool_name} not available"
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            registration = self.tools[tool_name]
            metadata = registration.metadata
            
            # Check circuit breaker
            if not self._check_circuit_breaker(tool_name):
                error_msg = f"Tool {tool_name} circuit breaker is open"
                self.logger.warning(error_msg)
                raise RuntimeError(error_msg)
            
            # Execute through middleware stack
            result = await self._execute_with_middleware(
                registration, state, **kwargs
            )
            
            # Update success metrics
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_tool_metrics(tool_name, True, execution_time)
            
            # Add to state
            add_tool_result(state, tool_name, result, execution_time, True)
            
            self.logger.info(f"Tool {tool_name} executed successfully in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            # Update error metrics
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_tool_metrics(tool_name, False, execution_time, str(e))
            
            # Update circuit breaker
            self._record_tool_failure(tool_name, str(e))
            
            # Add error to state
            add_error(state, e, f"Tool execution: {tool_name}", ErrorSeverity.MEDIUM)
            
            self.logger.error(f"Tool {tool_name} execution failed: {str(e)}")
            raise
    
    def get_available_tools(self, state: EnhancedState) -> List[str]:
        """
        Get list of available tools based on project configuration and tool status.
        
        Args:
            state: Current enhanced state
            
        Returns:
            List of available tool names
        """
        project = state["user"]["project"]
        enabled_tools = project.enabled_tools if hasattr(project, 'enabled_tools') else []
        
        available = []
        
        for tool_name, registration in self.tools.items():
            metadata = registration.metadata
            
            # Check if tool is enabled for this project
            if self._is_tool_enabled_for_project(tool_name, enabled_tools):
                # Check tool status
                if metadata.status == ToolStatus.ACTIVE:
                    # Check circuit breaker
                    if self._check_circuit_breaker(tool_name):
                        available.append(tool_name)
        
        return available
    
    def get_tool_instances(self, tool_names: List[str]) -> List[Any]:
        """
        Get tool instances for the given tool names.
        
        Args:
            tool_names: List of tool names
            
        Returns:
            List of original tool instances (for LangChain compatibility)
        """
        instances = []
        
        for tool_name in tool_names:
            if tool_name in self.tools:
                registration = self.tools[tool_name]
                
                # Return original tool instance for LangChain compatibility
                # The adapter is used only during execution, not for tool binding
                instance = registration.tool_instance
                instances.append(instance)
                
        return instances
    
    def reload_tool(self, tool_name: str) -> bool:
        """
        Reload a tool (useful for development and updates).
        
        Args:
            tool_name: Name of tool to reload
            
        Returns:
            bool: True if reload successful
        """
        try:
            if tool_name not in self.tools:
                return False
            
            registration = self.tools[tool_name]
            
            # Reset circuit breaker
            self._reset_circuit_breaker(tool_name)
            
            # Reset metrics
            registration.metadata.call_count = 0
            registration.metadata.success_count = 0
            registration.metadata.error_count = 0
            registration.metadata.avg_execution_time = 0.0
            registration.metadata.last_error = None
            
            # Update status
            registration.metadata.status = ToolStatus.ACTIVE
            
            self.logger.info(f"Tool {tool_name} reloaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to reload tool {tool_name}: {str(e)}")
            return False
    
    def get_tool_status(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed status information for a tool.
        
        Args:
            tool_name: Name of tool
            
        Returns:
            Dict with tool status information or None if not found
        """
        if tool_name not in self.tools:
            return None
        
        registration = self.tools[tool_name]
        metadata = registration.metadata
        
        return {
            "name": tool_name,
            "type": metadata.tool_type.value,
            "status": metadata.status.value,
            "description": metadata.description,
            "version": metadata.version,
            "tags": metadata.tags,
            "call_count": metadata.call_count,
            "success_count": metadata.success_count,
            "error_count": metadata.error_count,
            "success_rate": metadata.success_count / max(1, metadata.call_count),
            "avg_execution_time": metadata.avg_execution_time,
            "last_used": metadata.last_used.isoformat() if metadata.last_used else None,
            "last_error": metadata.last_error,
            "circuit_breaker_status": self._get_circuit_breaker_status(tool_name),
            "dependencies": metadata.dependencies
        }
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get overall registry statistics."""
        total_tools = len(self.tools)
        active_tools = len([t for t in self.tools.values() if t.metadata.status == ToolStatus.ACTIVE])
        
        total_calls = sum(t.metadata.call_count for t in self.tools.values())
        total_successes = sum(t.metadata.success_count for t in self.tools.values())
        
        return {
            "total_tools": total_tools,
            "active_tools": active_tools,
            "total_calls": total_calls,
            "total_successes": total_successes,
            "overall_success_rate": total_successes / max(1, total_calls),
            "tool_types": {tt.value: len([t for t in self.tools.values() if t.metadata.tool_type == tt]) 
                          for tt in ToolType},
            "circuit_breakers_open": len([name for name in self.tools.keys() 
                                        if not self._check_circuit_breaker(name)])
        }
    
    # Private helper methods
    
    def _generate_tool_metadata(self, tool: Any) -> ToolMetadata:
        """Generate metadata for a tool."""
        
        # Determine tool type
        if isinstance(tool, BaseTool):
            tool_type = ToolType.LANGCHAIN
        elif hasattr(tool, '_mcp_server'):
            tool_type = ToolType.MCP
        else:
            tool_type = ToolType.CUSTOM
        
        # Extract name and description
        name = getattr(tool, 'name', tool.__class__.__name__)
        description = getattr(tool, 'description', f"Tool: {name}")
        
        return ToolMetadata(
            name=name,
            tool_type=tool_type,
            description=description
        )
    
    def _validate_tool(self, tool: Any, metadata: ToolMetadata) -> bool:
        """Validate tool before registration."""
        
        # Check required attributes based on tool type
        if metadata.tool_type == ToolType.LANGCHAIN:
            required_attrs = ['name', 'description']
            return all(hasattr(tool, attr) for attr in required_attrs)
        
        elif metadata.tool_type == ToolType.MCP:
            return hasattr(tool, '_mcp_server')
        
        elif metadata.tool_type == ToolType.CUSTOM:
            # Custom tools should have __call__ or invoke method
            return hasattr(tool, '__call__') or hasattr(tool, 'invoke')
        
        return True
    
    def _is_tool_available(self, tool_name: str) -> bool:
        """Check if tool is available for execution."""
        if tool_name not in self.tools:
            return False
        
        metadata = self.tools[tool_name].metadata
        return metadata.status == ToolStatus.ACTIVE
    
    def _is_tool_enabled_for_project(self, tool_name: str, enabled_tools: List[str]) -> bool:
        """Check if tool is enabled for the current project."""
        
        # Built-in tools are always available (herramientas siempre disponibles)
        always_available = [
            'current_datetime_tool', 'week_info_tool', 'check_chile_holiday_tool',
            'next_chile_holidays_tool', 'test_calendar_connectivity', 'save_contact_tool'
        ]
        
        if tool_name in always_available:
            return True
        
        # Check exact match first
        if tool_name in enabled_tools:
            return True
        
        # Check if tool category is enabled (buscar por categoría)
        tool_category_map = {
            'agenda_tool': 'agenda_tool',
            'image_processor': 'image_processor',
            'unified_search_tool': 'unified_search',
            'document_retriever': 'retriever',
            'faq_retriever': 'faq_retriever',
            'search_products_unified': 'products_search',
            'openai_vector_search': 'openai_vector',
            'google_calendar_tool': 'calendar',
            'mongo_db_tool': 'mongo_db',
            'buscar_en_vector_openai': 'buscar_en_vector_openai',
            'buscar_productos_tienda': 'tienda',
            'consultar_info_tienda': 'tienda',
            'gestionar_carrito': 'tienda'
        }
        
        # Buscar por mapeo de categorías
        category = tool_category_map.get(tool_name)
        if category and category in enabled_tools:
            return True
        
        # Fallback: buscar si alguna herramienta habilitada está en el nombre
        return any(enabled in tool_name for enabled in enabled_tools)
    
    async def _execute_with_middleware(
        self,
        registration: ToolRegistration,
        state: EnhancedState,
        **kwargs
    ) -> Any:
        """Execute tool through middleware stack."""
        
        tool_instance = registration.tool_instance
        middleware_stack = registration.middleware_stack
        
        # Build execution chain
        async def execute():
            if registration.adapter:
                self.logger.info(f"🔧 Using adapter for {registration.metadata.name}")
                adapted_tool = registration.adapter.adapt_tool(tool_instance)
                
                # CRÍTICO: Pasar el estado actual al adaptador para tools que lo requieren
                # Esto permite que el adaptador inyecte el parámetro 'state' automáticamente
                if hasattr(adapted_tool, '_set_current_state'):
                    adapted_tool._set_current_state(state)
                    self.logger.info(f"🎯 Set current state for {registration.metadata.name}")
                
                if asyncio.iscoroutinefunction(adapted_tool.invoke):
                    return await adapted_tool.invoke(kwargs)
                else:
                    return adapted_tool.invoke(kwargs)
            else:
                self.logger.info(f"❌ No adapter for {registration.metadata.name}, using direct execution")
                # Direct execution
                if hasattr(tool_instance, 'invoke'):
                    if asyncio.iscoroutinefunction(tool_instance.invoke):
                        return await tool_instance.invoke(kwargs)
                    else:
                        return tool_instance.invoke(kwargs)
                elif callable(tool_instance):
                    if asyncio.iscoroutinefunction(tool_instance):
                        return await tool_instance(**kwargs)
                    else:
                        return tool_instance(**kwargs)
                else:
                    raise RuntimeError(f"Tool {registration.metadata.name} is not callable")
        
        # Apply middleware (simplified for now)
        return await execute()
    
    def _init_circuit_breaker(self, tool_name: str) -> None:
        """Initialize circuit breaker for a tool."""
        self.circuit_breakers[tool_name] = {
            "failure_count": 0,
            "last_failure": None,
            "state": "closed"  # closed, open, half_open
        }
    
    def _check_circuit_breaker(self, tool_name: str) -> bool:
        """Check if circuit breaker allows execution."""
        if tool_name not in self.circuit_breakers:
            return True
        
        cb = self.circuit_breakers[tool_name]
        metadata = self.tools[tool_name].metadata
        
        if cb["state"] == "closed":
            return True
        
        elif cb["state"] == "open":
            # Check if timeout has passed
            if cb["last_failure"]:
                time_since_failure = datetime.now() - cb["last_failure"]
                if time_since_failure > metadata.circuit_breaker_timeout:
                    cb["state"] = "half_open"
                    return True
            return False
        
        elif cb["state"] == "half_open":
            return True
        
        return False
    
    def _record_tool_failure(self, tool_name: str, error: str) -> None:
        """Record a tool failure for circuit breaker."""
        if tool_name not in self.circuit_breakers:
            return
        
        cb = self.circuit_breakers[tool_name]
        metadata = self.tools[tool_name].metadata
        
        cb["failure_count"] += 1
        cb["last_failure"] = datetime.now()
        metadata.last_error = error
        
        # Open circuit breaker if threshold reached
        if cb["failure_count"] >= metadata.circuit_breaker_threshold:
            cb["state"] = "open"
            metadata.status = ToolStatus.CIRCUIT_OPEN
            metadata.circuit_breaker_open_since = datetime.now()
    
    def _reset_circuit_breaker(self, tool_name: str) -> None:
        """Reset circuit breaker for a tool."""
        if tool_name in self.circuit_breakers:
            self.circuit_breakers[tool_name] = {
                "failure_count": 0,
                "last_failure": None,
                "state": "closed"
            }
        
        if tool_name in self.tools:
            metadata = self.tools[tool_name].metadata
            metadata.status = ToolStatus.ACTIVE
            metadata.circuit_breaker_open_since = None
    
    def _get_circuit_breaker_status(self, tool_name: str) -> Dict[str, Any]:
        """Get circuit breaker status for a tool."""
        if tool_name not in self.circuit_breakers:
            return {"state": "unknown"}
        
        return self.circuit_breakers[tool_name].copy()
    
    def _update_tool_metrics(
        self,
        tool_name: str,
        success: bool,
        execution_time: float,
        error: Optional[str] = None
    ) -> None:
        """Update tool performance metrics."""
        if tool_name not in self.tools:
            return
        
        metadata = self.tools[tool_name].metadata
        
        metadata.call_count += 1
        metadata.last_used = datetime.now()
        
        if success:
            metadata.success_count += 1
            # Reset circuit breaker on success
            if tool_name in self.circuit_breakers:
                cb = self.circuit_breakers[tool_name]
                if cb["state"] == "half_open":
                    cb["state"] = "closed"
                    cb["failure_count"] = 0
        else:
            metadata.error_count += 1
            if error:
                metadata.last_error = error
        
        # Update average execution time
        total_time = metadata.avg_execution_time * (metadata.call_count - 1) + execution_time
        metadata.avg_execution_time = total_time / metadata.call_count
    
    def _update_dependency_graph(self, tool_name: str, dependencies: List[str]) -> None:
        """Update dependency graph for a tool."""
        self.dependency_graph[tool_name] = dependencies.copy()
    
    def _get_dependent_tools(self, tool_name: str) -> List[str]:
        """Get tools that depend on the given tool."""
        dependents = []
        for tool, deps in self.dependency_graph.items():
            if tool_name in deps:
                dependents.append(tool)
        return dependents
    
    def _cleanup_tool(self, tool_name: str) -> None:
        """Cleanup resources for a tool."""
        # Remove from circuit breakers
        if tool_name in self.circuit_breakers:
            del self.circuit_breakers[tool_name]
        
        # Remove from dependency graph
        if tool_name in self.dependency_graph:
            del self.dependency_graph[tool_name]
        
        # Clear from cache
        cache_keys_to_remove = [k for k in self.tool_cache.keys() if tool_name in k]
        for key in cache_keys_to_remove:
            del self.tool_cache[key]
    
    def _initialize_default_adapters(self) -> None:
        """Initialize default tool adapters."""
        
        try:
            # Register LangChain adapter
            from .adapters.langchain import create_langchain_adapter
            self.adapters[ToolType.LANGCHAIN] = create_langchain_adapter()
            self.logger.info("Registered LangChain adapter")
            
        except ImportError as e:
            self.logger.warning(f"Could not import LangChain adapter: {e}")
        except Exception as e:
            self.logger.error(f"Failed to initialize LangChain adapter: {e}")
        
        try:
            # Register MCP adapter if available
            from .adapters.mcp import create_mcp_adapter
            self.adapters[ToolType.MCP] = create_mcp_adapter()
            self.logger.info("Registered MCP adapter")
            
        except ImportError as e:
            self.logger.debug(f"MCP adapter not available: {e}")
        except Exception as e:
            self.logger.error(f"Failed to initialize MCP adapter: {e}")


# Global registry instance
_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def register_tool(tool: Any, metadata: Optional[ToolMetadata] = None) -> bool:
    """Convenience function to register a tool with the global registry."""
    return get_tool_registry().register_tool(tool, metadata)