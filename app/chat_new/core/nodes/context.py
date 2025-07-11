"""
Context Node - Context Retrieval and Enrichment for Enhanced LangGraph Chat

The ContextNode is responsible for:
1. Retrieving relevant context from various sources
2. Enriching conversation with historical data
3. User profile and preference loading
4. Knowledge base integration
5. Dynamic context window management
6. Context relevance scoring and filtering

This node ensures the conversation has all necessary context for optimal responses.
"""

import logging
import asyncio
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, AIMessage

from ..state import EnhancedState, add_error, ErrorSeverity
from app.controler.chat.store.persistence import Persist
from app.controler.chat.services.contact_service import ContactService


class ContextNode:
    """
    Context retrieval and enrichment node that gathers relevant information for conversations.
    
    Features:
    - Multi-source context retrieval (database, knowledge base, user profile)
    - Intelligent context relevance scoring
    - Dynamic context window management
    - Conversation history summarization
    - User preference integration
    - Knowledge base search integration
    - Context caching for performance
    """
    
    def __init__(self, max_context_tokens: int = 4000):
        self.logger = logging.getLogger(__name__)
        self.max_context_tokens = max_context_tokens
        
        # Initialize services
        self.db = Persist()
        self.contact_service = ContactService()
        
        # Context cache (in production, use Redis)
        self.context_cache = {}
        self.cache_ttl = timedelta(minutes=10)
        
        # Context source weights for relevance scoring
        self.source_weights = {
            "user_profile": 1.0,
            "conversation_history": 0.8,
            "knowledge_base": 0.7,
            "project_config": 0.9,
            "contact_info": 0.8,
            "tool_results": 0.6
        }
    
    def __call__(self, state: EnhancedState) -> EnhancedState:
        """
        Main context retrieval logic that enriches the conversation state.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state with enriched context
        """
        try:
            self.logger.info(f"{state['unique_id']} ContextNode: Starting context enrichment")
            
            # Check what context is needed based on routing
            context_requirements = state["routing"]["context_needed"]
            
            if not context_requirements:
                self.logger.info(f"{state['unique_id']} ContextNode: No specific context required")
                return self._add_basic_context(state)
            
            # Step 1: Retrieve user context
            state = self._enrich_user_context(state)
            
            # Step 2: Add conversation history context
            state = self._add_conversation_context(state)
            
            # Step 3: Retrieve knowledge base context
            state = self._add_knowledge_context(state, context_requirements)
            
            # Step 4: Add tool-specific context
            state = self._add_tool_context(state, context_requirements)
            
            # Step 5: Optimize context window
            state = self._optimize_context_window(state)
            
            self.logger.info(f"{state['unique_id']} ContextNode: Context enrichment completed")
            return state
            
        except Exception as e:
            self.logger.error(f"{state['unique_id']} ContextNode error: {str(e)}", exc_info=True)
            return add_error(state, e, "Context retrieval", ErrorSeverity.MEDIUM)
    
    def _add_basic_context(self, state: EnhancedState) -> EnhancedState:
        """Add basic context that's always needed."""
        
        # Add current time and project info
        user_context = state["user"]["session_metadata"]
        user_context["current_time"] = datetime.now().isoformat()
        user_context["project_name"] = state["user"]["project"].name
        user_context["source_platform"] = state["user"]["source"]
        
        return state
    
    def _enrich_user_context(self, state: EnhancedState) -> EnhancedState:
        """
        Enrich user context with profile information and contact details.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state with user context
        """
        
        try:
            user_id = state["user"]["user_id"]
            project_id = state["user"]["project"].id
            
            # Check cache first
            cache_key = f"user_context_{project_id}_{user_id}"
            cached_context = self._get_from_cache(cache_key)
            
            if cached_context:
                state["user"]["contact_info"] = cached_context.get("contact_info", {})
                state["user"]["user_preferences"] = cached_context.get("preferences", {})
                return state
            
            # Retrieve contact information
            contact_info = asyncio.run(
                self.contact_service.get_contact_by_user_id(project_id, user_id)
            )
            
            if contact_info:
                state["user"]["contact_info"] = contact_info
                
                # Extract preferences from contact info
                additional_fields = contact_info.get("additional_fields", {})
                if isinstance(additional_fields, str):
                    import json
                    try:
                        additional_fields = json.loads(additional_fields)
                    except:
                        additional_fields = {}
                
                state["user"]["user_preferences"] = additional_fields
                
                # Cache the context
                self._cache_context(cache_key, {
                    "contact_info": contact_info,
                    "preferences": additional_fields
                })
            
            return state
            
        except Exception as e:
            self.logger.error(f"Failed to enrich user context: {str(e)}")
            return state
    
    def _add_conversation_context(self, state: EnhancedState) -> EnhancedState:
        """
        Add relevant conversation history and summary.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state with conversation context
        """
        
        try:
            # Get conversation summary from persistence
            summary = self.db.get_summary(state)
            
            if summary and summary.strip():
                state["conversation"]["summary"] = summary
                
                # Add summary to session metadata for easy access
                state["user"]["session_metadata"]["conversation_summary"] = summary[:500]  # Truncate for metadata
            
            # Analyze conversation patterns
            messages = state["conversation"]["messages"]
            if len(messages) > 2:
                patterns = self._analyze_conversation_patterns(messages)
                state["user"]["session_metadata"]["conversation_patterns"] = patterns
            
            return state
            
        except Exception as e:
            self.logger.error(f"Failed to add conversation context: {str(e)}")
            return state
    
    def _add_knowledge_context(self, state: EnhancedState, requirements: List[str]) -> EnhancedState:
        """
        Add knowledge base context based on requirements.
        
        Args:
            state: Current enhanced state
            requirements: List of context requirements
            
        Returns:
            EnhancedState: Updated state with knowledge context
        """
        
        try:
            project = state["user"]["project"]
            last_message = self._get_last_user_message(state)
            
            if not last_message:
                return state
            
            knowledge_context = {}
            
            # Add FAQ context if needed
            if "faq_knowledge" in requirements and "faq_retriever" in project.enabled_tools:
                try:
                    from app.controler.chat.core.tools.faq_retriever_tool import faq_retriever
                    faq_results = faq_retriever.invoke({"query": last_message})
                    if faq_results:
                        knowledge_context["faq"] = faq_results[:200]  # Truncate
                except Exception as e:
                    self.logger.error(f"FAQ retrieval failed: {str(e)}")
            
            # Add unified search context if available
            if "unified_search" in project.enabled_tools:
                try:
                    from app.controler.chat.core.tools.unified_search_tool import unified_search_tool
                    search_results = unified_search_tool(query=last_message, state=state)
                    if search_results:
                        knowledge_context["search"] = search_results[:300]  # Truncate
                except Exception as e:
                    self.logger.error(f"Unified search failed: {str(e)}")
            
            # Add to session metadata
            if knowledge_context:
                state["user"]["session_metadata"]["knowledge_context"] = knowledge_context
            
            return state
            
        except Exception as e:
            self.logger.error(f"Failed to add knowledge context: {str(e)}")
            return state
    
    def _add_tool_context(self, state: EnhancedState, requirements: List[str]) -> EnhancedState:
        """
        Add tool-specific context based on requirements.
        
        Args:
            state: Current enhanced state
            requirements: List of context requirements
            
        Returns:
            EnhancedState: Updated state with tool context
        """
        
        try:
            tool_context = {}
            project = state["user"]["project"]
            
            # Calendar availability context
            if "calendar_availability" in requirements and "agenda_tool" in project.enabled_tools:
                try:
                    from app.controler.chat.core.tools.datetime_tool import current_datetime_tool
                    current_time = current_datetime_tool.invoke({})
                    tool_context["current_datetime"] = current_time
                except Exception as e:
                    self.logger.error(f"DateTime tool failed: {str(e)}")
            
            # Product catalog context
            if "product_catalog" in requirements and "products_search" in project.enabled_tools:
                # Add product categories or featured products
                tool_context["product_context"] = {
                    "has_product_search": True,
                    "last_search": state["tool_state"]["tool_cache"].get("last_product_search")
                }
            
            # Service capabilities context
            if "service_capabilities" in requirements:
                enabled_tools = project.enabled_tools
                tool_context["available_services"] = {
                    "can_schedule": "agenda_tool" in enabled_tools,
                    "can_search_products": "products_search" in enabled_tools,
                    "can_send_email": "email" in enabled_tools,
                    "has_faq": "faq_retriever" in enabled_tools,
                    "has_api_tools": "api" in enabled_tools
                }
            
            # Add to session metadata
            if tool_context:
                state["user"]["session_metadata"]["tool_context"] = tool_context
            
            return state
            
        except Exception as e:
            self.logger.error(f"Failed to add tool context: {str(e)}")
            return state
    
    def _optimize_context_window(self, state: EnhancedState) -> EnhancedState:
        """
        Optimize context window to fit within token limits.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state with optimized context
        """
        
        try:
            # Calculate approximate token usage
            session_metadata = state["user"]["session_metadata"]
            
            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            total_chars = 0
            context_items = []
            
            for key, value in session_metadata.items():
                if isinstance(value, str):
                    chars = len(value)
                    total_chars += chars
                    context_items.append((key, value, chars))
                elif isinstance(value, dict):
                    chars = len(str(value))
                    total_chars += chars
                    context_items.append((key, value, chars))
            
            estimated_tokens = total_chars // 4
            
            # If over limit, prioritize and truncate
            if estimated_tokens > self.max_context_tokens:
                self.logger.info(f"Context window optimization needed: {estimated_tokens} tokens")
                
                # Sort by importance (based on key names)
                priority_order = [
                    "user_contact", "conversation_summary", "tool_context",
                    "knowledge_context", "conversation_patterns"
                ]
                
                optimized_metadata = {}
                remaining_tokens = self.max_context_tokens
                
                for priority_key in priority_order:
                    for key, value, chars in context_items:
                        if key == priority_key and chars // 4 <= remaining_tokens:
                            optimized_metadata[key] = value
                            remaining_tokens -= chars // 4
                            break
                
                state["user"]["session_metadata"] = optimized_metadata
                self.logger.info(f"Context optimized to ~{self.max_context_tokens - remaining_tokens} tokens")
            
            return state
            
        except Exception as e:
            self.logger.error(f"Context optimization failed: {str(e)}")
            return state
    
    def _analyze_conversation_patterns(self, messages: List) -> Dict[str, Any]:
        """
        Analyze conversation patterns for context.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Dict with conversation patterns
        """
        
        patterns = {
            "total_messages": len(messages),
            "user_messages": 0,
            "ai_messages": 0,
            "avg_message_length": 0,
            "topics_mentioned": [],
            "has_questions": False,
            "has_requests": False
        }
        
        total_length = 0
        question_indicators = ["?", "qué", "cómo", "cuándo", "dónde", "por qué", "what", "how", "when", "where", "why"]
        request_indicators = ["quiero", "necesito", "puedes", "podrías", "can you", "could you", "i want", "i need"]
        
        for message in messages:
            if isinstance(message, HumanMessage):
                patterns["user_messages"] += 1
                content = message.content.lower()
                total_length += len(content)
                
                # Check for questions
                if any(indicator in content for indicator in question_indicators):
                    patterns["has_questions"] = True
                
                # Check for requests
                if any(indicator in content for indicator in request_indicators):
                    patterns["has_requests"] = True
                    
            elif isinstance(message, AIMessage):
                patterns["ai_messages"] += 1
                total_length += len(message.content)
        
        if len(messages) > 0:
            patterns["avg_message_length"] = total_length / len(messages)
        
        return patterns
    
    def _get_last_user_message(self, state: EnhancedState) -> Optional[str]:
        """Extract the last user message from the conversation."""
        messages = state["conversation"]["messages"]
        
        for message in reversed(messages):
            if isinstance(message, HumanMessage) and message.content:
                return message.content.strip()
        
        return None
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get data from context cache."""
        if key in self.context_cache:
            cached_data, timestamp = self.context_cache[key]
            if datetime.now() - timestamp < self.cache_ttl:
                return cached_data
            else:
                del self.context_cache[key]
        return None
    
    def _cache_context(self, key: str, data: Dict[str, Any]) -> None:
        """Cache context data with timestamp."""
        self.context_cache[key] = (data, datetime.now())
    
    def get_context_summary(self, state: EnhancedState) -> Dict[str, Any]:
        """
        Get a summary of available context for debugging.
        
        Args:
            state: Current enhanced state
            
        Returns:
            Dict with context summary
        """
        
        session_metadata = state["user"]["session_metadata"]
        
        return {
            "context_sources": list(session_metadata.keys()),
            "has_user_contact": bool(state["user"]["contact_info"]),
            "has_conversation_summary": bool(state["conversation"]["summary"]),
            "context_requirements": state["routing"]["context_needed"],
            "estimated_context_size": sum(len(str(v)) for v in session_metadata.values()),
            "cache_entries": len(self.context_cache)
        }


def create_context_node(max_context_tokens: int = 4000) -> ContextNode:
    """
    Factory function to create a ContextNode instance.
    
    Args:
        max_context_tokens: Maximum context window size in tokens
        
    Returns:
        ContextNode: Configured context node
    """
    return ContextNode(max_context_tokens)