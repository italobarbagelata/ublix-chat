"""
Integration Utilities for Enhanced LangGraph Chat System

Provides utilities to integrate the enhanced system with the existing codebase:
1. Migration from old Graph to EnhancedGraph
2. Backwards compatibility layers
3. Configuration adapters
4. Performance comparison tools
5. A/B testing utilities

This allows for smooth transition and parallel operation during migration.
"""

import logging
from typing import Dict, Any, Optional, Union
import asyncio

from ..core.graph import EnhancedGraph
from ..core.state import create_initial_enhanced_state
from ..tools.registry import get_tool_registry, ToolMetadata, ToolType
from ..tools.adapters.langchain import create_langchain_adapter

# Import existing system components
from app.controler.chat.core.graph import Graph as LegacyGraph
from app.controler.chat.classes.chat_state import ChatState


async def create_enhanced_graph_from_existing(
    project_id: str,
    user_id: str,
    name: str,
    number_phone_agent: str,
    source: str,
    source_id: str,
    unique_id: str,
    project: Any
) -> EnhancedGraph:
    """
    Create an EnhancedGraph instance using the same parameters as the legacy Graph.
    
    This function provides a drop-in replacement for the legacy Graph.create() method
    while using the enhanced architecture underneath.
    
    Args:
        project_id: Project identifier
        user_id: User identifier
        name: User display name
        number_phone_agent: Phone number (legacy parameter, not used in enhanced version)
        source: Source platform
        source_id: Source-specific identifier
        unique_id: Unique conversation identifier
        project: Project configuration object
        
    Returns:
        EnhancedGraph: Configured enhanced graph instance
    """
    
    logger = logging.getLogger(__name__)
    logger.info(f"Creating EnhancedGraph for legacy compatibility: {project_id}/{user_id}")
    
    try:
        # Create enhanced graph with mapped parameters
        enhanced_graph = await EnhancedGraph.create(
            project_id=project_id,
            user_id=user_id,
            username=name,
            source=source,
            source_id=source_id,
            project=project,
            unique_id=unique_id
        )
        
        logger.info(f"Successfully created EnhancedGraph for {project_id}/{user_id}")
        return enhanced_graph
        
    except Exception as e:
        logger.error(f"Failed to create EnhancedGraph: {str(e)}")
        raise


class LegacyCompatibilityWrapper:
    """
    Wrapper that provides legacy Graph interface while using EnhancedGraph underneath.
    
    This allows existing code to use the enhanced system without modification.
    """
    
    def __init__(self, enhanced_graph: EnhancedGraph):
        self.enhanced_graph = enhanced_graph
        self.logger = logging.getLogger(__name__)
        
        # Legacy properties
        self.state = ChatState(enhanced_graph.project_id, enhanced_graph.user_id)
        self.project_id = enhanced_graph.project_id
        self.user_id = enhanced_graph.user_id
        self.name = enhanced_graph.username
        self.source = enhanced_graph.source
        self.source_id = enhanced_graph.source_id
        self.unique_id = enhanced_graph.unique_id
        self.project = enhanced_graph.project
    
    async def execute(self, message: str, debug: bool = False) -> Dict[str, Any]:
        """
        Execute method compatible with legacy Graph interface.
        
        Args:
            message: User message to process
            debug: Debug mode (legacy parameter, not used)
            
        Returns:
            Dict with response in legacy format
        """
        try:
            # Execute using enhanced graph
            result = await self.enhanced_graph.execute(message)
            
            # Convert to legacy format
            legacy_response = {
                'response': result['response'],
                'message_id': result['message_id'],
                'user_id': result['user_id'],
                'processing_time': result['processing_time']
            }
            
            return legacy_response
            
        except Exception as e:
            self.logger.error(f"Legacy execute wrapper failed: {str(e)}")
            raise
    
    async def execute_with_immediate_response(self, message: str, background_tasks: Any) -> Dict[str, Any]:
        """
        Legacy execute_with_immediate_response compatibility method.
        
        Args:
            message: User message to process
            background_tasks: Background tasks handler
            
        Returns:
            Dict with response in legacy format
        """
        try:
            # Execute using enhanced graph
            result = await self.enhanced_graph.execute(message, background_tasks)
            
            # Add immediate response metadata for legacy compatibility
            result['immediate_response'] = "⏳ Procesando tu mensaje..."
            result['query_type'] = "enhanced"
            result['messages_processed'] = 1
            result['includes_queued_messages'] = False
            
            return result
            
        except Exception as e:
            self.logger.error(f"Legacy execute_with_immediate_response wrapper failed: {str(e)}")
            raise
    
    async def execute_stream(self, message: str, background_tasks: Any):
        """
        Legacy execute_stream compatibility method.
        
        Args:
            message: User message to process
            background_tasks: Background tasks handler
            
        Yields:
            Dict with streaming response chunks in legacy format
        """
        try:
            # Stream using enhanced graph
            async for chunk in self.enhanced_graph.execute_stream(message, background_tasks):
                # Convert enhanced events to legacy format
                if chunk.get("type") == "content_chunk":
                    legacy_chunk = {
                        "type": "content_chunk",
                        "content": chunk["content"],
                        "message_id": chunk.get("message_id"),
                        "is_complete": chunk["is_complete"]
                    }
                    yield legacy_chunk
                
                elif chunk.get("type") == "completion":
                    legacy_chunk = {
                        "type": "completion",
                        "response": chunk.get("response", ""),
                        "is_complete": True,
                        "status": "finished",
                        "message_id": chunk.get("message_id")
                    }
                    yield legacy_chunk
                
                elif chunk.get("type") == "error":
                    legacy_chunk = {
                        "type": "error",
                        "error": chunk["error"],
                        "is_complete": True
                    }
                    yield legacy_chunk
                
                # Pass through other chunk types
                else:
                    yield chunk
            
        except Exception as e:
            self.logger.error(f"Legacy execute_stream wrapper failed: {str(e)}")
            yield {
                "type": "error",
                "error": str(e),
                "is_complete": True
            }


async def migrate_existing_tools():
    """
    Migrate tools from the existing system to the enhanced tool registry.
    
    This function discovers and registers existing tools with the enhanced system.
    """
    
    logger = logging.getLogger(__name__)
    logger.info("Starting tool migration from existing system")
    
    try:
        # Get the enhanced tool registry
        registry = get_tool_registry()
        
        # Register LangChain adapter
        from ..tools.adapters.langchain import LangChainToolAdapter
        registry.register_adapter(ToolType.LANGCHAIN, LangChainToolAdapter)
        
        # Import and register core tools
        try:
            from app.controler.chat.core.tools.contact_tool import SaveContactTool
            from app.controler.chat.core.tools.datetime_tool import current_datetime_tool, week_info_tool
            from app.controler.chat.core.tools.chile_holidays_tool import check_chile_holiday_tool, next_chile_holidays_tool
            
            # Register core tools
            sample_project_id = "migration_test"
            sample_user_id = "migration_user"
            
            contact_tool = SaveContactTool(sample_project_id, sample_user_id)
            
            tools_to_register = [
                (current_datetime_tool, "current_datetime_tool", "Get current date and time"),
                (week_info_tool, "week_info_tool", "Get week information"),
                (check_chile_holiday_tool, "check_chile_holiday_tool", "Check if date is Chilean holiday"),
                (next_chile_holidays_tool, "next_chile_holidays_tool", "Get next Chilean holidays"),
                (contact_tool, "save_contact_tool", "Save and manage contact information")
            ]
            
            for tool, name, description in tools_to_register:
                metadata = ToolMetadata(
                    name=name,
                    tool_type=ToolType.LANGCHAIN,
                    description=description,
                    tags=["core", "migrated"]
                )
                
                success = registry.register_tool(tool, metadata)
                if success:
                    logger.info(f"Successfully migrated tool: {name}")
                else:
                    logger.warning(f"Failed to migrate tool: {name}")
            
        except ImportError as e:
            logger.warning(f"Could not import some tools for migration: {str(e)}")
        
        logger.info("Tool migration completed")
        
    except Exception as e:
        logger.error(f"Tool migration failed: {str(e)}")


class PerformanceComparator:
    """
    Utility to compare performance between legacy and enhanced systems.
    
    Useful for A/B testing and migration validation.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.legacy_metrics = []
        self.enhanced_metrics = []
    
    async def compare_execution(
        self,
        message: str,
        legacy_graph: LegacyGraph,
        enhanced_graph: EnhancedGraph
    ) -> Dict[str, Any]:
        """
        Compare execution between legacy and enhanced systems.
        
        Args:
            message: Test message
            legacy_graph: Legacy graph instance
            enhanced_graph: Enhanced graph instance
            
        Returns:
            Dict with comparison results
        """
        
        comparison_result = {
            "message": message,
            "legacy_result": None,
            "enhanced_result": None,
            "performance_comparison": None,
            "feature_comparison": None
        }
        
        try:
            # Execute with legacy system
            import time
            start_time = time.time()
            legacy_result = await legacy_graph.execute(message)
            legacy_time = time.time() - start_time
            
            comparison_result["legacy_result"] = {
                **legacy_result,
                "execution_time": legacy_time
            }
            
        except Exception as e:
            self.logger.error(f"Legacy execution failed: {str(e)}")
            comparison_result["legacy_result"] = {"error": str(e)}
        
        try:
            # Execute with enhanced system
            start_time = time.time()
            enhanced_result = await enhanced_graph.execute(message)
            enhanced_time = time.time() - start_time
            
            comparison_result["enhanced_result"] = {
                **enhanced_result,
                "execution_time": enhanced_time
            }
            
        except Exception as e:
            self.logger.error(f"Enhanced execution failed: {str(e)}")
            comparison_result["enhanced_result"] = {"error": str(e)}
        
        # Compare performance
        if (comparison_result["legacy_result"] and 
            comparison_result["enhanced_result"] and
            "error" not in comparison_result["legacy_result"] and
            "error" not in comparison_result["enhanced_result"]):
            
            legacy_time = comparison_result["legacy_result"]["execution_time"]
            enhanced_time = comparison_result["enhanced_result"]["execution_time"]
            
            comparison_result["performance_comparison"] = {
                "speed_improvement": ((legacy_time - enhanced_time) / legacy_time) * 100,
                "legacy_time": legacy_time,
                "enhanced_time": enhanced_time,
                "faster_system": "enhanced" if enhanced_time < legacy_time else "legacy"
            }
            
            # Compare features
            enhanced_features = enhanced_result.keys() - legacy_result.keys()
            comparison_result["feature_comparison"] = {
                "new_features": list(enhanced_features),
                "enhanced_feature_count": len(enhanced_features)
            }
        
        return comparison_result
    
    def generate_migration_report(self) -> Dict[str, Any]:
        """Generate a comprehensive migration report."""
        
        return {
            "total_comparisons": len(self.legacy_metrics) + len(self.enhanced_metrics),
            "legacy_average_time": sum(self.legacy_metrics) / len(self.legacy_metrics) if self.legacy_metrics else 0,
            "enhanced_average_time": sum(self.enhanced_metrics) / len(self.enhanced_metrics) if self.enhanced_metrics else 0,
            "recommendation": self._get_migration_recommendation()
        }
    
    def _get_migration_recommendation(self) -> str:
        """Get migration recommendation based on performance data."""
        
        if not self.legacy_metrics or not self.enhanced_metrics:
            return "Insufficient data for recommendation"
        
        legacy_avg = sum(self.legacy_metrics) / len(self.legacy_metrics)
        enhanced_avg = sum(self.enhanced_metrics) / len(self.enhanced_metrics)
        
        if enhanced_avg < legacy_avg * 0.8:  # 20% improvement
            return "Strong recommendation: Migrate to enhanced system"
        elif enhanced_avg < legacy_avg:
            return "Moderate recommendation: Enhanced system shows improvement"
        else:
            return "Caution: Legacy system currently performs better"


# Factory function for easy integration
async def create_legacy_compatible_graph(*args, **kwargs) -> LegacyCompatibilityWrapper:
    """
    Create a legacy-compatible graph using the enhanced system.
    
    This function can be used as a drop-in replacement for Graph.create()
    """
    
    enhanced_graph = await create_enhanced_graph_from_existing(*args, **kwargs)
    return LegacyCompatibilityWrapper(enhanced_graph)