"""
Routing Logic for Enhanced LangGraph Chat System

Provides sophisticated routing decisions between nodes based on:
- State health and error conditions
- Route types and requirements
- Tool availability and execution status
- Context completeness and quality
- Recovery strategies and fallback options

Each routing function analyzes the current state and determines
the optimal next step in the conversation flow.
"""

import logging
from typing import Literal, Dict, Any, Callable

from ..state import (
    EnhancedState,
    RouteType,
    IntentCategory,
    ErrorSeverity,
    is_state_healthy
)


logger = logging.getLogger(__name__)


def post_validation_routing(state: EnhancedState) -> Literal["route", "recovery", "end"]:
    """
    Determine next step after validation.
    
    Args:
        state: Current enhanced state
        
    Returns:
        Next node to execute
    """
    
    # Check for critical validation errors
    errors = state["errors"]
    
    if errors["has_errors"]:
        if errors["error_severity"] == ErrorSeverity.CRITICAL:
            logger.warning(f"{state['unique_id']} Critical validation error, ending conversation")
            return "end"
        elif errors["error_severity"] == ErrorSeverity.HIGH:
            logger.warning(f"{state['unique_id']} High severity validation error, going to recovery")
            return "recovery"
    
    # Check if state is healthy enough to continue
    if not is_state_healthy(state):
        logger.warning(f"{state['unique_id']} State unhealthy after validation, going to recovery")
        return "recovery"
    
    # Normal flow - proceed to routing
    logger.info(f"{state['unique_id']} Validation passed, proceeding to routing")
    return "route"


def post_routing_routing(state: EnhancedState) -> Literal["context", "direct", "recovery"]:
    """
    Determine next step after routing/intent classification.
    
    Args:
        state: Current enhanced state
        
    Returns:
        Next node to execute
    """
    
    routing_info = state["routing"]
    route_type = routing_info["current_route"]
    confidence = routing_info["confidence_score"]
    
    # Check if routing failed or has low confidence
    if confidence < 0.3:
        logger.warning(f"{state['unique_id']} Low routing confidence ({confidence:.2f}), going to recovery")
        return "recovery"
    
    # Check if context is needed
    context_needed = routing_info["context_needed"]
    
    if context_needed or route_type in [RouteType.CONTEXT_RETRIEVAL, RouteType.COMPLEX_WORKFLOW]:
        logger.info(f"{state['unique_id']} Context needed, going to context enrichment")
        return "context"
    
    # For simple direct responses, skip context enrichment
    if route_type == RouteType.DIRECT_RESPONSE and confidence > 0.8:
        logger.info(f"{state['unique_id']} High confidence direct response, skipping context")
        return "direct"
    
    # Default to context enrichment for better responses
    logger.info(f"{state['unique_id']} Going to context enrichment for route {route_type.value}")
    return "context"


def post_agent_routing(state: EnhancedState) -> Literal["tools", "format", "recovery"]:
    """
    Determine next step after agent processing.
    
    Args:
        state: Current enhanced state
        
    Returns:
        Next node to execute
    """
    
    # Check for agent processing errors
    errors = state["errors"]
    if errors["has_errors"] and errors["error_severity"] in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
        logger.warning(f"{state['unique_id']} Agent processing error, going to recovery")
        return "recovery"
    
    # Check if the agent wants to use tools
    messages = state["conversation"]["messages"]
    
    if messages:
        last_message = messages[-1]
        
        # Check if there are tool calls
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            logger.info(f"{state['unique_id']} Tool calls detected, executing tools")
            return "tools"
    
    # Check route type to see if tools were expected
    route_type = state["routing"]["current_route"]
    
    if route_type == RouteType.TOOL_EXECUTION:
        # Tools were expected but not called - might be an issue
        tool_state = state["tool_state"]
        if tool_state["tool_execution_count"] == 0:
            logger.warning(f"{state['unique_id']} Tool execution expected but no tools used")
            # Continue to formatting anyway, agent might have handled it differently
    
    # No tools needed, proceed to formatting
    logger.info(f"{state['unique_id']} No tools needed, proceeding to formatting")
    return "format"


def post_recovery_routing(state: EnhancedState) -> Literal["retry", "fallback", "end"]:
    """
    Determine next step after error recovery.
    
    Args:
        state: Current enhanced state
        
    Returns:
        Next node to execute
    """
    
    # Check what the recovery node decided
    next_action = state["routing"].get("next_action")
    
    if next_action == "end":
        logger.info(f"{state['unique_id']} Recovery decided to end conversation")
        return "end"
    elif next_action == "retry":
        logger.info(f"{state['unique_id']} Recovery decided to retry with agent")
        return "retry"
    elif next_action == "fallback":
        logger.info(f"{state['unique_id']} Recovery decided to use fallback response")
        return "fallback"
    
    # Default decision based on error state
    errors = state["errors"]
    
    if errors["error_severity"] == ErrorSeverity.CRITICAL:
        return "end"
    elif errors["recovery_attempts"] >= 3:
        return "fallback"
    else:
        return "retry"


def should_use_tools(state: EnhancedState) -> bool:
    """
    Helper function to determine if tools should be used.
    
    Args:
        state: Current enhanced state
        
    Returns:
        bool: True if tools should be used
    """
    
    route_type = state["routing"]["current_route"]
    intent = state["routing"]["intent_category"]
    
    # Tools needed for these routes
    tool_routes = [RouteType.TOOL_EXECUTION, RouteType.COMPLEX_WORKFLOW]
    
    # Tools useful for these intents
    tool_intents = [
        IntentCategory.BOOKING,
        IntentCategory.PRODUCT_INQUIRY,
        IntentCategory.SUPPORT
    ]
    
    return route_type in tool_routes or intent in tool_intents


def get_confidence_threshold(route_type: RouteType) -> float:
    """
    Get confidence threshold for different route types.
    
    Args:
        route_type: Type of route
        
    Returns:
        float: Confidence threshold
    """
    
    thresholds = {
        RouteType.DIRECT_RESPONSE: 0.7,
        RouteType.TOOL_EXECUTION: 0.6,
        RouteType.COMPLEX_WORKFLOW: 0.5,
        RouteType.CONTEXT_RETRIEVAL: 0.4,
        RouteType.ERROR_RECOVERY: 0.3
    }
    
    return thresholds.get(route_type, 0.5)


def analyze_conversation_health(state: EnhancedState) -> Dict[str, Any]:
    """
    Analyze the overall health of the conversation.
    
    Args:
        state: Current enhanced state
        
    Returns:
        Dict with health analysis
    """
    
    health_report = {
        "overall_healthy": True,
        "issues": [],
        "recommendations": []
    }
    
    # Check error state
    errors = state["errors"]
    if errors["has_errors"]:
        if errors["error_count"] > 5:
            health_report["overall_healthy"] = False
            health_report["issues"].append("High error count")
            health_report["recommendations"].append("Consider conversation reset")
        
        if errors["error_severity"] in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            health_report["overall_healthy"] = False
            health_report["issues"].append(f"Severe errors: {errors['error_severity'].value}")
    
    # Check conversation flow
    conversation = state["conversation"]
    if conversation["turn_count"] > 50:
        health_report["issues"].append("Very long conversation")
        health_report["recommendations"].append("Consider summarization")
    
    # Check tool performance
    tools = state["tool_state"]
    if tools["tool_errors"] and len(tools["tool_errors"]) > 3:
        health_report["issues"].append("Multiple tool failures")
        health_report["recommendations"].append("Check tool availability")
    
    # Check routing confidence
    routing = state["routing"]
    if routing["confidence_score"] < 0.5:
        health_report["issues"].append("Low routing confidence")
        health_report["recommendations"].append("Request clarification from user")
    
    return health_report


def create_routing_logic() -> Dict[str, Callable]:
    """
    Create the complete routing logic for the enhanced graph.
    
    Returns:
        Dict mapping routing points to functions
    """
    
    return {
        "post_validation": post_validation_routing,
        "post_routing": post_routing_routing,
        "post_agent": post_agent_routing,
        "post_recovery": post_recovery_routing
    }


# Additional utility functions for complex routing decisions

def should_summarize_conversation(state: EnhancedState) -> bool:
    """Check if conversation should be summarized."""
    
    turn_count = state["conversation"]["turn_count"]
    message_count = len(state["conversation"]["messages"])
    
    # Summarize if conversation is getting long
    return turn_count > 20 or message_count > 40


def get_fallback_strategy(state: EnhancedState) -> str:
    """Determine the best fallback strategy for current state."""
    
    intent = state["routing"]["intent_category"]
    errors = state["errors"]
    
    # Choose fallback based on context
    if intent == IntentCategory.GREETING:
        return "friendly_greeting"
    elif intent == IntentCategory.SUPPORT:
        return "helpful_clarification"
    elif errors["error_severity"] == ErrorSeverity.CRITICAL:
        return "system_maintenance"
    else:
        return "general_assistance"


def estimate_processing_complexity(state: EnhancedState) -> float:
    """
    Estimate the complexity of processing the current request.
    
    Returns complexity score from 0.0 (simple) to 1.0 (very complex)
    """
    
    complexity = 0.0
    
    # Route complexity
    route_complexity = {
        RouteType.DIRECT_RESPONSE: 0.1,
        RouteType.TOOL_EXECUTION: 0.5,
        RouteType.COMPLEX_WORKFLOW: 0.8,
        RouteType.CONTEXT_RETRIEVAL: 0.6,
        RouteType.ERROR_RECOVERY: 0.9
    }
    
    route = state["routing"]["current_route"]
    complexity += route_complexity.get(route, 0.5)
    
    # Context requirements add complexity
    context_needed = state["routing"]["context_needed"]
    complexity += len(context_needed) * 0.1
    
    # Tool requirements add complexity
    available_tools = state["tool_state"]["available_tools"]
    complexity += len(available_tools) * 0.05
    
    # Error state adds complexity
    if state["errors"]["has_errors"]:
        complexity += 0.2
    
    return min(1.0, complexity)