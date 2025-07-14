import logging
import time
from typing import Literal, Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass
from app.controler.chat.core.state import CustomState

class RouteType(Enum):
    """Tipos de rutas disponibles en el grafo"""
    TOOLS_SEQUENTIAL = "tools_sequential"
    TOOLS_PARALLEL = "tools_parallel"
    RESPONSE_VALIDATOR = "response_validator"
    CONTEXT_MANAGER = "context_manager"
    SUMMARIZE_CONVERSATION = "summarize_conversation"
    ERROR_HANDLER = "error_handler"
    QUALITY_CHECKER = "quality_checker"
    END = "end"

@dataclass
class RoutingContext:
    """Contexto para decisiones de enrutamiento"""
    message_complexity: float = 0.0
    tool_types: List[str] = None
    user_urgency: float = 0.0
    system_load: float = 0.0
    conversation_depth: int = 0
    error_history: List[str] = None
    
    def __post_init__(self):
        if self.tool_types is None:
            self.tool_types = []
        if self.error_history is None:
            self.error_history = []

class IntelligentRouter:
    """
    Sistema de enrutamiento inteligente para el grafo de LangGraph.
    
    Características:
    - Análisis de complejidad de mensajes
    - Enrutamiento basado en tipos de herramientas
    - Paralelización automática de tareas independientes
    - Validación de calidad de respuestas
    - Manejo inteligente de errores
    - Optimización basada en carga del sistema
    """
    
    def __init__(self):
        self.route_stats = {}
        self.parallelizable_tools = {
            'search', 'calendar', 'email', 'api_tool', 'document_retriever',
            'faq_retriever', 'products_search', 'openai_vector'
        }
        self.blocking_tools = {
            'save_contact_tool', 'agenda_tool', 'image_processor', 'mongo_db_tool'
        }
        self.critical_tools = {
            'save_contact_tool', 'agenda_tool', 'send_email'
        }
    
    def route_from_agent(self, state: CustomState) -> Literal[
        "tools_sequential", "tools_parallel", "context_manager", 
        "response_validator", "summarize_conversation", "end"
    ]:
        """
        Ruta principal desde el nodo agent. Decide el siguiente paso basado en análisis inteligente.
        
        Args:
            state: Estado actual del grafo
            
        Returns:
            Nombre del siguiente nodo
        """
        messages = state["messages"]
        last_message = messages[-1]
        
        # Si no hay tool calls, ir directo a validación o resumen
        if not last_message.tool_calls:
            return self._route_no_tools(state)
        
        # Analizar contexto para decisión de enrutamiento
        routing_context = self._analyze_routing_context(state)
        
        # Decidir tipo de ejecución de herramientas
        if self._should_use_parallel_execution(routing_context):
            logging.info(f"🔀 Enrutamiento inteligente: ejecución PARALELA de {len(routing_context.tool_types)} herramientas")
            return "tools_parallel"
        elif self._requires_context_management(routing_context):
            logging.info("🔀 Enrutamiento inteligente: gestión de CONTEXTO requerida")
            return "context_manager"
        else:
            logging.info(f"🔀 Enrutamiento inteligente: ejecución SECUENCIAL de herramientas")
            return "tools_sequential"
    
    def route_from_tools(self, state: CustomState) -> Literal[
        "agent", "response_validator", "quality_checker", "error_handler"
    ]:
        """
        Ruta desde nodos de herramientas. Decide si validar respuesta o continuar.
        
        Args:
            state: Estado actual del grafo
            
        Returns:
            Nombre del siguiente nodo
        """
        # Analizar la calidad de la respuesta de las herramientas
        tool_response_quality = self._analyze_tool_response_quality(state)
        
        if tool_response_quality < 0.6:
            logging.warning("🔍 Respuesta de herramientas de baja calidad, enviando a validador")
            return "quality_checker"
        elif tool_response_quality > 0.9:
            logging.info("✅ Respuesta de herramientas de alta calidad, continuando")
            return "agent"
        else:
            # Verificar si necesita validación adicional
            if self._requires_response_validation(state):
                logging.info("🔍 Enviando respuesta a validador")
                return "response_validator"
            else:
                return "agent"
    
    def route_from_validator(self, state: CustomState) -> Literal[
        "agent", "tools_sequential", "quality_checker", "summarize_conversation"
    ]:
        """
        Ruta desde el validador de respuestas.
        
        Args:
            state: Estado actual del grafo
            
        Returns:
            Nombre del siguiente nodo
        """
        validation_result = self._get_validation_result(state)
        
        if validation_result.get("requires_retry", False):
            logging.warning("🔄 Validación falló, reintentando con herramientas")
            return "tools_sequential"
        elif validation_result.get("requires_quality_check", False):
            logging.info("🔍 Enviando a checker de calidad")
            return "quality_checker"
        elif validation_result.get("is_valid", True):
            logging.info("✅ Validación exitosa, continuando")
            return "agent"
        else:
            logging.info("📝 Respuesta completa, enviando a resumen")
            return "summarize_conversation"
    
    def _route_no_tools(self, state: CustomState) -> str:
        """Decide ruta cuando no hay tool calls"""
        messages = state["messages"]
        
        # Verificar si la respuesta necesita validación
        if len(messages) > 20:
            return "summarize_conversation"
        elif self._response_needs_validation(state):
            return "response_validator"
        else:
            return "summarize_conversation"
    
    def _analyze_routing_context(self, state: CustomState) -> RoutingContext:
        """Analiza el contexto para decisiones de enrutamiento"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # Extraer tipos de herramientas
        tool_types = []
        if last_message.tool_calls:
            tool_types = [call.get("name", "") for call in last_message.tool_calls]
        
        # Calcular complejidad del mensaje
        message_complexity = self._calculate_message_complexity(state)
        
        # Calcular urgencia del usuario
        user_urgency = self._calculate_user_urgency(state)
        
        # Estimar carga del sistema
        system_load = self._estimate_system_load()
        
        # Profundidad de conversación
        conversation_depth = len(messages)
        
        # Historial de errores recientes
        error_history = self._get_recent_errors(state)
        
        return RoutingContext(
            message_complexity=message_complexity,
            tool_types=tool_types,
            user_urgency=user_urgency,
            system_load=system_load,
            conversation_depth=conversation_depth,
            error_history=error_history
        )
    
    def _should_use_parallel_execution(self, context: RoutingContext) -> bool:
        """Decide si usar ejecución paralela de herramientas"""
        # No usar paralelización si hay herramientas bloqueantes
        if any(tool in self.blocking_tools for tool in context.tool_types):
            return False
        
        # No usar paralelización si hay alta urgencia y pocas herramientas
        if context.user_urgency > 0.8 and len(context.tool_types) <= 2:
            return False
        
        # Usar paralelización si todas las herramientas son paralelizables
        if len(context.tool_types) >= 2:
            parallelizable_count = sum(
                1 for tool in context.tool_types 
                if tool in self.parallelizable_tools
            )
            return parallelizable_count >= 2
        
        return False
    
    def _requires_context_management(self, context: RoutingContext) -> bool:
        """Decide si se requiere gestión especial de contexto"""
        # Requerir gestión de contexto para conversaciones muy profundas
        if context.conversation_depth > 30:
            return True
        
        # Requerir para alta complejidad de mensaje
        if context.message_complexity > 0.8:
            return True
        
        # Requerir si hay herramientas críticas
        if any(tool in self.critical_tools for tool in context.tool_types):
            return True
        
        return False
    
    def _calculate_message_complexity(self, state: CustomState) -> float:
        """Calcula la complejidad del mensaje actual"""
        messages = state["messages"]
        if not messages:
            return 0.0
        
        last_message = messages[-1]
        
        # Factores de complejidad
        complexity_factors = []
        
        # Número de tool calls
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            complexity_factors.append(min(len(last_message.tool_calls) / 5.0, 1.0))
        
        # Longitud del contenido
        if hasattr(last_message, 'content') and last_message.content:
            content_length = len(str(last_message.content))
            complexity_factors.append(min(content_length / 1000.0, 1.0))
        
        # Diversidad de tipos de herramientas
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            unique_tools = len(set(call.get("name", "") for call in last_message.tool_calls))
            complexity_factors.append(min(unique_tools / 3.0, 1.0))
        
        # Promedio de factores
        if complexity_factors:
            return sum(complexity_factors) / len(complexity_factors)
        
        return 0.0
    
    def _calculate_user_urgency(self, state: CustomState) -> float:
        """Calcula la urgencia percibida del usuario"""
        messages = state.get("messages", [])
        if not messages:
            return 0.0
        
        # Palabras que indican urgencia
        urgency_keywords = [
            'urgente', 'rápido', 'inmediato', 'ya', 'ahora', 
            'pronto', 'cuanto antes', 'emergen', 'crítico'
        ]
        
        urgency_score = 0.0
        recent_messages = messages[-3:]  # Últimos 3 mensajes
        
        for message in recent_messages:
            if hasattr(message, 'content') and message.content:
                content = str(message.content).lower()
                urgency_count = sum(1 for keyword in urgency_keywords if keyword in content)
                urgency_score += min(urgency_count / 3.0, 1.0)
        
        return min(urgency_score / len(recent_messages), 1.0) if recent_messages else 0.0
    
    def _estimate_system_load(self) -> float:
        """Estima la carga actual del sistema"""
        # Implementación simplificada
        # En un entorno real, esto podría usar métricas del sistema
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            return (cpu_percent + memory_percent) / 200.0  # Normalizar a [0,1]
        except ImportError:
            # Fallback: usar timestamp para simular carga variable
            return (time.time() % 100) / 100.0
    
    def _get_recent_errors(self, state: CustomState) -> List[str]:
        """Obtiene errores recientes del contexto"""
        # Buscar en el estado errores recientes
        # Esto dependería de cómo se almacenan los errores en el estado
        return []
    
    def _analyze_tool_response_quality(self, state: CustomState) -> float:
        """Analiza la calidad de las respuestas de herramientas"""
        messages = state.get("messages", [])
        if not messages:
            return 0.5
        
        last_message = messages[-1]
        
        # Factores de calidad
        quality_factors = []
        
        # Verificar si hay contenido
        if hasattr(last_message, 'content') and last_message.content:
            content = str(last_message.content)
            
            # Longitud razonable
            if 50 <= len(content) <= 2000:
                quality_factors.append(1.0)
            elif len(content) < 10:
                quality_factors.append(0.2)
            else:
                quality_factors.append(0.7)
            
            # Presencia de información estructurada
            if any(pattern in content.lower() for pattern in ['http', 'email', 'teléfono', 'fecha']):
                quality_factors.append(0.9)
            
            # Ausencia de errores obvios
            error_indicators = ['error', 'falló', 'no encontrado', 'no disponible']
            if not any(indicator in content.lower() for indicator in error_indicators):
                quality_factors.append(0.8)
            else:
                quality_factors.append(0.3)
        
        # Promedio de factores de calidad
        if quality_factors:
            return sum(quality_factors) / len(quality_factors)
        
        return 0.5
    
    def _requires_response_validation(self, state: CustomState) -> bool:
        """Decide si la respuesta requiere validación adicional"""
        routing_context = self._analyze_routing_context(state)
        
        # Validar respuestas de herramientas críticas
        if any(tool in self.critical_tools for tool in routing_context.tool_types):
            return True
        
        # Validar si hay alta urgencia del usuario
        if routing_context.user_urgency > 0.7:
            return True
        
        # Validar mensajes complejos
        if routing_context.message_complexity > 0.6:
            return True
        
        return False
    
    def _response_needs_validation(self, state: CustomState) -> bool:
        """Verifica si una respuesta sin herramientas necesita validación"""
        messages = state.get("messages", [])
        if not messages:
            return False
        
        last_message = messages[-1]
        
        # Validar respuestas muy cortas o muy largas
        if hasattr(last_message, 'content') and last_message.content:
            content_length = len(str(last_message.content))
            if content_length < 20 or content_length > 3000:
                return True
        
        return False
    
    def _get_validation_result(self, state: CustomState) -> Dict[str, Any]:
        """Obtiene resultado de validación del estado"""
        # Esto dependería de cómo se almacena el resultado de validación
        # Por ahora, retorna un resultado mock
        return {
            "is_valid": True,
            "requires_retry": False,
            "requires_quality_check": False,
            "confidence": 0.8
        }
    
    def get_routing_analytics(self) -> Dict[str, Any]:
        """Obtiene analíticas del sistema de enrutamiento"""
        return {
            "total_routes": sum(self.route_stats.values()),
            "route_distribution": self.route_stats.copy(),
            "parallelizable_tools_count": len(self.parallelizable_tools),
            "blocking_tools_count": len(self.blocking_tools),
            "critical_tools_count": len(self.critical_tools)
        }

# Instancia global del router inteligente
intelligent_router = IntelligentRouter()