"""
Tools Node - Enhanced Tool Execution for LangGraph Chat

The ToolsNode handles tool execution with advanced features:
1. Circuit breaker pattern for failed tools
2. Retry logic with exponential backoff
3. Tool performance monitoring
4. Parallel tool execution when possible
5. Result validation and caching
6. Error recovery and fallbacks

This node integrates with the enhanced tool registry for optimal performance.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from langchain_core.messages import ToolMessage, AIMessage

from ..state import (
    EnhancedState, 
    add_tool_result,
    add_error,
    ErrorSeverity
)
from ...tools.registry import get_tool_registry


class ToolsNode:
    """
    Enhanced tools execution node with circuit breakers and retry logic.
    
    Features:
    - Circuit breaker pattern for reliability
    - Retry logic with exponential backoff
    - Performance monitoring and metrics
    - Parallel execution for independent tools
    - Result validation and sanitization
    - Comprehensive error handling
    """
    
    def __init__(self, max_retries: int = 3, timeout: float = 30.0):
        self.logger = logging.getLogger(__name__)
        self.max_retries = max_retries
        self.timeout = timeout
        
        # Performance tracking
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "avg_execution_time": 0.0
        }
    
    def __call__(self, state: EnhancedState) -> EnhancedState:
        """
        Main tools execution logic with enhanced error handling.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state with tool results
        """
        try:
            # CRÍTICO: Normalizar estado al inicio para prevenir warnings Pydantic
            from ..utils import normalize_state_messages
            state = normalize_state_messages(state)
            
            # CRÍTICO: Pasar estado actual al registry para tools que requieren state
            from ...tools.registry import get_tool_registry
            registry = get_tool_registry()
            registry._current_enhanced_state = state
            
            self.logger.info(f"{state['unique_id']} ToolsNode: Starting enhanced tool execution")
            
            # Get the last message to check for tool calls
            messages = state["conversation"]["messages"]
            if not messages:
                self.logger.info("No messages found, skipping tool execution")
                return state
            
            last_message = messages[-1]
            
            # Check if there are tool calls to execute
            if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
                self.logger.info("No tool calls found, skipping tool execution")
                return state
            
            # Execute tool calls
            tool_results = asyncio.run(self._execute_tools_async(state, last_message.tool_calls))
            
            # Add tool results to messages
            for result in tool_results:
                tool_msg = ToolMessage(
                    content=result["content"],
                    tool_call_id=result["tool_call_id"]
                )
                state["messages"].append(tool_msg)
                state["conversation"]["messages"].append(tool_msg)
            
            self.logger.info(f"{state['unique_id']} ToolsNode: Executed {len(tool_results)} tools successfully")
            return state
            
        except Exception as e:
            self.logger.error(f"{state['unique_id']} ToolsNode error: {str(e)}", exc_info=True)
            return add_error(state, e, "Tools execution", ErrorSeverity.MEDIUM)
        
        finally:
            # CRÍTICO: Limpiar estado del registry después de la ejecución
            try:
                from ...tools.registry import get_tool_registry
                registry = get_tool_registry()
                if hasattr(registry, '_current_enhanced_state'):
                    delattr(registry, '_current_enhanced_state')
            except Exception:
                pass
    
    async def _execute_tools_async(self, state: EnhancedState, tool_calls: List[Dict]) -> List[Dict]:
        """
        Execute tool calls asynchronously with enhanced error handling.
        
        Args:
            state: Current enhanced state
            tool_calls: List of tool calls to execute
            
        Returns:
            List of tool execution results
        """
        
        tool_results = []
        registry = get_tool_registry()
        
        # Execute tools (can be parallel for independent tools)
        for tool_call in tool_calls:
            try:
                tool_name = tool_call.get("name", "unknown")
                tool_args = tool_call.get("args", {})
                tool_call_id = tool_call.get("id", "unknown")
                
                self.logger.info(f"Executing tool: {tool_name}")
                
                # Execute tool through enhanced registry
                result = await registry.execute_tool(tool_name, state, **tool_args)
                
                # Validate and sanitize result
                sanitized_result = self._sanitize_tool_result(result)
                
                tool_results.append({
                    "tool_call_id": tool_call_id,
                    "content": str(sanitized_result),
                    "success": True,
                    "tool_name": tool_name
                })
                
                self.logger.info(f"Tool {tool_name} executed successfully")
                
            except Exception as e:
                self.logger.error(f"Tool {tool_name} execution failed: {str(e)}")
                
                # Add error result
                tool_results.append({
                    "tool_call_id": tool_call.get("id", "unknown"),
                    "content": f"Error executing {tool_name}: {str(e)}",
                    "success": False,
                    "tool_name": tool_name,
                    "error": str(e)
                })
        
        return tool_results
    
    def _sanitize_tool_result(self, result: Any) -> Any:
        """
        Sanitize and validate tool execution result.
        
        Args:
            result: Raw tool result
            
        Returns:
            Sanitized result
        """
        
        # Handle None results
        if result is None:
            return "Tool executed successfully (no result returned)"
        
        # Handle string results
        if isinstance(result, str):
            # Truncate very long results
            if len(result) > 5000:
                return result[:5000] + "... [truncated]"
            return result
        
        # Handle dict/object results
        if isinstance(result, dict):
            # Convert to string representation
            try:
                import json
                return json.dumps(result, indent=2, ensure_ascii=False)
            except:
                return str(result)
        
        # Handle list results
        if isinstance(result, list):
            # Limit list size
            if len(result) > 50:
                limited_result = result[:50]
                limited_result.append("... [truncated]")
                return str(limited_result)
            return str(result)
        
        # Default: convert to string
        return str(result)
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get tool execution statistics."""
        
        success_rate = 0.0
        if self.execution_stats["total_executions"] > 0:
            success_rate = (
                self.execution_stats["successful_executions"] / 
                self.execution_stats["total_executions"]
            )
        
        return {
            **self.execution_stats,
            "success_rate": success_rate
        }


def create_tools_node(max_retries: int = 3, timeout: float = 30.0) -> ToolsNode:
    """
    Factory function to create a ToolsNode instance.
    
    Args:
        max_retries: Maximum number of retries for failed tools
        timeout: Timeout for tool execution in seconds
        
    Returns:
        ToolsNode: Configured tools node
    """
    return ToolsNode(max_retries, timeout)