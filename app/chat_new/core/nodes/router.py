"""
Router Node - Intelligence Routing for Enhanced LangGraph Chat

The RouterNode is responsible for:
1. Intent classification from user messages
2. Route determination based on intent and context
3. Confidence scoring for routing decisions
4. Alternative route suggestions
5. Context requirement identification

This node uses lightweight LLM calls for fast decision making.
"""

import logging
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from app.controler.chat.core.llm_adapter import LLMAdapter

from ..state import (
    EnhancedState, 
    RouteType, 
    IntentCategory, 
    set_route,
    update_conversation_state
)


class RouterNode:
    """
    Intelligent routing node that classifies user intents and determines conversation flow.
    
    Features:
    - Fast intent classification using lightweight models
    - Multi-layered routing (rule-based + ML-based)
    - Confidence scoring and alternative route suggestions
    - Context-aware routing based on conversation history
    - Fallback strategies for ambiguous cases
    """
    
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name
        self.model = LLMAdapter.get_llm(model_name, 0)
        
        # Keyword patterns for fast rule-based routing
        self.keyword_patterns = {
            IntentCategory.GREETING: [
                r'\b(hola|buenos días|buenas tardes|buenas noches|saludos|hey)\b',
                r'\b(hello|hi|good morning|good afternoon|good evening)\b'
            ],
            IntentCategory.BOOKING: [
                r'\b(agendar|reservar|cita|horario|agenda|disponible)\b',
                r'\b(book|schedule|appointment|available|reserve)\b'
            ],
            IntentCategory.PRODUCT_INQUIRY: [
                r'\b(producto|precio|comprar|catálogo|tienda|oferta)\b',
                r'\b(product|price|buy|catalog|store|offer|shopping)\b'
            ],
            IntentCategory.SUPPORT: [
                r'\b(ayuda|soporte|problema|error|no funciona)\b',
                r'\b(help|support|problem|error|not working|issue)\b'
            ],
            IntentCategory.COMPLAINT: [
                r'\b(queja|reclamo|molesto|insatisfecho|mal servicio)\b',
                r'\b(complaint|unhappy|unsatisfied|bad service|disappointed)\b'
            ]
        }
        
        # Tool requirement mapping
        self.tool_requirements = {
            IntentCategory.BOOKING: ['agenda_tool', 'calendar', 'contact'],
            IntentCategory.PRODUCT_INQUIRY: ['products_search', 'unified_search'],
            IntentCategory.SUPPORT: ['unified_search', 'faq_retriever'],
            IntentCategory.REQUEST: ['contact', 'email']
        }
        
        # Initialize classification prompt
        self.classification_prompt = self._create_classification_prompt()
    
    def __call__(self, state: EnhancedState) -> EnhancedState:
        """
        Main routing logic that processes the current state and determines the next route.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state with routing information
        """
        try:
            # CRÍTICO: Normalizar estado al inicio para prevenir warnings Pydantic
            from ..utils import normalize_state_messages
            state = normalize_state_messages(state)
            
            self.logger.info(f"{state['unique_id']} RouterNode: Starting intelligent routing")
            
            # Get the last user message
            last_message = self._get_last_user_message(state)
            if not last_message:
                self.logger.warning(f"{state['unique_id']} RouterNode: No user message found")
                return self._set_default_route(state)
            
            # Step 1: Fast rule-based classification
            rule_based_intent, rule_confidence = self._classify_with_rules(last_message)
            
            # Step 2: LLM-based classification for higher accuracy
            llm_intent, llm_confidence = self._classify_with_llm(last_message, state)
            
            # Step 3: Combine classifications with confidence weighting
            final_intent, final_confidence = self._combine_classifications(
                rule_based_intent, rule_confidence,
                llm_intent, llm_confidence
            )
            
            # Step 4: Determine route based on intent and available tools
            route = self._determine_route(final_intent, state)
            
            # Step 5: Update state with routing decision
            state = set_route(state, route, final_intent, final_confidence)
            
            # Step 6: Add context requirements
            state = self._add_context_requirements(state, final_intent)
            
            # Step 7: Set alternative routes
            state = self._set_alternative_routes(state, final_intent)
            
            self.logger.info(
                f"{state['unique_id']} RouterNode: Routed to {route.value} "
                f"(intent: {final_intent.value}, confidence: {final_confidence:.2f})"
            )
            
            return state
            
        except Exception as e:
            self.logger.error(f"{state['unique_id']} RouterNode error: {str(e)}", exc_info=True)
            return self._set_error_route(state, e)
    
    def _get_last_user_message(self, state: EnhancedState) -> Optional[str]:
        """Extract the last user message from the conversation."""
        messages = state["conversation"]["messages"]
        
        for message in reversed(messages):
            if isinstance(message, HumanMessage) and message.content:
                return message.content.strip()
        
        return None
    
    def _classify_with_rules(self, message: str) -> Tuple[IntentCategory, float]:
        """
        Fast rule-based intent classification using keyword patterns.
        
        Args:
            message: User message to classify
            
        Returns:
            Tuple of (intent_category, confidence_score)
        """
        message_lower = message.lower()
        
        # Check each intent category for pattern matches
        for intent, patterns in self.keyword_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    # Higher confidence for exact matches
                    confidence = 0.8 if len(re.findall(pattern, message_lower)) > 1 else 0.6
                    return intent, confidence
        
        # Default to general with low confidence
        return IntentCategory.GENERAL, 0.3
    
    def _classify_with_llm(self, message: str, state: EnhancedState) -> Tuple[IntentCategory, float]:
        """
        LLM-based intent classification for higher accuracy on complex cases.
        
        Args:
            message: User message to classify
            state: Current conversation state for context
            
        Returns:
            Tuple of (intent_category, confidence_score)
        """
        try:
            # Build context from conversation history
            context = self._build_conversation_context(state)
            
            # Create classification request
            messages = [
                {"role": "system", "content": self.classification_prompt},
                {"role": "user", "content": f"Context: {context}\n\nMessage to classify: {message}"}
            ]
            
            # Get classification from LLM
            response = self.model.invoke(messages)
            
            # Parse response
            intent, confidence = self._parse_classification_response(response.content)
            
            return intent, confidence
            
        except Exception as e:
            self.logger.error(f"LLM classification failed: {str(e)}")
            return IntentCategory.GENERAL, 0.2
    
    def _combine_classifications(
        self, 
        rule_intent: IntentCategory, 
        rule_confidence: float,
        llm_intent: IntentCategory, 
        llm_confidence: float
    ) -> Tuple[IntentCategory, float]:
        """
        Combine rule-based and LLM-based classifications using confidence weighting.
        
        Args:
            rule_intent: Intent from rule-based classification
            rule_confidence: Confidence from rule-based classification
            llm_intent: Intent from LLM-based classification
            llm_confidence: Confidence from LLM-based classification
            
        Returns:
            Tuple of (final_intent, final_confidence)
        """
        
        # If both agree, use higher confidence
        if rule_intent == llm_intent:
            return rule_intent, max(rule_confidence, llm_confidence)
        
        # If they disagree, use the one with higher confidence
        if rule_confidence > llm_confidence:
            return rule_intent, rule_confidence
        else:
            return llm_intent, llm_confidence
    
    def _determine_route(self, intent: IntentCategory, state: EnhancedState) -> RouteType:
        """
        Determine the appropriate route based on intent and available tools.
        
        Args:
            intent: Classified intent category
            state: Current enhanced state
            
        Returns:
            RouteType: Determined route
        """
        
        # Check if required tools are available
        required_tools = self.tool_requirements.get(intent, [])
        available_tools = state["tool_state"]["available_tools"]
        
        has_required_tools = all(
            any(req in tool for tool in available_tools) 
            for req in required_tools
        )
        
        # Route determination logic
        if intent == IntentCategory.GREETING:
            return RouteType.DIRECT_RESPONSE
        
        elif intent in [IntentCategory.BOOKING, IntentCategory.PRODUCT_INQUIRY] and has_required_tools:
            return RouteType.TOOL_EXECUTION
        
        elif intent in [IntentCategory.SUPPORT, IntentCategory.COMPLAINT]:
            return RouteType.COMPLEX_WORKFLOW if has_required_tools else RouteType.DIRECT_RESPONSE
        
        elif intent == IntentCategory.REQUEST and has_required_tools:
            return RouteType.TOOL_EXECUTION
        
        elif required_tools and not has_required_tools:
            # Need tools but don't have them - try to get context
            return RouteType.CONTEXT_RETRIEVAL
        
        else:
            return RouteType.DIRECT_RESPONSE
    
    def _add_context_requirements(self, state: EnhancedState, intent: IntentCategory) -> EnhancedState:
        """Add context requirements based on intent."""
        
        context_map = {
            IntentCategory.BOOKING: ["user_contact", "calendar_availability"],
            IntentCategory.PRODUCT_INQUIRY: ["product_catalog", "user_preferences"],
            IntentCategory.SUPPORT: ["faq_knowledge", "support_history"],
            IntentCategory.REQUEST: ["user_contact", "service_capabilities"]
        }
        
        required_context = context_map.get(intent, [])
        state["routing"]["context_needed"] = required_context
        
        return state
    
    def _set_alternative_routes(self, state: EnhancedState, intent: IntentCategory) -> EnhancedState:
        """Set alternative routes in case primary route fails."""
        
        current_route = state["routing"]["current_route"]
        alternatives = []
        
        if current_route == RouteType.TOOL_EXECUTION:
            alternatives = [RouteType.DIRECT_RESPONSE, RouteType.CONTEXT_RETRIEVAL]
        elif current_route == RouteType.COMPLEX_WORKFLOW:
            alternatives = [RouteType.TOOL_EXECUTION, RouteType.DIRECT_RESPONSE]
        elif current_route == RouteType.CONTEXT_RETRIEVAL:
            alternatives = [RouteType.DIRECT_RESPONSE]
        
        state["routing"]["alternative_routes"] = alternatives
        
        return state
    
    def _build_conversation_context(self, state: EnhancedState) -> str:
        """Build conversation context for LLM classification."""
        
        messages = state["conversation"]["messages"]
        context_parts = []
        
        # Add recent messages (last 3-4 exchanges)
        recent_messages = messages[-8:] if len(messages) > 8 else messages
        
        for msg in recent_messages:
            if isinstance(msg, HumanMessage):
                context_parts.append(f"User: {msg.content[:100]}")
            elif isinstance(msg, AIMessage):
                context_parts.append(f"Assistant: {msg.content[:100]}")
        
        # Add user context
        user_info = state["user"]
        context_parts.append(f"Source: {user_info['source']}")
        
        if user_info["contact_info"]:
            context_parts.append("User has provided contact info")
        
        return " | ".join(context_parts) if context_parts else "No previous context"
    
    def _create_classification_prompt(self) -> str:
        """Create the prompt for LLM-based intent classification."""
        
        return """You are an expert intent classifier for a conversational AI system.

Your task is to classify user messages into one of these categories:

GREETING: Basic greetings and conversation starters
- Examples: "Hola", "Buenos días", "Hi there"

QUESTION: Information requests and general questions  
- Examples: "¿Qué servicios ofrecen?", "How does this work?"

REQUEST: Specific action requests
- Examples: "Envíame información", "I need help with..."

BOOKING: Appointment or reservation requests
- Examples: "Quiero agendar una cita", "Book an appointment"

PRODUCT_INQUIRY: Product or service inquiries
- Examples: "¿Cuánto cuesta?", "What products do you have?"

SUPPORT: Technical support or help requests
- Examples: "Tengo un problema", "This isn't working"

COMPLAINT: Complaints or negative feedback
- Examples: "Estoy molesto", "Bad service"

GENERAL: Everything else

Respond with ONLY the category name and a confidence score (0.0-1.0), separated by a pipe.
Example: "BOOKING|0.85"

Consider the conversation context when classifying."""
    
    def _parse_classification_response(self, response: str) -> Tuple[IntentCategory, float]:
        """Parse LLM classification response."""
        
        try:
            parts = response.strip().split('|')
            if len(parts) != 2:
                return IntentCategory.GENERAL, 0.3
            
            category_name = parts[0].strip().upper()
            confidence = float(parts[1].strip())
            
            # Map category name to enum
            category_map = {
                "GREETING": IntentCategory.GREETING,
                "QUESTION": IntentCategory.QUESTION, 
                "REQUEST": IntentCategory.REQUEST,
                "BOOKING": IntentCategory.BOOKING,
                "PRODUCT_INQUIRY": IntentCategory.PRODUCT_INQUIRY,
                "SUPPORT": IntentCategory.SUPPORT,
                "COMPLAINT": IntentCategory.COMPLAINT,
                "GENERAL": IntentCategory.GENERAL
            }
            
            intent = category_map.get(category_name, IntentCategory.GENERAL)
            confidence = max(0.0, min(1.0, confidence))  # Clamp between 0-1
            
            return intent, confidence
            
        except Exception as e:
            self.logger.error(f"Failed to parse classification response: {response}")
            return IntentCategory.GENERAL, 0.2
    
    def _set_default_route(self, state: EnhancedState) -> EnhancedState:
        """Set default route when no clear routing can be determined."""
        return set_route(state, RouteType.DIRECT_RESPONSE, IntentCategory.GENERAL, 0.5)
    
    def _set_error_route(self, state: EnhancedState, error: Exception) -> EnhancedState:
        """Set error recovery route when routing fails."""
        self.logger.error(f"Router error: {str(error)}")
        return set_route(state, RouteType.ERROR_RECOVERY, IntentCategory.GENERAL, 0.0)


def create_router_node(model_name: str = "gpt-3.5-turbo") -> RouterNode:
    """
    Factory function to create a RouterNode instance.
    
    Args:
        model_name: LLM model to use for classification
        
    Returns:
        RouterNode: Configured router node
    """
    return RouterNode(model_name)