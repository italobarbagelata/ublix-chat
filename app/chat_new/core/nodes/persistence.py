"""
Persistence Node - Enhanced Message and State Persistence

Handles saving conversation messages and state to the database with
enhanced features for the new chat system.
"""

import logging
import asyncio
from typing import Dict, Any

from ..state import EnhancedState
from ...store.persistence import schedule_persistence


class PersistenceNode:
    """
    Enhanced persistence node for saving conversation data.
    
    Features:
    - Asynchronous message persistence
    - State consistency validation
    - Error recovery and retry logic
    - Performance monitoring
    - Compatibility with original database schema
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self.persistence_stats = {
            "total_saves": 0,
            "successful_saves": 0,
            "failed_saves": 0,
            "avg_save_time": 0.0
        }
    
    def __call__(self, state: EnhancedState) -> EnhancedState:
        """
        Main persistence logic with enhanced error handling.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state with persistence metadata
        """
        try:
            self.logger.info(f"{state.get('unique_id', 'unknown')} PersistenceNode: Starting message persistence")
            
            # Validate state before persistence
            if not self._validate_state_for_persistence(state):
                self.logger.warning(f"{state.get('unique_id', 'unknown')} State validation failed, skipping persistence")
                return state
            
            # Check if there are new messages to persist
            messages = state.get("conversation", {}).get("messages", [])
            if not messages:
                self.logger.info(f"{state.get('unique_id', 'unknown')} No messages to persist")
                return state
            
            # Check for unsaved messages
            unsaved_messages = [msg for msg in messages if not getattr(msg, 'additional_kwargs', {}).get('saved', False)]
            if not unsaved_messages:
                self.logger.info(f"{state.get('unique_id', 'unknown')} All messages already saved")
                return state
            
            self.logger.info(f"{state.get('unique_id', 'unknown')} Found {len(unsaved_messages)} unsaved messages")
            
            # Schedule asynchronous persistence (non-blocking)
            self._schedule_async_persistence(state)
            
            # Update persistence metadata in state
            self._update_persistence_metadata(state)
            
            # Update statistics
            self.persistence_stats["total_saves"] += 1
            
            self.logger.info(f"{state.get('unique_id', 'unknown')} Persistence scheduled successfully")
            return state
            
        except Exception as e:
            self.logger.error(f"{state.get('unique_id', 'unknown')} PersistenceNode error: {str(e)}", exc_info=True)
            self.persistence_stats["failed_saves"] += 1
            
            # Add error to state but don't fail the conversation
            if "errors" not in state:
                state["errors"] = {
                    "error_history": [],
                    "last_error": None,
                    "error_count": 0,
                    "has_errors": False,
                    "error_severity": None
                }
            
            error_info = {
                "error_type": "PersistenceError",
                "error_message": str(e),
                "context": "Message persistence",
                "severity": "medium",
                "timestamp": "now"
            }
            
            state["errors"]["error_history"].append(error_info)
            state["errors"]["last_error"] = error_info
            state["errors"]["error_count"] += 1
            state["errors"]["has_errors"] = True
            
            return state
    
    def _validate_state_for_persistence(self, state: EnhancedState) -> bool:
        """
        Validate that state has required data for persistence.
        
        Args:
            state: Enhanced state to validate
            
        Returns:
            bool: True if state is valid for persistence
        """
        required_fields = [
            ("conversation", "conversation_id"),
            ("user", "project"),
            ("user", "user_id")
        ]
        
        for field_path in required_fields:
            current = state
            for field in field_path:
                if field not in current:
                    self.logger.warning(f"Missing required field for persistence: {'.'.join(field_path)}")
                    return False
                current = current[field]
                if current is None:
                    self.logger.warning(f"Required field is None: {'.'.join(field_path)}")
                    return False
        
        return True
    
    def _schedule_async_persistence(self, state: EnhancedState) -> None:
        """
        Schedule asynchronous persistence without blocking conversation flow.
        
        Args:
            state: Enhanced state to persist
        """
        try:
            # Use the enhanced persistence system
            schedule_persistence(state)
            
            self.logger.debug(f"{state.get('unique_id', 'unknown')} Async persistence scheduled")
            
        except Exception as e:
            self.logger.error(f"Failed to schedule async persistence: {str(e)}")
            
            # Fallback to synchronous persistence if async fails
            try:
                from ...store.persistence import persist_state_sync
                persist_state_sync(state)
                self.logger.info(f"{state.get('unique_id', 'unknown')} Fallback sync persistence completed")
                
            except Exception as sync_error:
                self.logger.error(f"Sync persistence fallback also failed: {str(sync_error)}")
                raise sync_error
    
    def _update_persistence_metadata(self, state: EnhancedState) -> None:
        """
        Update state with persistence metadata.
        
        Args:
            state: Enhanced state to update
        """
        # Mark messages as saved to prevent duplicate persistence
        messages = state.get("conversation", {}).get("messages", [])
        for message in messages:
            if not hasattr(message, 'additional_kwargs'):
                message.additional_kwargs = {}
            message.additional_kwargs["saved"] = True
        
        # Update tool state with persistence info
        if "tool_state" not in state:
            state["tool_state"] = {
                "tool_results": [],
                "last_tool_used": None,
                "tool_execution_count": 0,
                "active_tools": []
            }
        
        state["tool_state"]["last_persistence"] = "scheduled"
        
        # Update conversation metadata
        conv_data = state.get("conversation", {})
        conv_data["last_persistence_attempt"] = "now"
        conv_data["messages_count"] = len(messages)
    
    def get_persistence_stats(self) -> Dict[str, Any]:
        """Get persistence statistics."""
        
        success_rate = 0.0
        if self.persistence_stats["total_saves"] > 0:
            success_rate = (
                self.persistence_stats["successful_saves"] / 
                self.persistence_stats["total_saves"]
            )
        
        return {
            **self.persistence_stats,
            "success_rate": success_rate
        }


def create_persistence_node() -> PersistenceNode:
    """
    Factory function to create a PersistenceNode instance.
    
    Returns:
        PersistenceNode: Configured persistence node
    """
    return PersistenceNode()