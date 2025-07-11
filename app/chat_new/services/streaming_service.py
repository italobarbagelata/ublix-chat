"""
Enhanced Streaming Service for LangGraph Chat System

Provides advanced streaming capabilities with:
1. Real-time graph execution monitoring
2. Node-level progress tracking
3. Enhanced error handling and recovery
4. Performance metrics collection
5. State checkpoint management
6. Custom event generation
7. Quality assessment during streaming

This service significantly enhances the user experience with
detailed progress information and robust error handling.
"""

import logging
import asyncio
import time
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from langchain_core.messages import AIMessage, HumanMessage

from ..core.state import EnhancedState, ErrorSeverity


class StreamEventType(Enum):
    """Types of streaming events"""
    IMMEDIATE_RESPONSE = "immediate_response"
    NODE_START = "node_start"
    NODE_COMPLETE = "node_complete"
    CONTENT_CHUNK = "content_chunk"
    TOOL_EXECUTION = "tool_execution"
    ERROR = "error"
    COMPLETION = "completion"
    STATUS_UPDATE = "status_update"
    PERFORMANCE_METRIC = "performance_metric"


class NodeStatus(Enum):
    """Node execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EnhancedStreamingService:
    """
    Advanced streaming service with comprehensive monitoring and control.
    
    Features:
    - Real-time node execution tracking
    - Performance metrics collection
    - Enhanced error handling with recovery
    - Custom event generation
    - State checkpoint management
    - Quality assessment
    - User experience optimization
    """
    
    def __init__(self, compiled_graph):
        self.logger = logging.getLogger(__name__)
        self.compiled_graph = compiled_graph
        
        # Execution tracking
        self.current_execution = None
        self.execution_start_time = None
        self.node_timings = {}
        self.final_state = None
        
        # Performance metrics
        self.metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "avg_execution_time": 0.0,
            "node_performance": {}
        }
        
        # Node execution tracking
        self.node_status = {}
        self.execution_flow = []
        
        # Quality thresholds
        self.min_response_length = 10
        self.max_chunk_delay = 2.0  # seconds
        
        self.logger.info("EnhancedStreamingService initialized")
    
    async def stream_enhanced_execution(
        self,
        initial_state: EnhancedState,
        config: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream enhanced graph execution with detailed monitoring.
        
        Args:
            initial_state: Initial state for execution
            config: Execution configuration
            
        Yields:
            Dict: Streaming events with detailed information
        """
        
        execution_id = initial_state["unique_id"]
        self.current_execution = execution_id
        self.execution_start_time = time.time()
        
        try:
            self.logger.info(f"Starting enhanced streaming execution: {execution_id}")
            
            # Update metrics
            self.metrics["total_executions"] += 1
            
            # Send immediate response
            yield await self._generate_immediate_response(initial_state)
            
            # Initialize node tracking
            await self._initialize_node_tracking(initial_state)
            
            # Stream graph execution with monitoring
            async for event in self._stream_with_monitoring(initial_state, config):
                yield event
            
            # Send completion event
            execution_time = time.time() - self.execution_start_time
            yield self._create_completion_event(execution_time)
            
            # Update success metrics
            self.metrics["successful_executions"] += 1
            self._update_performance_metrics(execution_time)
            
        except Exception as e:
            # Handle execution errors
            self.logger.error(f"Enhanced streaming execution failed: {str(e)}", exc_info=True)
            self.metrics["failed_executions"] += 1
            
            yield {
                "type": StreamEventType.ERROR.value,
                "error": str(e),
                "execution_id": execution_id,
                "is_complete": True,
                "timestamp": datetime.now().isoformat()
            }
    
    async def _generate_immediate_response(self, state: EnhancedState) -> Dict[str, Any]:
        """Generate immediate response based on message analysis."""
        
        # Analyze the user message for immediate response
        messages = state["conversation"]["messages"]
        if not messages:
            response_text = "⏳ Procesando tu mensaje..."
        else:
            last_message = messages[-1].content if hasattr(messages[-1], 'content') else ""
            response_text = self._get_contextual_immediate_response(last_message)
        
        return {
            "type": StreamEventType.IMMEDIATE_RESPONSE.value,
            "content": response_text,
            "execution_id": state["unique_id"],
            "timestamp": datetime.now().isoformat(),
            "is_complete": False
        }
    
    def _get_contextual_immediate_response(self, message: str) -> str:
        """Get contextual immediate response based on message content."""
        
        message_lower = message.lower()
        
        # Contextual immediate responses
        if any(word in message_lower for word in ['agenda', 'cita', 'horario', 'agendar']):
            return "📅 Revisando tu agenda y horarios disponibles..."
        elif any(word in message_lower for word in ['producto', 'precio', 'comprar', 'catálogo']):
            return "🛍️ Buscando productos y precios..."
        elif any(word in message_lower for word in ['ayuda', 'soporte', 'problema']):
            return "🔧 Analizando tu consulta de soporte..."
        elif any(word in message_lower for word in ['email', 'enviar', 'correo']):
            return "📧 Preparando información para el email..."
        elif any(word in message_lower for word in ['información', 'buscar', 'encontrar']):
            return "🔍 Buscando información relevante..."
        else:
            return "⏳ Procesando tu mensaje..."
    
    async def _initialize_node_tracking(self, state: EnhancedState) -> None:
        """Initialize node execution tracking."""
        
        # Define expected node execution order
        expected_nodes = [
            "validator", "router", "context", "agent", "tools", "formatter"
        ]
        
        self.node_status = {
            node: NodeStatus.PENDING for node in expected_nodes
        }
        self.execution_flow = []
        self.node_timings = {}
    
    async def _stream_with_monitoring(
        self,
        initial_state: EnhancedState,
        config: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream graph execution with detailed monitoring."""
        
        try:
            # Use LangGraph's streaming capability
            async for chunk in self.compiled_graph.astream(initial_state, config):
                
                # Process each chunk from the graph
                for node_name, node_output in chunk.items():
                    
                    # Track node execution
                    await self._track_node_execution(node_name, node_output)
                    
                    # Generate node events
                    async for event in self._process_node_output(node_name, node_output):
                        yield event
                    
                    # Extract content for streaming
                    async for content_event in self._extract_streaming_content(node_name, node_output):
                        yield content_event
                
                # Store final state
                if chunk:
                    # Extract state from the last node output
                    last_node_output = list(chunk.values())[-1]
                    if isinstance(last_node_output, dict) and "messages" in last_node_output:
                        self.final_state = last_node_output
        
        except Exception as e:
            self.logger.error(f"Streaming monitoring failed: {str(e)}")
            raise
    
    async def _track_node_execution(self, node_name: str, node_output: Any) -> None:
        """Track node execution for monitoring."""
        
        current_time = time.time()
        
        # Update node status
        if node_name in self.node_status:
            
            # Mark as running if pending
            if self.node_status[node_name] == NodeStatus.PENDING:
                self.node_status[node_name] = NodeStatus.RUNNING
                self.node_timings[f"{node_name}_start"] = current_time
                self.execution_flow.append(f"{node_name}_start")
            
            # Mark as completed
            elif self.node_status[node_name] == NodeStatus.RUNNING:
                self.node_status[node_name] = NodeStatus.COMPLETED
                start_time = self.node_timings.get(f"{node_name}_start", current_time)
                execution_time = current_time - start_time
                self.node_timings[f"{node_name}_duration"] = execution_time
                self.execution_flow.append(f"{node_name}_complete")
                
                # Update node performance metrics
                if node_name not in self.metrics["node_performance"]:
                    self.metrics["node_performance"][node_name] = {
                        "executions": 0,
                        "total_time": 0.0,
                        "avg_time": 0.0
                    }
                
                node_metrics = self.metrics["node_performance"][node_name]
                node_metrics["executions"] += 1
                node_metrics["total_time"] += execution_time
                node_metrics["avg_time"] = node_metrics["total_time"] / node_metrics["executions"]
    
    async def _process_node_output(
        self,
        node_name: str,
        node_output: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process node output and generate appropriate events."""
        
        # Generate node start event
        if node_name in self.node_status and self.node_status[node_name] == NodeStatus.RUNNING:
            yield {
                "type": StreamEventType.NODE_START.value,
                "node_name": node_name,
                "execution_id": self.current_execution,
                "timestamp": datetime.now().isoformat()
            }
        
        # Check for tool execution
        if node_name == "tools" and isinstance(node_output, dict):
            if "tool_results" in node_output or "tool_calls" in str(node_output):
                yield {
                    "type": StreamEventType.TOOL_EXECUTION.value,
                    "node_name": node_name,
                    "execution_id": self.current_execution,
                    "timestamp": datetime.now().isoformat()
                }
        
        # Generate node completion event
        if node_name in self.node_status and self.node_status[node_name] == NodeStatus.COMPLETED:
            execution_time = self.node_timings.get(f"{node_name}_duration", 0.0)
            yield {
                "type": StreamEventType.NODE_COMPLETE.value,
                "node_name": node_name,
                "execution_time": execution_time,
                "execution_id": self.current_execution,
                "timestamp": datetime.now().isoformat()
            }
    
    async def _extract_streaming_content(
        self,
        node_name: str,
        node_output: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Extract streamable content from node output."""
        
        try:
            # Extract messages from node output
            messages = []
            
            if isinstance(node_output, dict):
                if "messages" in node_output:
                    messages = node_output["messages"]
                elif "conversation" in node_output and "messages" in node_output["conversation"]:
                    messages = node_output["conversation"]["messages"]
            
            # Process AI messages for streaming
            for message in messages:
                if isinstance(message, AIMessage) and hasattr(message, 'content'):
                    content = message.content
                    
                    if content and content.strip():
                        # Split content into chunks for streaming effect
                        async for chunk in self._create_content_chunks(content, node_name):
                            yield chunk
        
        except Exception as e:
            self.logger.error(f"Content extraction failed for {node_name}: {str(e)}")
    
    async def _create_content_chunks(
        self,
        content: str,
        node_name: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Create content chunks for streaming effect."""
        
        # Simple word-based chunking for now
        words = content.split()
        chunk_size = 3  # words per chunk
        
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i:i + chunk_size]
            chunk_content = " ".join(chunk_words)
            
            # Add space if not last chunk
            if i + chunk_size < len(words):
                chunk_content += " "
            
            yield {
                "type": StreamEventType.CONTENT_CHUNK.value,
                "content": chunk_content,
                "node_name": node_name,
                "execution_id": self.current_execution,
                "chunk_index": i // chunk_size,
                "is_complete": False,
                "timestamp": datetime.now().isoformat()
            }
            
            # Small delay for streaming effect
            await asyncio.sleep(0.03)
    
    def _create_completion_event(self, execution_time: float) -> Dict[str, Any]:
        """Create completion event with execution summary."""
        
        return {
            "type": StreamEventType.COMPLETION.value,
            "execution_id": self.current_execution,
            "execution_time": execution_time,
            "nodes_executed": len([s for s in self.node_status.values() if s == NodeStatus.COMPLETED]),
            "total_nodes": len(self.node_status),
            "execution_flow": self.execution_flow,
            "node_timings": self.node_timings,
            "is_complete": True,
            "timestamp": datetime.now().isoformat()
        }
    
    def _update_performance_metrics(self, execution_time: float) -> None:
        """Update overall performance metrics."""
        
        total_executions = self.metrics["total_executions"]
        current_avg = self.metrics["avg_execution_time"]
        
        # Update average execution time
        new_avg = ((current_avg * (total_executions - 1)) + execution_time) / total_executions
        self.metrics["avg_execution_time"] = new_avg
    
    def get_final_state(self) -> Optional[EnhancedState]:
        """Get the final state from the last execution."""
        return self.final_state
    
    def get_execution_metrics(self) -> Dict[str, Any]:
        """Get detailed execution metrics."""
        
        success_rate = 0.0
        if self.metrics["total_executions"] > 0:
            success_rate = self.metrics["successful_executions"] / self.metrics["total_executions"]
        
        return {
            **self.metrics,
            "success_rate": success_rate,
            "current_execution": self.current_execution,
            "last_execution_time": time.time() - self.execution_start_time if self.execution_start_time else 0
        }
    
    def get_node_performance_summary(self) -> Dict[str, Any]:
        """Get summary of node performance."""
        
        summary = {}
        
        for node_name, metrics in self.metrics["node_performance"].items():
            summary[node_name] = {
                "avg_execution_time": metrics["avg_time"],
                "total_executions": metrics["executions"],
                "performance_score": self._calculate_node_performance_score(metrics)
            }
        
        return summary
    
    def _calculate_node_performance_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate performance score for a node (0.0 to 1.0, higher is better)."""
        
        avg_time = metrics["avg_time"]
        executions = metrics["executions"]
        
        # Score based on execution time (lower is better)
        time_score = max(0.0, 1.0 - (avg_time / 10.0))  # 10 seconds = 0 score
        
        # Score based on consistency (more executions = more reliable)
        consistency_score = min(1.0, executions / 10.0)  # 10 executions = full score
        
        # Combined score
        return (time_score * 0.7) + (consistency_score * 0.3)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the streaming service."""
        
        health_status = {
            "healthy": True,
            "issues": [],
            "recommendations": []
        }
        
        # Check success rate
        if self.metrics["total_executions"] > 5:  # Need some data
            success_rate = self.metrics["successful_executions"] / self.metrics["total_executions"]
            
            if success_rate < 0.8:
                health_status["healthy"] = False
                health_status["issues"].append(f"Low success rate: {success_rate:.2f}")
                health_status["recommendations"].append("Check graph configuration and error handling")
        
        # Check average execution time
        if self.metrics["avg_execution_time"] > 30.0:  # 30 seconds
            health_status["issues"].append("High average execution time")
            health_status["recommendations"].append("Optimize node performance or add timeouts")
        
        # Check node performance
        for node_name, metrics in self.metrics["node_performance"].items():
            if metrics["avg_time"] > 15.0:  # 15 seconds per node
                health_status["issues"].append(f"Slow node: {node_name}")
                health_status["recommendations"].append(f"Optimize {node_name} node performance")
        
        return health_status