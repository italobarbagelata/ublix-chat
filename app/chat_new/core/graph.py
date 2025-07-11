"""
Enhanced LangGraph Chat System - Main Graph Implementation

The EnhancedGraph provides a sophisticated conversation flow with:
1. Intelligent routing based on intent classification
2. Multi-path execution with specialized nodes
3. Advanced error handling and recovery
4. Circuit breaker patterns for reliability
5. Context-aware processing
6. Tool integration with MCP support
7. Streaming capabilities with enhanced monitoring

This represents a significant advancement over the simpler linear flow
of the original system.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime
import uuid
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage
from app.chat_new.core.utils import clean_state_for_serialization, normalize_state_messages
from app.chat_new.tools.loaders import load_langchain_tools_for_project
from langchain_core.messages import AIMessage, ToolMessage

from .state import (
    EnhancedState, 
    RouteType, 
    IntentCategory,
    create_initial_enhanced_state,
    update_conversation_state,
    add_error,
    ErrorSeverity,
    is_state_healthy
)
from .nodes.router import create_router_node
from .nodes.validator import create_validator_node
from .nodes.context import create_context_node
from .nodes.agent import create_agent_node
from .nodes.persistence import create_persistence_node
from .edges.routing import create_routing_logic
from ..tools.registry import get_tool_registry
from ..services.streaming_service import EnhancedStreamingService
from app.controler.chat.store.persistence_state import MemoryStatePersistence
from app.controler.chat.core.utils import decorate_message


class EnhancedGraph:
    """
    Enhanced LangGraph implementation with sophisticated conversation management.
    
    Features:
    - Multi-path routing based on intent classification
    - Specialized nodes for different conversation aspects
    - Advanced error handling and recovery mechanisms
    - Tool integration with circuit breaker patterns
    - Context-aware processing with memory management
    - Streaming support with real-time monitoring
    - MCP tool support for extensibility
    """
    
    def __init__(
        self,
        project_id: str,
        user_id: str,
        username: str,
        source: str,
        source_id: str,
        project: Any,
        unique_id: Optional[str] = None
    ):
        self.logger = logging.getLogger(__name__)
        
        # Core identifiers
        self.project_id = project_id
        self.user_id = user_id
        self.username = username
        self.source = source
        self.source_id = source_id
        self.project = project
        self.unique_id = unique_id or str(uuid.uuid4())
        
        # State and persistence
        self.state_persistence = MemoryStatePersistence()
        self.memory = None
        
        # Graph components
        self.workflow = None
        self.compiled_graph = None
        
        # Services
        self.tool_registry = get_tool_registry()
        self.streaming_service = None
        
        # Performance tracking
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "avg_execution_time": 0.0,
            "total_execution_time": 0.0
        }
        
        self.logger.info(f"EnhancedGraph initialized for project {project_id}, user {user_id}")
    
    @classmethod
    async def create(
        cls,
        project_id: str,
        user_id: str,
        username: str,
        source: str,
        source_id: str,
        project: Any,
        unique_id: Optional[str] = None
    ) -> 'EnhancedGraph':
        """
        Factory method to create and initialize an EnhancedGraph.
        
        Args:
            project_id: Project identifier
            user_id: User identifier
            username: User display name
            source: Source platform (whatsapp, instagram, etc.)
            source_id: Source-specific identifier
            project: Project configuration object
            unique_id: Optional unique identifier
            
        Returns:
            EnhancedGraph: Fully initialized graph instance
        """
        
        instance = cls(
            project_id, user_id, username, source, source_id, project, unique_id
        )
        
        # Initialize components
        await instance._initialize_memory()
        await instance._initialize_tools()
        await instance._build_graph()
        
        return instance
    
    async def _initialize_memory(self) -> None:
        """Initialize memory and state persistence."""
        
        self.logger.info(f"{self.unique_id} Initializing memory system")
        
        # Create custom memory saver que normaliza mensajes automáticamente
        self.memory = self._create_normalized_memory_saver()
        
        # Load existing state from persistence
        try:
            saved_state = await self.state_persistence.fetch_state(
                self.project_id, self.user_id
            )
            
            if saved_state and isinstance(saved_state.get("state"), dict):
                # CRÍTICO: Normalizar estado cargado ANTES de asignarlo a memoria
                # Esto previene warnings de Pydantic cuando LangGraph procesa mensajes dict
                
                raw_state = saved_state["state"]
                self.logger.debug(f"Normalizing loaded state to prevent Pydantic warnings")
                
                # Normalizar cada valor en el estado persistido
                normalized_state = {}
                for key, value in raw_state.items():
                    if isinstance(value, dict):
                        # Normalizar sub-estados que pueden contener mensajes
                        normalized_state[key] = normalize_state_messages(value)
                    else:
                        normalized_state[key] = value
                
                self.memory.storage[self.user_id] = normalized_state
                self.logger.info(
                    f"Loaded and normalized existing state for user {self.user_id}, "
                    f"memory keys: {list(normalized_state.keys())}"
                )
            else:
                self.logger.info(f"No previous state found for user {self.user_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to load state: {str(e)}")
    
    async def _initialize_tools(self) -> None:
        """Initialize and register available tools using enhanced loader."""
        
        self.logger.info(f"{self.unique_id} Initializing tool system")
        
        try:
            # Load tools for this project with enhanced adapter
            stats = await load_langchain_tools_for_project(
                project_id=self.project_id,
                user_id=self.user_id,
                name=self.username,
                number_phone_agent="",  # Not needed for enhanced system
                unique_id=self.unique_id,
                project=self.project,
                enabled_tools=self.project.enabled_tools
            )
            
            self.logger.info(
                f"{self.unique_id} Tool loading completed: "
                f"{stats['loaded_count']} loaded, {stats['failed_count']} failed"
            )
            
            if stats['failed_count'] > 0:
                self.logger.warning(
                    f"{self.unique_id} Failed tools: {stats['failed_tools']}"
                )
            
        except Exception as e:
            self.logger.error(f"{self.unique_id} Tool initialization failed: {str(e)}", exc_info=True)
    
    async def _build_graph(self) -> None:
        """Build the enhanced conversation graph."""
        
        self.logger.info(f"{self.unique_id} Building enhanced conversation graph")
        
        # Create workflow
        self.workflow = StateGraph(EnhancedState)
        
        # Create specialized nodes
        router_node = create_router_node()
        validator_node = create_validator_node()
        context_node = create_context_node()
        agent_node = create_agent_node()
        persistence_node = create_persistence_node()
        
        # Add nodes to workflow
        self.workflow.add_node("preprocessor", self._create_preprocessor_node())  # CRÍTICO: Primer nodo
        self.workflow.add_node("validator", validator_node)
        self.workflow.add_node("router", router_node)
        self.workflow.add_node("context", context_node)
        self.workflow.add_node("agent", agent_node)
        self.workflow.add_node("tools", self._create_tools_node())
        self.workflow.add_node("recovery", self._create_recovery_node())
        self.workflow.add_node("formatter", self._create_formatter_node())
        self.workflow.add_node("persistence", persistence_node)
        
        # Create routing logic
        routing_logic = create_routing_logic()
        
        # Add edges
        self._add_graph_edges(routing_logic)
        
        # Compile graph
        self.compiled_graph = self.workflow.compile(checkpointer=self.memory)
        
        # Initialize streaming service
        self.streaming_service = EnhancedStreamingService(self.compiled_graph)
        
        self.logger.info(f"{self.unique_id} Enhanced graph built successfully")
    
    def _create_normalized_memory_saver(self):
        """
        Create a custom MemorySaver that automatically normalizes messages.
        
        CRÍTICO: Esto previene warnings de Pydantic interceptando mensajes dict
        ANTES de que LangGraph los procese internamente.
        """
        
        class NormalizedMemorySaver(MemorySaver):
            def __init__(self, logger):
                super().__init__()
                self.logger = logger
            
            def get(self, config):
                """Intercepta la carga de estado y normaliza mensajes dict."""
                checkpoint = super().get(config)
                
                if checkpoint is None:
                    return None
                
                try:                    
                    # Normalizar el channel_values dentro del checkpoint
                    if hasattr(checkpoint, 'channel_values') and checkpoint.channel_values:
                        normalized_values = {}
                        for key, value in checkpoint.channel_values.items():
                            if isinstance(value, dict):
                                # Normalizar sub-estados que pueden contener mensajes dict
                                normalized_value = normalize_state_messages(value)
                                normalized_values[key] = normalized_value
                            else:
                                normalized_values[key] = value
                        
                        # Actualizar el checkpoint con valores normalizados
                        checkpoint.channel_values = normalized_values
                        self.logger.debug("Checkpoint normalized by custom MemorySaver")
                    
                    return checkpoint
                    
                except Exception as e:
                    self.logger.warning(f"Error normalizing checkpoint in MemorySaver: {e}")
                    return checkpoint
            
            def put(self, config, checkpoint, metadata, new_versions):
                """Intercepta el guardado de estado y normaliza mensajes."""
                try:
                    # Limpiar checkpoint antes de guardarlo
                    if hasattr(checkpoint, 'channel_values'):
                        # checkpoint.channel_values contiene el estado actual
                        cleaned_values = clean_state_for_serialization(checkpoint.channel_values)
                        checkpoint.channel_values = cleaned_values
                    
                    return super().put(config, checkpoint, metadata, new_versions)
                    
                except Exception as e:
                    self.logger.warning(f"Error cleaning checkpoint in MemorySaver: {e}")
                    return super().put(config, checkpoint, metadata, new_versions)
        
        return NormalizedMemorySaver(self.logger)
    
    def _create_preprocessor_node(self):
        """
        Create preprocessor node that normalizes state from persistence.
        
        CRÍTICO: Este nodo debe ser el PRIMERO para interceptar mensajes dict
        que vienen de la persistencia de LangGraph y prevenir warnings Pydantic.
        """
        
        def preprocessor_node(state: EnhancedState) -> EnhancedState:
            """
            Preprocessor que normaliza TODOS los mensajes del estado.
            
            Args:
                state: Estado (puede contener mensajes dict de persistencia)
                
            Returns:
                Estado con todos los mensajes normalizados
            """
            try:                
                # CRÍTICO: Normalizar INMEDIATAMENTE al recibir el estado
                # Esto previene que mensajes dict causen warnings Pydantic
                normalized_state = normalize_state_messages(state)
                
                # Verificar y limpiar secuencias de tool_calls
                normalized_state = self._fix_tool_message_sequence(normalized_state)
                
                self.logger.debug(f"{state.get('unique_id', 'unknown')} State preprocessed successfully")
                
                return normalized_state
                
            except Exception as e:
                self.logger.error(f"Preprocessor error: {str(e)}")
                # Devolver estado original si falla la normalización
                return state
        
        return preprocessor_node
    
    def _fix_tool_message_sequence(self, state: EnhancedState) -> EnhancedState:
        """
        Arregla secuencias de tool_calls para evitar errores de OpenAI API.
        
        Args:
            state: Estado con mensajes normalizados
            
        Returns:
            Estado con secuencias de herramientas corregidas
        """
        
        try:
            messages = state.get("messages", [])
            conversation_messages = state.get("conversation", {}).get("messages", [])
            
            # Limpiar ambas listas de mensajes
            state["messages"] = self._clean_tool_message_sequence(messages)
            if "conversation" in state and "messages" in state["conversation"]:
                state["conversation"]["messages"] = self._clean_tool_message_sequence(conversation_messages)
            
            return state
            
        except Exception as e:
            self.logger.warning(f"Error fixing tool message sequence: {e}")
            return state
    
    def _clean_tool_message_sequence(self, messages: List) -> List:
        """
        Limpia una secuencia de mensajes para asegurar que tool_calls tengan respuestas.
        Evita el error: "An assistant message with 'tool_calls' must be followed by tool messages"
        
        Args:
            messages: Lista de mensajes
            
        Returns:
            Lista de mensajes limpia sin tool_calls huérfanos
        """
        
        if not messages:
            return []
        
        cleaned_messages = []
        i = 0
        
        while i < len(messages):
            msg = messages[i]
            
            # Si es un AI message con tool_calls
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                # Buscar los ToolMessage correspondientes
                expected_tool_call_ids = set()
                for tc in msg.tool_calls:
                    if isinstance(tc, dict) and 'id' in tc:
                        expected_tool_call_ids.add(tc['id'])
                
                # Buscar los ToolMessage que siguen a este AI message
                found_tool_call_ids = set()
                j = i + 1
                tool_messages = []
                
                while j < len(messages) and len(found_tool_call_ids) < len(expected_tool_call_ids):
                    next_msg = messages[j]
                    
                    # Si es un ToolMessage que responde a nuestros tool_calls
                    if (hasattr(next_msg, 'tool_call_id') and 
                        next_msg.tool_call_id in expected_tool_call_ids):
                        found_tool_call_ids.add(next_msg.tool_call_id)
                        tool_messages.append(next_msg)
                    
                    # Si es otro AI message, parar la búsqueda
                    elif hasattr(next_msg, 'content') and next_msg.__class__.__name__ == 'AIMessage':
                        break
                    
                    j += 1
                
                # Solo incluir AI message con tool_calls si TODOS tienen respuesta
                if len(found_tool_call_ids) == len(expected_tool_call_ids):
                    # Incluir AI message y sus ToolMessage
                    cleaned_messages.append(msg)
                    cleaned_messages.extend(tool_messages)
                    i = j  # Saltar a después de los ToolMessages procesados
                else:
                    # AI message con tool_calls incompletos - crear versión limpia
                    clean_ai_msg = AIMessage(content=msg.content)
                    cleaned_messages.append(clean_ai_msg)
                    i += 1
            
            # Si es un ToolMessage huérfano (sin AI message previo con tool_calls)
            elif hasattr(msg, 'tool_call_id') and msg.tool_call_id:
                # Omitir ToolMessages huérfanos
                i += 1
            
            # Mensaje normal (Human, AI sin tool_calls, etc.)
            else:
                cleaned_messages.append(msg)
                i += 1
        
        return cleaned_messages
    
    def _add_graph_edges(self, routing_logic: Dict[str, Any]) -> None:
        """Add edges to define the conversation flow."""
        
        # Start with preprocessing to normalize state from persistence
        self.workflow.add_edge(START, "preprocessor")
        self.workflow.add_edge("preprocessor", "validator")
        
        # After validation, route based on state
        self.workflow.add_conditional_edges(
            "validator",
            routing_logic["post_validation"],
            {
                "route": "router",
                "recovery": "recovery",
                "end": "persistence"
            }
        )
        
        # After routing, decide next step
        self.workflow.add_conditional_edges(
            "router", 
            routing_logic["post_routing"],
            {
                "context": "context",
                "direct": "agent",
                "recovery": "recovery"
            }
        )
        
        # After context enrichment, go to agent
        self.workflow.add_edge("context", "agent")
        
        # After agent, decide if tools are needed
        self.workflow.add_conditional_edges(
            "agent",
            routing_logic["post_agent"],
            {
                "tools": "tools",
                "format": "formatter",
                "recovery": "recovery"
            }
        )
        
        # After tools, back to agent for final response
        self.workflow.add_edge("tools", "agent")
        
        # After formatting, save to database then end
        self.workflow.add_edge("formatter", "persistence")
        self.workflow.add_edge("persistence", END)
        
        # Recovery can go to different places
        self.workflow.add_conditional_edges(
            "recovery",
            routing_logic["post_recovery"],
            {
                "retry": "agent",
                "fallback": "formatter",
                "end": "persistence"
            }
        )
    
    def _create_tools_node(self):
        """Create tools execution node with enhanced error handling."""
        
        async def tools_node(state: EnhancedState) -> EnhancedState:
            try:
                self.logger.info(f"{state['unique_id']} Executing tools node")
                
                # Get the last message to check for tool calls
                messages = state["conversation"]["messages"]
                if not messages:
                    return state
                
                last_message = messages[-1]
                
                # Check if there are tool calls to execute
                if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
                    self.logger.info("No tool calls found, skipping tools execution")
                    return state
                
                # Execute tool calls using the enhanced registry
                tool_results = []
                
                for tool_call in last_message.tool_calls:
                    try:
                        tool_name = tool_call.get("name", "unknown")
                        tool_args = tool_call.get("args", {})
                        
                        # Execute tool through registry
                        result = await self.tool_registry.execute_tool(
                            tool_name, state, **tool_args
                        )
                        
                        tool_results.append({
                            "tool_call_id": tool_call.get("id"),
                            "content": str(result)
                        })
                        
                    except Exception as e:
                        self.logger.error(f"Tool {tool_name} execution failed: {str(e)}")
                        tool_results.append({
                            "tool_call_id": tool_call.get("id"),
                            "content": f"Error: {str(e)}"
                        })
                
                # Add tool results to messages
                if tool_results:
                    for result in tool_results:
                        tool_msg = ToolMessage(
                            content=result["content"],
                            tool_call_id=result["tool_call_id"]
                        )
                        state["messages"].append(tool_msg)
                        state["conversation"]["messages"].append(tool_msg)
                
                return state
                
            except Exception as e:
                self.logger.error(f"Tools node error: {str(e)}")
                return add_error(state, e, "Tools execution", ErrorSeverity.MEDIUM)
        
        return tools_node
    
    def _create_recovery_node(self):
        """Create error recovery node."""
        
        def recovery_node(state: EnhancedState) -> EnhancedState:
            try:
                self.logger.info(f"{state['unique_id']} Executing recovery node")
                
                # Check error state
                errors = state["errors"]
                
                if errors["has_errors"]:
                    # Implement recovery strategies based on error severity
                    if errors["error_severity"] == ErrorSeverity.CRITICAL:
                        # Critical errors - stop processing
                        state["routing"]["next_action"] = "end"
                    elif errors["error_severity"] == ErrorSeverity.HIGH:
                        # High severity - try fallback
                        state["routing"]["next_action"] = "fallback"
                        errors["recovery_attempts"] += 1
                    else:
                        # Medium/Low severity - retry if not too many attempts
                        if errors["recovery_attempts"] < 3:
                            state["routing"]["next_action"] = "retry"
                            errors["recovery_attempts"] += 1
                        else:
                            state["routing"]["next_action"] = "fallback"
                
                return state
                
            except Exception as e:
                self.logger.error(f"Recovery node error: {str(e)}")
                return state
        
        return recovery_node
    
    def _create_formatter_node(self):
        """Create response formatting node."""
        
        def formatter_node(state: EnhancedState) -> EnhancedState:
            try:
                self.logger.info(f"{state['unique_id']} Executing formatter node")
                
                # Get the last AI message
                messages = state["conversation"]["messages"]
                if messages and hasattr(messages[-1], 'content'):
                    last_response = messages[-1].content
                    
                    # Apply source-specific formatting
                    source = state["user"]["source"]
                    
                    if source == "whatsapp":
                        # WhatsApp-specific formatting
                        formatted_response = self._format_for_whatsapp(last_response)
                    elif source == "instagram":
                        # Instagram-specific formatting
                        formatted_response = self._format_for_instagram(last_response)
                    else:
                        # Default formatting
                        formatted_response = last_response
                    
                    # Update the message content
                    messages[-1].content = formatted_response
                
                return state
                
            except Exception as e:
                self.logger.error(f"Formatter node error: {str(e)}")
                return state
        
        return formatter_node
    
    def _format_for_whatsapp(self, response: str) -> str:
        """Apply WhatsApp-specific formatting."""
        # Basic WhatsApp formatting - could be enhanced
        return response
    
    def _format_for_instagram(self, response: str) -> str:
        """Apply Instagram-specific formatting."""
        # Basic Instagram formatting - could be enhanced
        return response
    
    async def execute(self, message: str, background_tasks: Optional[Any] = None) -> Dict[str, Any]:
        """
        Execute the enhanced graph with a user message.
        
        Args:
            message: User message to process
            background_tasks: Optional background tasks handler
            
        Returns:
            Dict with execution result
        """
        
        start_time = datetime.now()
        
        try:
            self.logger.info(f"{self.unique_id} Starting enhanced graph execution")
            
            # Update execution stats
            self.execution_stats["total_executions"] += 1
            
            # Create initial state
            initial_state = create_initial_enhanced_state(
                user_id=self.user_id,
                username=self.username,
                project=self.project,
                source=self.source,
                source_id=self.source_id,
                unique_id=self.unique_id
            )
            
            # Add user message
            human_message = HumanMessage(content=message)
            decorate_message(human_message, initial_state["exec_init"], initial_state["conversation"]["conversation_id"])
            
            initial_state["messages"] = [human_message]
            initial_state["conversation"]["messages"] = [human_message]
            initial_state = update_conversation_state(initial_state, human_message)
            
            # CRÍTICO: Limpiar estado ANTES de invocar LangGraph para prevenir warnings    
            # Doble limpieza: normalización + serialización
            normalized_initial_state = normalize_state_messages(initial_state)
            ultra_cleaned_state = clean_state_for_serialization(normalized_initial_state)
            
            # Execute graph con estado completamente limpio
            final_state = await self.compiled_graph.ainvoke(
                ultra_cleaned_state,
                {"configurable": {"thread_id": self.user_id}}
            )
            
            # Extract response
            messages = final_state["conversation"]["messages"]
            ai_response = None
            
            for msg in reversed(messages):
                if hasattr(msg, 'content') and msg.__class__.__name__ == 'AIMessage':
                    ai_response = msg
                    break
            
            if not ai_response:
                raise RuntimeError("No AI response generated")
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Update stats
            self.execution_stats["successful_executions"] += 1
            self.execution_stats["total_execution_time"] += execution_time
            self.execution_stats["avg_execution_time"] = (
                self.execution_stats["total_execution_time"] / 
                self.execution_stats["total_executions"]
            )
            
            # Save state in background
            if background_tasks:
                background_tasks.add_task(self._save_state_background, final_state)
            else:
                await self._save_state_background(final_state)
            
            # Prepare response
            response = {
                "response": ai_response.content,
                "message_id": getattr(ai_response, 'id', str(uuid.uuid4())),
                "user_id": self.user_id,
                "processing_time": execution_time,
                "execution_route": final_state["routing"]["current_route"].value,
                "intent_category": final_state["routing"]["intent_category"].value,
                "confidence_score": final_state["routing"]["confidence_score"],
                "tools_used": len(final_state["tool_state"]["tool_results"]),
                "state_healthy": is_state_healthy(final_state)
            }
            
            self.logger.info(
                f"{self.unique_id} Enhanced graph execution completed in {execution_time:.2f}s"
            )
            
            return response
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.execution_stats["failed_executions"] += 1
            
            self.logger.error(
                f"{self.unique_id} Enhanced graph execution failed: {str(e)}", 
                exc_info=True
            )
            
            # Return error response
            return {
                "response": "Lo siento, ocurrió un error procesando tu mensaje. ¿Podrías intentar de nuevo?",
                "message_id": str(uuid.uuid4()),
                "user_id": self.user_id,
                "processing_time": execution_time,
                "error": str(e),
                "execution_route": "error",
                "state_healthy": False
            }
    
    async def execute_stream(self, message: str, background_tasks: Optional[Any] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the enhanced graph with streaming response.
        
        Args:
            message: User message to process
            background_tasks: Optional background tasks handler
            
        Yields:
            Dict with streaming response chunks
        """
        
        try:
            self.logger.info(f"{self.unique_id} Starting enhanced streaming execution")
            
            # Create initial state (same as execute)
            initial_state = create_initial_enhanced_state(
                user_id=self.user_id,
                username=self.username,
                project=self.project,
                source=self.source,
                source_id=self.source_id,
                unique_id=self.unique_id
            )
            
            # Add user message
            human_message = HumanMessage(content=message)
            decorate_message(human_message, initial_state["exec_init"], initial_state["conversation"]["conversation_id"])
            
            initial_state["messages"] = [human_message]
            initial_state["conversation"]["messages"] = [human_message]
            initial_state = update_conversation_state(initial_state, human_message)
            
            # CRÍTICO: Limpiar estado ANTES de streaming para prevenir warnings
            
            
            # Doble limpieza: normalización + serialización  
            normalized_initial_state = normalize_state_messages(initial_state)
            ultra_cleaned_state = clean_state_for_serialization(normalized_initial_state)
            
            # Stream execution con estado completamente limpio
            async for chunk in self.streaming_service.stream_enhanced_execution(
                ultra_cleaned_state,
                {"configurable": {"thread_id": self.user_id}}
            ):
                yield chunk
            
            # Save state in background after streaming completes
            if background_tasks:
                # Get final state from streaming service
                final_state = self.streaming_service.get_final_state()
                if final_state:
                    background_tasks.add_task(self._save_state_background, final_state)
            
        except Exception as e:
            self.logger.error(f"Enhanced streaming execution failed: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
                "is_complete": True
            }
    
    async def _save_state_background(self, final_state: EnhancedState) -> None:
        """Save state to persistence in background."""
        
        try:
            # Extract and clean memory state
            final_memory_state = self.compiled_graph.checkpointer.storage.get(self.user_id)
            
            if final_memory_state:
                # Clean up old entries to manage memory size
                nested_dict = final_memory_state.get('', {})
                
                if isinstance(nested_dict, dict):
                    from collections import OrderedDict
                    if not isinstance(nested_dict, OrderedDict):
                        nested_dict = OrderedDict(nested_dict)
                    
                    # Keep only the most recent entries
                    MAX_KEYS = 5
                    while len(nested_dict) > MAX_KEYS:
                        nested_dict.popitem(last=False)
                    
                    final_memory_state[''] = nested_dict
                
                # Save to persistence
                from app.controler.chat.classes.chat_state import ChatState
                chat_state = ChatState(self.project_id, self.user_id)
                chat_state.state = final_memory_state
                
                await self.state_persistence.save_state(chat_state)
                
                self.logger.info(f"State saved successfully for user {self.user_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to save state: {str(e)}")
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics for monitoring."""
        
        success_rate = 0.0
        if self.execution_stats["total_executions"] > 0:
            success_rate = (
                self.execution_stats["successful_executions"] / 
                self.execution_stats["total_executions"]
            )
        
        return {
            **self.execution_stats,
            "success_rate": success_rate,
            "tool_registry_stats": self.tool_registry.get_registry_stats(),
            "memory_keys": len(self.memory.storage.get(self.user_id, {})),
            "graph_healthy": success_rate > 0.8  # 80% success rate threshold
        }
    
    def get_current_state(self) -> Optional[EnhancedState]:
        """
        Get current conversation state from memory.
        
        Returns:
            Current enhanced state or None if not available
        """
        try:
            config = {"configurable": {"thread_id": self.user_id}}
            checkpoint = self.memory.get(config)
            
            if checkpoint and hasattr(checkpoint, 'channel_values'):
                return checkpoint.channel_values
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get current state: {str(e)}")
            return None
    
    @property 
    def state(self) -> Optional[EnhancedState]:
        """Property to access current conversation state."""
        return self.get_current_state()
    
    def get_conversation_history(self) -> List[Any]:
        """
        Get conversation message history.
        
        Returns:
            List of conversation messages
        """
        current_state = self.get_current_state()
        if current_state:
            return current_state.get("conversation", {}).get("messages", [])
        return []
    
    def get_tool_execution_history(self) -> List[Dict[str, Any]]:
        """
        Get tool execution history.
        
        Returns:
            List of tool execution results
        """
        current_state = self.get_current_state()
        if current_state:
            return current_state.get("tool_state", {}).get("tool_results", [])
        return []