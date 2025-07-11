"""
Enhanced State Management System

Provides granular state management with multiple layers:
- ConversationState: Current conversation context
- UserContext: User information and preferences  
- ToolState: Tool execution state and results
- RouteState: Routing decisions and metadata
- ErrorState: Error tracking and recovery
"""

from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any, List
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from datetime import datetime
from enum import Enum
import uuid

from app.controler.chat.classes.project import Project


class RouteType(Enum):
    """Available routing types for different conversation flows"""
    DIRECT_RESPONSE = "direct_response"      # Simple Q&A
    TOOL_EXECUTION = "tool_execution"        # Requires tools
    COMPLEX_WORKFLOW = "complex_workflow"    # Multi-step process
    ERROR_RECOVERY = "error_recovery"        # Error handling
    CONTEXT_RETRIEVAL = "context_retrieval"  # Need more context


class IntentCategory(Enum):
    """Intent categories for routing decisions"""
    GREETING = "greeting"
    QUESTION = "question"
    REQUEST = "request"
    COMPLAINT = "complaint"
    BOOKING = "booking"
    PRODUCT_INQUIRY = "product_inquiry"
    SUPPORT = "support"
    GENERAL = "general"


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"           # Minor issues, continue normally
    MEDIUM = "medium"     # Significant issues, try alternatives
    HIGH = "high"         # Critical issues, require intervention
    CRITICAL = "critical" # System-level issues, halt processing


class ConversationState(TypedDict):
    """State related to the current conversation"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    conversation_id: str
    turn_count: int
    summary: str
    last_user_message: Optional[str]
    last_ai_message: Optional[str]
    conversation_started_at: datetime
    last_activity_at: datetime


class UserContext(TypedDict):
    """State related to user information and context"""
    user_id: str
    username: str
    project: Project
    source: str            # whatsapp, instagram, etc.
    source_id: str
    phone_number: Optional[str]
    email: Optional[str]
    language: str
    timezone: str
    user_preferences: Dict[str, Any]
    contact_info: Dict[str, Any]
    session_metadata: Dict[str, Any]


class ToolState(TypedDict):
    """State related to tool execution"""
    available_tools: List[str]
    tool_calls_in_progress: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    tool_errors: List[Dict[str, Any]]
    tool_cache: Dict[str, Any]
    last_tool_used: Optional[str]
    tool_execution_count: int
    mcp_tools: List[Dict[str, Any]]


class RouteState(TypedDict):
    """State related to routing decisions and flow control"""
    current_route: RouteType
    intent_category: IntentCategory
    confidence_score: float
    alternative_routes: List[RouteType]
    routing_history: List[Dict[str, Any]]
    context_needed: List[str]
    workflow_step: Optional[str]
    next_action: Optional[str]


class ErrorState(TypedDict):
    """State related to error tracking and recovery"""
    has_errors: bool
    error_count: int
    last_error: Optional[Dict[str, Any]]
    error_history: List[Dict[str, Any]]
    recovery_attempts: int
    fallback_used: bool
    circuit_breaker_status: Dict[str, Any]
    error_severity: ErrorSeverity


class EnhancedState(TypedDict):
    """
    Enhanced state combining all state layers for comprehensive conversation management.
    
    This state provides:
    - Granular tracking of conversation flow
    - Detailed user context management  
    - Tool execution monitoring
    - Intelligent routing information
    - Comprehensive error handling
    """
    
    # Core identifiers
    unique_id: str
    exec_init: str
    
    # State layers
    conversation: ConversationState
    user: UserContext
    tool_state: ToolState
    routing: RouteState
    errors: ErrorState
    
    # Compatibility with existing system
    project: Project
    user_id: str
    messages: Annotated[Sequence[BaseMessage], add_messages]
    summary: str


def create_initial_enhanced_state(
    user_id: str,
    username: str,
    project: Project,
    source: str,
    source_id: str,
    unique_id: Optional[str] = None
) -> EnhancedState:
    """
    Factory function to create initial enhanced state with proper defaults.
    
    Args:
        user_id: User identifier
        username: User display name
        project: Project configuration
        source: Source platform (whatsapp, instagram, etc.)
        source_id: Source-specific identifier
        unique_id: Optional unique identifier for this conversation
        
    Returns:
        EnhancedState: Fully initialized state object
    """
    
    now = datetime.now()
    conversation_id = str(uuid.uuid4())
    unique_id = unique_id or str(uuid.uuid4())
    
    return EnhancedState(
        # Core identifiers
        unique_id=unique_id,
        exec_init=now.isoformat(),
        
        # Conversation state
        conversation=ConversationState(
            messages=[],
            conversation_id=conversation_id,
            turn_count=0,
            summary="",
            last_user_message=None,
            last_ai_message=None,
            conversation_started_at=now,
            last_activity_at=now
        ),
        
        # User context
        user=UserContext(
            user_id=user_id,
            username=username,
            project=project,
            source=source,
            source_id=source_id,
            phone_number=None,
            email=None,
            language="es",
            timezone="America/Santiago",
            user_preferences={},
            contact_info={},
            session_metadata={}
        ),
        
        # Tool state
        tool_state=ToolState(
            available_tools=[],
            tool_calls_in_progress=[],
            tool_results=[],
            tool_errors=[],
            tool_cache={},
            last_tool_used=None,
            tool_execution_count=0,
            mcp_tools=[]
        ),
        
        # Routing state
        routing=RouteState(
            current_route=RouteType.DIRECT_RESPONSE,
            intent_category=IntentCategory.GENERAL,
            confidence_score=0.0,
            alternative_routes=[],
            routing_history=[],
            context_needed=[],
            workflow_step=None,
            next_action=None
        ),
        
        # Error state
        errors=ErrorState(
            has_errors=False,
            error_count=0,
            last_error=None,
            error_history=[],
            recovery_attempts=0,
            fallback_used=False,
            circuit_breaker_status={},
            error_severity=ErrorSeverity.LOW
        ),
        
        # Compatibility fields
        project=project,
        user_id=user_id,
        messages=[],
        summary=""
    )


def update_conversation_state(
    state: EnhancedState, 
    new_message: Optional[BaseMessage] = None
) -> EnhancedState:
    """
    Update conversation state with new message and metadata.
    
    Args:
        state: Current enhanced state
        new_message: Optional new message to add
        
    Returns:
        EnhancedState: Updated state
    """
    
    now = datetime.now()
    
    # Update conversation metadata
    state["conversation"]["turn_count"] += 1
    state["conversation"]["last_activity_at"] = now
    
    if new_message:
        # Track last messages by type
        if hasattr(new_message, 'content'):
            if new_message.__class__.__name__ == 'HumanMessage':
                state["conversation"]["last_user_message"] = new_message.content
            elif new_message.__class__.__name__ == 'AIMessage':
                state["conversation"]["last_ai_message"] = new_message.content
    
    return state


def add_tool_result(
    state: EnhancedState,
    tool_name: str,
    result: Any,
    execution_time: float = 0.0,
    success: bool = True
) -> EnhancedState:
    """
    Add tool execution result to state.
    
    Args:
        state: Current enhanced state
        tool_name: Name of the executed tool
        result: Tool execution result
        execution_time: Time taken to execute
        success: Whether execution was successful
        
    Returns:
        EnhancedState: Updated state
    """
    
    # Inicializar tool_state si no existe o está incompleto
    if "tool_state" not in state:
        state["tool_state"] = create_tool_state()
    
    # Verificar que tool_results exista
    if "tool_results" not in state["tool_state"]:
        state["tool_state"]["tool_results"] = []
    
    if "tool_execution_count" not in state["tool_state"]:
        state["tool_state"]["tool_execution_count"] = 0
    
    tool_result = {
        "tool_name": tool_name,
        "result": result,
        "execution_time": execution_time,
        "success": success,
        "timestamp": datetime.now().isoformat()
    }
    
    state["tool_state"]["tool_results"].append(tool_result)
    state["tool_state"]["last_tool_used"] = tool_name
    state["tool_state"]["tool_execution_count"] += 1
    
    return state


def add_error(
    state: EnhancedState,
    error: Exception,
    context: str,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
) -> EnhancedState:
    """
    Add error information to state.
    
    Args:
        state: Current enhanced state
        error: Exception that occurred
        context: Context where error occurred
        severity: Error severity level
        
    Returns:
        EnhancedState: Updated state
    """
    
    # Inicializar errors si no existe o está incompleto
    if "errors" not in state:
        state["errors"] = create_error_state()
    
    # Verificar que error_history exista
    if "error_history" not in state["errors"]:
        state["errors"]["error_history"] = []
    
    if "error_count" not in state["errors"]:
        state["errors"]["error_count"] = 0
    
    error_info = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context,
        "severity": severity.value,
        "timestamp": datetime.now().isoformat(),
        "stack_trace": str(error) if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL] else None
    }
    
    state["errors"]["error_history"].append(error_info)
    state["errors"]["last_error"] = error_info
    state["errors"]["error_count"] += 1
    state["errors"]["has_errors"] = True
    state["errors"]["error_severity"] = severity
    
    return state


def set_route(
    state: EnhancedState,
    route: RouteType,
    intent: IntentCategory,
    confidence: float = 0.0
) -> EnhancedState:
    """
    Set routing information in state.
    
    Args:
        state: Current enhanced state
        route: Selected route type
        intent: Detected intent category
        confidence: Confidence score for the routing decision
        
    Returns:
        EnhancedState: Updated state
    """
    
    # Add to routing history
    routing_decision = {
        "route": route.value,
        "intent": intent.value,
        "confidence": confidence,
        "timestamp": datetime.now().isoformat()
    }
    
    state["routing"]["routing_history"].append(routing_decision)
    state["routing"]["current_route"] = route
    state["routing"]["intent_category"] = intent
    state["routing"]["confidence_score"] = confidence
    
    return state


# Utility functions for state inspection

def get_conversation_summary(state: EnhancedState) -> str:
    """Get a brief summary of the conversation state"""
    conv = state["conversation"]
    return f"Turn {conv['turn_count']}: {len(conv['messages'])} messages, last activity: {conv['last_activity_at']}"


def get_tool_summary(state: EnhancedState) -> str:
    """Get a brief summary of tool execution state"""
    tools = state["tool_state"]
    return f"Tools: {tools['tool_execution_count']} executions, {len(tools['tool_errors'])} errors, last: {tools['last_tool_used']}"


def get_error_summary(state: EnhancedState) -> str:
    """Get a brief summary of error state"""
    errors = state["errors"]
    if not errors["has_errors"]:
        return "No errors"
    return f"Errors: {errors['error_count']} total, severity: {errors['error_severity'].value}, recoveries: {errors['recovery_attempts']}"


def is_state_healthy(state: EnhancedState) -> bool:
    """Check if the conversation state is healthy"""
    errors = state["errors"]
    
    # State is unhealthy if there are critical errors or too many errors
    if errors["error_severity"] == ErrorSeverity.CRITICAL:
        return False
    
    if errors["error_count"] > 10:  # Too many errors
        return False
        
    if errors["recovery_attempts"] > 5:  # Too many recovery attempts
        return False
    
    return True