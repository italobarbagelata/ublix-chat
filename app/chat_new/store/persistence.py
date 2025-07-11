"""
Enhanced Message Persistence for New Chat System

Integrates with the original database persistence system while providing
enhanced state management and compatibility with the new EnhancedState structure.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage

from ..core.state import EnhancedState
from ...controler.chat.store.persistence import Persist as OriginalPersist
from ...resources.postgresql import SupabaseDatabase
from ...resources.constants import MESSAGES_TABLE, AI_MESSAGE_TABLE


class EnhancedPersist:
    """
    Enhanced persistence manager for the new chat system.
    
    Features:
    - Compatibility with EnhancedState structure
    - Asynchronous persistence operations
    - Message deduplication
    - Tool metadata tracking
    - Conversation state management
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.original_persist = OriginalPersist()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="persist")
        
    async def persist_conversation_async(self, state: EnhancedState) -> None:
        """
        Asynchronously persist conversation messages to database.
        
        Args:
            state: Enhanced state containing conversation data
        """
        try:
            self.logger.info(f"{state.get('unique_id', 'unknown')} Starting async message persistence")
            
            # Convert enhanced state to format compatible with original persistence
            legacy_state = self._convert_to_legacy_state(state)
            
            # Run persistence in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self.original_persist.persist_conversation,
                legacy_state
            )
            
            self.logger.info(f"{state.get('unique_id', 'unknown')} Message persistence completed")
            
        except Exception as e:
            self.logger.error(f"Error in async persistence: {str(e)}", exc_info=True)
    
    def _convert_to_legacy_state(self, state: EnhancedState) -> Dict[str, Any]:
        """
        Convert EnhancedState to the legacy CustomState format for persistence.
        
        Args:
            state: Enhanced state to convert
            
        Returns:
            Dict compatible with original persistence system
        """
        
        # Extract data from enhanced state
        user_data = state.get("user", {})
        conversation_data = state.get("conversation", {})
        
        # Build legacy state structure
        legacy_state = {
            # Core conversation data
            "conversation_id": conversation_data.get("conversation_id", ""),
            "messages": conversation_data.get("messages", []),
            
            # User and project data
            "project": user_data.get("project"),
            "user_id": user_data.get("user_id", ""),
            "username": user_data.get("name", ""),
            
            # Source information (with defaults for API calls)
            "source_id": user_data.get("source_id", user_data.get("user_id", "")),
            "source": user_data.get("source", "api"),
            
            # Execution timing
            "exec_init": datetime.now(),
            
            # Additional context
            "unique_id": state.get("unique_id", ""),
        }
        
        self.logger.debug(f"Converted enhanced state to legacy format for conversation {legacy_state['conversation_id']}")
        
        return legacy_state
    
    async def persist_enhanced_metadata(self, state: EnhancedState) -> None:
        """
        Persist enhanced metadata specific to the new system.
        
        Args:
            state: Enhanced state with metadata to persist
        """
        try:
            # Store tool execution results
            tool_state = state.get("tool_state", {})
            tool_results = tool_state.get("tool_results", [])
            
            if tool_results:
                await self._persist_tool_metadata(state, tool_results)
            
            # Store routing decisions
            routing_data = state.get("routing", {})
            if routing_data.get("path_history"):
                await self._persist_routing_history(state, routing_data)
                
        except Exception as e:
            self.logger.error(f"Error persisting enhanced metadata: {str(e)}")
    
    async def _persist_tool_metadata(self, state: EnhancedState, tool_results: List[Dict]) -> None:
        """Persist detailed tool execution metadata."""
        try:
            database = SupabaseDatabase()
            conversation_id = state.get("conversation", {}).get("conversation_id", "")
            
            tool_metadata = []
            for tool_result in tool_results:
                metadata = {
                    "conversation_id": conversation_id,
                    "tool_name": tool_result.get("tool_name"),
                    "execution_time": tool_result.get("execution_time", 0),
                    "success": tool_result.get("success", False),
                    "timestamp": tool_result.get("timestamp"),
                    "result_size": len(str(tool_result.get("result", "")))
                }
                tool_metadata.append(metadata)
            
            if tool_metadata:
                # Use existing AI_MESSAGE_TABLE or create custom metadata table
                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda: database.batch_insert("enhanced_tool_metadata", tool_metadata)
                )
                
                self.logger.info(f"Persisted {len(tool_metadata)} tool metadata records")
                
        except Exception as e:
            self.logger.warning(f"Failed to persist tool metadata: {str(e)}")
    
    async def _persist_routing_history(self, state: EnhancedState, routing_data: Dict) -> None:
        """Persist routing decisions for analytics."""
        try:
            database = SupabaseDatabase()
            conversation_id = state.get("conversation", {}).get("conversation_id", "")
            
            routing_record = {
                "conversation_id": conversation_id,
                "path_history": routing_data.get("path_history", []),
                "current_path": routing_data.get("current_path"),
                "decision_context": routing_data.get("decision_context", {}),
                "timestamp": datetime.now().isoformat()
            }
            
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: database.insert("enhanced_routing_history", routing_record)
            )
            
            self.logger.debug(f"Persisted routing history for conversation {conversation_id}")
            
        except Exception as e:
            self.logger.warning(f"Failed to persist routing history: {str(e)}")
    
    def schedule_persistence(self, state: EnhancedState) -> None:
        """
        Schedule asynchronous persistence without blocking current execution.
        
        Args:
            state: Enhanced state to persist
        """
        try:
            # Check if we have a running event loop
            try:
                loop = asyncio.get_running_loop()
                # Create task for background persistence
                task = loop.create_task(self.persist_conversation_async(state))
                
                # Add error handling callback
                task.add_done_callback(self._handle_persistence_completion)
                
                self.logger.debug(f"Scheduled persistence task for {state.get('unique_id', 'unknown')}")
                
            except RuntimeError:
                # No running event loop, fall back to sync persistence
                self.logger.info("No event loop available, using synchronous persistence")
                self.persist_conversation_sync(state)
            
        except Exception as e:
            self.logger.error(f"Failed to schedule persistence: {str(e)}")
            
            # Final fallback to sync persistence
            try:
                self.persist_conversation_sync(state)
            except Exception as sync_error:
                self.logger.error(f"Sync persistence fallback failed: {str(sync_error)}")
    
    def _handle_persistence_completion(self, task: asyncio.Task) -> None:
        """Handle completion of persistence task."""
        try:
            if task.exception():
                self.logger.error(f"Persistence task failed: {task.exception()}")
            else:
                self.logger.debug("Persistence task completed successfully")
        except Exception as e:
            self.logger.error(f"Error handling persistence completion: {str(e)}")
    
    def persist_conversation_sync(self, state: EnhancedState) -> None:
        """
        Synchronous persistence for compatibility with original system.
        
        Args:
            state: Enhanced state to persist
        """
        try:
            legacy_state = self._convert_to_legacy_state(state)
            self.original_persist.persist_conversation(legacy_state)
            self.logger.info(f"Synchronous persistence completed for {state.get('unique_id', 'unknown')}")
            
        except Exception as e:
            self.logger.error(f"Error in synchronous persistence: {str(e)}")
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            self.executor.shutdown(wait=True)
            self.logger.info("Persistence executor cleaned up")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")


# Global instance for easy access
_enhanced_persist: Optional[EnhancedPersist] = None


def get_enhanced_persist() -> EnhancedPersist:
    """Get global enhanced persistence instance."""
    global _enhanced_persist
    if _enhanced_persist is None:
        _enhanced_persist = EnhancedPersist()
    return _enhanced_persist


async def persist_state_async(state: EnhancedState) -> None:
    """
    Convenience function for async state persistence.
    
    Args:
        state: Enhanced state to persist
    """
    persist_manager = get_enhanced_persist()
    await persist_manager.persist_conversation_async(state)


def persist_state_sync(state: EnhancedState) -> None:
    """
    Convenience function for sync state persistence.
    
    Args:
        state: Enhanced state to persist
    """
    persist_manager = get_enhanced_persist()
    persist_manager.persist_conversation_sync(state)


def schedule_persistence(state: EnhancedState) -> None:
    """
    Convenience function to schedule background persistence.
    
    Args:
        state: Enhanced state to persist
    """
    persist_manager = get_enhanced_persist()
    persist_manager.schedule_persistence(state)