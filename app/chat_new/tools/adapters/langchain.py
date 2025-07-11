"""
LangChain Tool Adapter

Provides adaptation layer for LangChain BaseTool instances to work
with the enhanced tool system. Handles:
- Tool wrapping and interface standardization
- Input/output validation and transformation
- Error handling and retry logic
- Performance monitoring integration
- Async/sync execution bridging
"""

import logging
import asyncio
import inspect
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime

from langchain.tools import BaseTool
from langchain_core.tools import ToolException

from ..registry import ToolType, ToolMetadata


class LangChainToolAdapter:
    """
    Adapter for LangChain BaseTool instances.
    
    Features:
    - Automatic async/sync handling
    - Input validation and transformation
    - Enhanced error reporting
    - Performance tracking
    - Tool metadata extraction
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.tool_type = ToolType.LANGCHAIN
    
    def adapt_tool(self, tool: BaseTool) -> 'AdaptedLangChainTool':
        """
        Adapt a LangChain BaseTool to the enhanced interface.
        
        Args:
            tool: LangChain BaseTool instance
            
        Returns:
            AdaptedLangChainTool: Wrapped tool with enhanced interface
        """
        return AdaptedLangChainTool(tool, self)
    
    def extract_metadata(self, tool: BaseTool) -> ToolMetadata:
        """
        Extract metadata from a LangChain tool.
        
        Args:
            tool: LangChain BaseTool instance
            
        Returns:
            ToolMetadata: Extracted metadata
        """
        
        # Extract basic information
        name = tool.name
        description = tool.description
        
        # Extract tags from description or tool attributes
        tags = []
        if hasattr(tool, 'tags'):
            tags.extend(tool.tags)
        
        # Determine if tool has async support
        if hasattr(tool, '_arun') and callable(tool._arun):
            tags.append("async_supported")
        
        # Check for special capabilities
        if hasattr(tool, 'handle_tool_error'):
            tags.append("error_handling")
        
        if hasattr(tool, 'return_direct'):
            tags.append("direct_return")
        
        # Extract dependencies from description or args
        dependencies = []
        if hasattr(tool, 'dependencies'):
            dependencies.extend(tool.dependencies)
        
        return ToolMetadata(
            name=name,
            tool_type=ToolType.LANGCHAIN,
            description=description,
            tags=tags,
            dependencies=dependencies,
            config={
                "args_schema": str(tool.args_schema) if tool.args_schema else None,
                "return_direct": getattr(tool, 'return_direct', False),
                "verbose": getattr(tool, 'verbose', False)
            }
        )
    
    def validate_tool(self, tool: BaseTool) -> bool:
        """
        Validate that a tool is properly configured.
        
        Args:
            tool: Tool to validate
            
        Returns:
            bool: True if valid
        """
        
        if not isinstance(tool, BaseTool):
            self.logger.error(f"Tool is not a BaseTool instance: {type(tool)}")
            return False
        
        if not tool.name:
            self.logger.error("Tool missing name")
            return False
        
        if not tool.description:
            self.logger.error(f"Tool {tool.name} missing description")
            return False
        
        # Check if tool has required methods
        if not (hasattr(tool, '_run') or hasattr(tool, '_arun')):
            self.logger.error(f"Tool {tool.name} missing _run or _arun method")
            return False
        
        return True


class AdaptedLangChainTool:
    """
    Wrapper for LangChain tools that provides enhanced interface.
    
    This wrapper:
    - Provides consistent async/sync interface
    - Adds performance monitoring
    - Handles errors gracefully
    - Validates inputs and outputs
    - Integrates with circuit breaker patterns
    """
    
    def __init__(self, tool: BaseTool, adapter: LangChainToolAdapter):
        self.tool = tool
        self.adapter = adapter
        self.logger = logging.getLogger(__name__)
        
        # Extract tool properties
        self.name = tool.name
        self.description = tool.description
        self.args_schema = tool.args_schema
        
        # Performance tracking
        self.call_count = 0
        self.total_execution_time = 0.0
        self.last_execution_time = None
        
        # Error tracking
        self.error_count = 0
        self.last_error = None
        
        # State tracking for tools that require it
        self._current_enhanced_state = None
    
    async def invoke(self, inputs: Dict[str, Any]) -> Any:
        """
        Invoke the tool with enhanced error handling and monitoring.
        
        Args:
            inputs: Tool input parameters
            
        Returns:
            Tool execution result
        """
        start_time = datetime.now()
        
        try:
            self.call_count += 1
            
            # CRÍTICO: Inyectar state ANTES de validación Pydantic
            enhanced_inputs = self._enhance_inputs_with_state(inputs)
            
            # Validate inputs (ahora ya incluye 'state' si es necesario)
            validated_inputs = self._validate_inputs(enhanced_inputs)
            
            # Execute tool
            result = await self._execute_tool(validated_inputs)
            
            # Validate output
            validated_result = self._validate_output(result)
            
            # Update metrics
            execution_time = (datetime.now() - start_time).total_seconds()
            self.total_execution_time += execution_time
            self.last_execution_time = execution_time
            
            self.logger.debug(f"Tool {self.name} executed successfully in {execution_time:.3f}s")
            
            return validated_result
            
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            
            # Log error with context
            execution_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(
                f"Tool {self.name} failed after {execution_time:.3f}s: {str(e)}",
                extra={"tool_name": self.name, "inputs": inputs}
            )
            
            # Re-raise with additional context
            raise ToolException(f"Tool {self.name} execution failed: {str(e)}") from e
    
    def _set_current_state(self, state: Any) -> None:
        """
        Set the current enhanced state for this tool execution.
        
        Args:
            state: Current enhanced state
        """
        self._current_enhanced_state = state
    
    async def _execute_tool(self, inputs: Dict[str, Any]) -> Any:
        """Execute the underlying LangChain tool."""
        
        # CRÍTICO: Para tools que usan InjectedState, necesitamos bypass completo
        # de la validación de LangChain y llamar directamente a la función
        
        # Verificar si el tool tiene función original (unified_search_tool)
        if hasattr(self.tool, 'func') and hasattr(self.tool.func, '__name__'):
            tool_func_name = self.tool.func.__name__
            if tool_func_name == 'unified_search_tool':
                self.logger.info(f"🔄 Executing {tool_func_name} with direct function call")
                
                # Llamar directamente a la función con estado inyectado
                enhanced_inputs = self._enhance_inputs_with_state(inputs)
                
                # Inyectar estado como segundo parámetro para unified_search_tool
                if self._current_enhanced_state:
                    try:
                        # Preparar estado simplificado para la función
                        user_data = self._current_enhanced_state.get('user', {})
                        project_obj = user_data.get('project')
                        
                        simplified_state = {
                            'project': project_obj,  # Pasar el objeto proyecto directamente
                            'user_id': user_data.get('user_id'),
                            'project_id': getattr(project_obj, 'id', '') if project_obj else '',
                            'conversation_id': self._current_enhanced_state.get('conversation', {}).get('conversation_id', ''),
                            'unique_id': self._current_enhanced_state.get('unique_id', ''),
                            'messages': self._current_enhanced_state.get('messages', [])
                        }
                        
                        # Llamar directamente a la función bypassing LangChain
                        return await asyncio.get_event_loop().run_in_executor(
                            None, 
                            lambda: self.tool.func(
                                enhanced_inputs.get('query', ''),
                                simplified_state,
                                enhanced_inputs.get('content_types'),
                                enhanced_inputs.get('limit', 15),
                                enhanced_inputs.get('category')
                            )
                        )
                    except Exception as e:
                        self.logger.error(f"Direct function call failed: {e}")
                        # Fallback al método normal
                        pass
        
        # Método normal para otras herramientas
        enhanced_inputs = self._enhance_inputs_with_state(inputs)
        
        # Determine execution method
        if hasattr(self.tool, '_arun') and callable(self.tool._arun):
            # Use async method if available
            try:
                return await self.tool._arun(**enhanced_inputs)
            except TypeError as e:
                if "config" in str(e):
                    # Add minimal config if required
                    from langchain_core.runnables import RunnableConfig
                    config = RunnableConfig()
                    return await self.tool._arun(config=config, **enhanced_inputs)
                elif "state" in str(e) or "missing" in str(e):
                    # Fallback para tools que esperan state en sync
                    self.logger.warning(f"Tool {self.name} requires state, falling back to sync execution")
                    return await self._execute_sync(enhanced_inputs)
                else:
                    # Fallback to sync if async fails for other reasons
                    self.logger.warning(f"Async execution failed for {self.name}, falling back to sync")
                    return await self._execute_sync(enhanced_inputs)
            except Exception as e:
                # Fallback to sync if async fails
                self.logger.warning(f"Async execution failed for {self.name}, falling back to sync")
                return await self._execute_sync(enhanced_inputs)
        else:
            # Use sync method
            return await self._execute_sync(enhanced_inputs)
    
    async def _execute_sync(self, inputs: Dict[str, Any]) -> Any:
        """Execute sync tool in thread pool."""
        
        def sync_execution():
            # Some tools require a config parameter or state
            try:
                return self.tool._run(**inputs)
            except TypeError as e:
                if "config" in str(e):
                    # Add minimal config if required
                    from langchain_core.runnables import RunnableConfig
                    config = RunnableConfig()
                    return self.tool._run(config=config, **inputs)
                elif "state" in str(e) and "state" not in inputs:
                    # Add state if required but not provided
                    self.logger.warning(f"Tool {self.name} requires state parameter, adding mock state")
                    return self.tool._run(state={}, **inputs)
                else:
                    raise
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_execution)
    
    def _enhance_inputs_with_state(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance inputs with state for tools that require it.
        
        Args:
            inputs: Original tool inputs
            
        Returns:
            Enhanced inputs with state if needed
        """
        
        # Check if tool requires state parameter
        if hasattr(self.tool, '_run'):
            import inspect
            sig = inspect.signature(self.tool._run)
            if 'state' in sig.parameters and 'state' not in inputs:
                # Use current enhanced state if available
                if self._current_enhanced_state:
                    try:
                        enhanced_state = self._current_enhanced_state
                        
                        # Create a simplified state for the tool
                        tool_state = {
                            'project': enhanced_state.get('user', {}).get('project'),
                            'user_id': enhanced_state.get('user', {}).get('user_id'),
                            'project_id': enhanced_state.get('user', {}).get('project', {}).get('project_id', ''),
                            'conversation_id': enhanced_state.get('conversation', {}).get('conversation_id', ''),
                            'unique_id': enhanced_state.get('unique_id', ''),
                            'messages': enhanced_state.get('messages', [])
                        }
                        
                        # Add state to inputs
                        enhanced_inputs = inputs.copy()
                        enhanced_inputs['state'] = tool_state
                        
                        self.logger.debug(f"Added state parameter to tool {self.name} from current enhanced state")
                        return enhanced_inputs
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to add state to tool {self.name}: {e}")
                        # Fallback to mock state
                        enhanced_inputs = inputs.copy()
                        enhanced_inputs['state'] = {}
                        return enhanced_inputs
                else:
                    # Fallback to mock state if no current state
                    self.logger.warning(f"No current enhanced state available for tool {self.name}, using empty state")
                    enhanced_inputs = inputs.copy()
                    enhanced_inputs['state'] = {}
                    return enhanced_inputs
        
        return inputs
    
    def _validate_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and transform inputs according to tool schema."""
        
        if not inputs:
            inputs = {}
        
        # Basic validation using args_schema if available
        if self.args_schema:
            try:
                # Use pydantic validation if available
                if hasattr(self.args_schema, 'parse_obj'):
                    validated = self.args_schema.parse_obj(inputs)
                    return validated.dict()
                elif hasattr(self.args_schema, 'model_validate'):
                    validated = self.args_schema.model_validate(inputs)
                    return validated.model_dump()
            except Exception as e:
                self.logger.warning(f"Input validation failed for {self.name}: {str(e)}")
                # Continue with unvalidated inputs
        
        return inputs
    
    def _validate_output(self, result: Any) -> Any:
        """Validate and transform tool output."""
        
        # Basic output validation
        if result is None:
            self.logger.warning(f"Tool {self.name} returned None")
            return ""
        
        # Ensure result is serializable
        if not self._is_serializable(result):
            self.logger.warning(f"Tool {self.name} returned non-serializable result")
            return str(result)
        
        return result
    
    def _is_serializable(self, obj: Any) -> bool:
        """Check if object is JSON serializable."""
        try:
            import json
            json.dumps(obj)
            return True
        except (TypeError, ValueError):
            return False
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for this tool."""
        
        avg_execution_time = (
            self.total_execution_time / self.call_count 
            if self.call_count > 0 else 0.0
        )
        
        return {
            "name": self.name,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "success_rate": (self.call_count - self.error_count) / max(1, self.call_count),
            "avg_execution_time": avg_execution_time,
            "total_execution_time": self.total_execution_time,
            "last_execution_time": self.last_execution_time,
            "last_error": self.last_error
        }
    
    def reset_stats(self) -> None:
        """Reset performance statistics."""
        self.call_count = 0
        self.error_count = 0
        self.total_execution_time = 0.0
        self.last_execution_time = None
        self.last_error = None
    
    def __str__(self) -> str:
        return f"AdaptedLangChainTool({self.name})"
    
    def __repr__(self) -> str:
        return f"AdaptedLangChainTool(name='{self.name}', calls={self.call_count}, errors={self.error_count})"


def create_langchain_adapter() -> LangChainToolAdapter:
    """
    Factory function to create a LangChain tool adapter.
    
    Returns:
        LangChainToolAdapter: Configured adapter instance
    """
    return LangChainToolAdapter()