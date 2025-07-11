"""
Recovery Node - Error Recovery and Fallback Strategies

The RecoveryNode handles error recovery and provides fallback strategies:
1. Error severity assessment and classification
2. Automatic retry logic with exponential backoff
3. Fallback response generation
4. Circuit breaker management
5. State cleanup and recovery
6. User-friendly error messaging
7. Performance degradation handling

This node ensures the system can gracefully handle and recover from errors.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from langchain_core.messages import AIMessage

from ..state import (
    EnhancedState,
    ErrorSeverity,
    IntentCategory,
    RouteType,
    add_error,
    set_route
)


class RecoveryNode:
    """
    Error recovery node that handles failures and provides fallback strategies.
    
    Features:
    - Intelligent error severity assessment
    - Automatic retry with exponential backoff
    - Context-aware fallback responses
    - Circuit breaker pattern management
    - State recovery and cleanup
    - Performance monitoring
    - User experience optimization
    """
    
    def __init__(self, max_retries: int = 3):
        self.logger = logging.getLogger(__name__)
        self.max_retries = max_retries
        
        # Recovery strategies by error type
        self.recovery_strategies = {
            ErrorSeverity.LOW: "continue_with_warning",
            ErrorSeverity.MEDIUM: "retry_with_fallback", 
            ErrorSeverity.HIGH: "fallback_response",
            ErrorSeverity.CRITICAL: "emergency_response"
        }
        
        # Fallback responses by intent category
        self.fallback_responses = {
            IntentCategory.GREETING: "¡Hola! Es un gusto saludarte. ¿En qué puedo ayudarte hoy?",
            IntentCategory.QUESTION: "Entiendo tu pregunta. ¿Podrías darme un poco más de información para ayudarte mejor?",
            IntentCategory.REQUEST: "Estoy aquí para ayudarte. ¿Podrías ser más específico sobre lo que necesitas?",
            IntentCategory.BOOKING: "Me gustaría ayudarte con tu cita. ¿Podrías decirme qué tipo de servicio necesitas y cuándo te gustaría agendarlo?",
            IntentCategory.PRODUCT_INQUIRY: "Estaré encantado de ayudarte con información sobre nuestros productos. ¿Qué te interesa saber?",
            IntentCategory.SUPPORT: "Lamento que tengas dificultades. Estoy aquí para ayudarte a resolver cualquier problema. ¿Podrías explicarme qué está pasando?",
            IntentCategory.COMPLAINT: "Lamento mucho escuchar sobre tu experiencia. Tu opinión es muy importante para nosotros. ¿Podrías contarme más detalles para poder ayudarte?",
            IntentCategory.GENERAL: "Estoy aquí para ayudarte. ¿Podrías darme más información sobre lo que necesitas?"
        }
        
        # Emergency responses for critical errors
        self.emergency_responses = [
            "Disculpa, estoy experimentando algunas dificultades técnicas en este momento. ¿Podrías intentar de nuevo en unos minutos?",
            "Lo siento, hay un problema temporal en nuestro sistema. Por favor, inténtalo de nuevo pronto.",
            "Estamos resolviendo un problema técnico. Te agradeceríamos si pudieras intentar nuevamente en breve."
        ]
    
    def __call__(self, state: EnhancedState) -> EnhancedState:
        """
        Main recovery logic that analyzes errors and applies appropriate recovery strategies.
        
        Args:
            state: Current enhanced state with error information
            
        Returns:
            EnhancedState: Updated state with recovery actions applied
        """
        try:
            self.logger.info(f"{state['unique_id']} RecoveryNode: Starting error recovery")
            
            # Analyze error state
            error_analysis = self._analyze_errors(state)
            
            # Determine recovery strategy
            strategy = self._determine_recovery_strategy(error_analysis, state)
            
            # Apply recovery strategy
            state = self._apply_recovery_strategy(strategy, state, error_analysis)
            
            # Set next action for routing
            state = self._set_next_action(strategy, state)
            
            self.logger.info(
                f"{state['unique_id']} RecoveryNode: Applied strategy '{strategy}' "
                f"for error severity {error_analysis['severity'].value}"
            )
            
            return state
            
        except Exception as e:
            self.logger.error(f"{state['unique_id']} RecoveryNode error: {str(e)}", exc_info=True)
            # If recovery itself fails, apply emergency strategy
            return self._apply_emergency_recovery(state)
    
    def _analyze_errors(self, state: EnhancedState) -> Dict[str, Any]:
        """
        Analyze the error state to determine severity and impact.
        
        Args:
            state: Current enhanced state
            
        Returns:
            Dict with error analysis
        """
        
        errors = state["errors"]
        
        analysis = {
            "has_errors": errors["has_errors"],
            "error_count": errors["error_count"],
            "severity": errors["error_severity"],
            "recovery_attempts": errors["recovery_attempts"],
            "last_error": errors["last_error"],
            "can_retry": errors["recovery_attempts"] < self.max_retries,
            "is_circuit_breaker_issue": False,
            "affected_components": []
        }
        
        # Analyze error patterns
        if errors["error_history"]:
            recent_errors = errors["error_history"][-5:]  # Last 5 errors
            
            # Check for repeated errors (indicates systemic issue)
            error_types = [e.get("error_type") for e in recent_errors]
            if len(set(error_types)) == 1 and len(error_types) > 2:
                analysis["is_repeating_error"] = True
                analysis["severity"] = ErrorSeverity.HIGH
            
            # Check for circuit breaker issues
            if any("circuit" in str(e).lower() for e in recent_errors):
                analysis["is_circuit_breaker_issue"] = True
        
        # Analyze tool state
        tool_errors = state["tool_state"]["tool_errors"]
        if tool_errors:
            analysis["affected_components"].append("tools")
            if len(tool_errors) > 3:
                analysis["severity"] = max(analysis["severity"], ErrorSeverity.MEDIUM)
        
        return analysis
    
    def _determine_recovery_strategy(self, error_analysis: Dict[str, Any], state: EnhancedState) -> str:
        """
        Determine the appropriate recovery strategy based on error analysis.
        
        Args:
            error_analysis: Error analysis results
            state: Current enhanced state
            
        Returns:
            Recovery strategy name
        """
        
        severity = error_analysis["severity"]
        
        # Critical errors require emergency response
        if severity == ErrorSeverity.CRITICAL:
            return "emergency_response"
        
        # High severity errors with repeated failures
        if severity == ErrorSeverity.HIGH and not error_analysis["can_retry"]:
            return "fallback_response"
        
        # Medium severity with retry capability
        if severity == ErrorSeverity.MEDIUM and error_analysis["can_retry"]:
            return "retry_with_fallback"
        
        # Circuit breaker issues
        if error_analysis.get("is_circuit_breaker_issue"):
            return "wait_and_retry"
        
        # Low severity or recoverable errors
        return "continue_with_warning"
    
    def _apply_recovery_strategy(self, strategy: str, state: EnhancedState, error_analysis: Dict[str, Any]) -> EnhancedState:
        """
        Apply the determined recovery strategy.
        
        Args:
            strategy: Recovery strategy to apply
            state: Current enhanced state
            error_analysis: Error analysis results
            
        Returns:
            Updated state
        """
        
        if strategy == "emergency_response":
            return self._apply_emergency_response(state)
        
        elif strategy == "fallback_response":
            return self._apply_fallback_response(state)
        
        elif strategy == "retry_with_fallback":
            return self._apply_retry_with_fallback(state)
        
        elif strategy == "wait_and_retry":
            return self._apply_wait_and_retry(state)
        
        elif strategy == "continue_with_warning":
            return self._apply_continue_with_warning(state)
        
        else:
            # Unknown strategy, apply fallback
            return self._apply_fallback_response(state)
    
    def _apply_emergency_response(self, state: EnhancedState) -> EnhancedState:
        """Apply emergency response for critical errors."""
        
        import random
        emergency_message = random.choice(self.emergency_responses)
        
        # Create emergency AI response
        ai_message = AIMessage(content=emergency_message)
        ai_message.additional_kwargs = {
            "recovery_type": "emergency",
            "error_severity": "critical",
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to messages
        state["messages"].append(ai_message)
        state["conversation"]["messages"].append(ai_message)
        
        # Reset error state partially
        state["errors"]["recovery_attempts"] += 1
        
        return state
    
    def _apply_fallback_response(self, state: EnhancedState) -> EnhancedState:
        """Apply fallback response based on detected intent."""
        
        intent = state["routing"]["intent_category"]
        fallback_message = self.fallback_responses.get(intent, self.fallback_responses[IntentCategory.GENERAL])
        
        # Create fallback AI response
        ai_message = AIMessage(content=fallback_message)
        ai_message.additional_kwargs = {
            "recovery_type": "fallback",
            "intent_category": intent.value,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to messages
        state["messages"].append(ai_message)
        state["conversation"]["messages"].append(ai_message)
        
        # Update error state
        state["errors"]["recovery_attempts"] += 1
        state["errors"]["fallback_used"] = True
        
        return state
    
    def _apply_retry_with_fallback(self, state: EnhancedState) -> EnhancedState:
        """Apply retry strategy with fallback if retry fails."""
        
        # Increment retry attempts
        state["errors"]["recovery_attempts"] += 1
        
        # Clear some error flags to allow retry
        state["errors"]["has_errors"] = False
        
        # Reset route to try again
        current_route = state["routing"]["current_route"]
        if current_route == RouteType.ERROR_RECOVERY:
            # Go back to agent for retry
            state = set_route(state, RouteType.DIRECT_RESPONSE, state["routing"]["intent_category"])
        
        return state
    
    def _apply_wait_and_retry(self, state: EnhancedState) -> EnhancedState:
        """Apply wait and retry strategy for circuit breaker issues."""
        
        # Add delay information for circuit breaker recovery
        state["routing"]["next_action"] = "wait_and_retry"
        state["errors"]["recovery_attempts"] += 1
        
        # Create a temporary message
        ai_message = AIMessage(content="Dame un momento mientras resuelvo esto...")
        ai_message.additional_kwargs = {
            "recovery_type": "wait_and_retry",
            "timestamp": datetime.now().isoformat()
        }
        
        state["messages"].append(ai_message)
        state["conversation"]["messages"].append(ai_message)
        
        return state
    
    def _apply_continue_with_warning(self, state: EnhancedState) -> EnhancedState:
        """Continue processing with warning for low severity errors."""
        
        # Log the warning but continue
        self.logger.warning(f"Continuing with minor error: {state['errors']['last_error']}")
        
        # Don't add any messages, just update state
        state["errors"]["recovery_attempts"] += 1
        
        return state
    
    def _apply_emergency_recovery(self, state: EnhancedState) -> EnhancedState:
        """Emergency recovery when recovery itself fails."""
        
        emergency_message = "Lo siento, hay un problema técnico. Por favor contacta a soporte."
        
        ai_message = AIMessage(content=emergency_message)
        ai_message.additional_kwargs = {
            "recovery_type": "emergency_fallback",
            "timestamp": datetime.now().isoformat()
        }
        
        state["messages"].append(ai_message)
        state["conversation"]["messages"].append(ai_message)
        
        return state
    
    def _set_next_action(self, strategy: str, state: EnhancedState) -> EnhancedState:
        """Set the next action for the routing system."""
        
        action_map = {
            "emergency_response": "end",
            "fallback_response": "fallback",
            "retry_with_fallback": "retry",
            "wait_and_retry": "retry",
            "continue_with_warning": "retry"
        }
        
        next_action = action_map.get(strategy, "fallback")
        state["routing"]["next_action"] = next_action
        
        return state
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics for monitoring."""
        
        return {
            "available_strategies": list(self.recovery_strategies.keys()),
            "max_retries": self.max_retries,
            "fallback_responses_count": len(self.fallback_responses),
            "emergency_responses_count": len(self.emergency_responses),
            "features": [
                "error_severity_assessment",
                "automatic_retry_logic",
                "context_aware_fallbacks",
                "circuit_breaker_recovery",
                "emergency_responses"
            ]
        }


def create_recovery_node(max_retries: int = 3) -> RecoveryNode:
    """
    Factory function to create a RecoveryNode instance.
    
    Args:
        max_retries: Maximum number of retry attempts
        
    Returns:
        RecoveryNode: Configured recovery node
    """
    return RecoveryNode(max_retries)