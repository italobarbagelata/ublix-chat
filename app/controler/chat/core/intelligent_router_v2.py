"""
Router Inteligente V2 - Versión mejorada con detección avanzada de intenciones.
Reemplaza la lógica básica con análisis contextual y corrección de errores.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

from .intent_detector import fuzzy_intent_detector, IntentCategory, IntentMatch
from .intelligent_router import IntelligentRouter as BaseRouter

logger = logging.getLogger(__name__)

@dataclass
class RoutingDecision:
    """Decisión de enrutamiento con explicación detallada."""
    route: str
    confidence: float
    tools_required: List[str]
    execution_mode: str  # 'sequential', 'parallel', 'conditional'
    reasoning: str
    intent_match: Optional[IntentMatch] = None
    fallback_applied: bool = False

class IntelligentRouterV2:
    """
    Router Inteligente V2 con capacidades avanzadas:
    - Detección de intenciones con corrección de errores
    - Análisis contextual de conversación
    - Decisiones de enrutamiento explicables
    - Fallback inteligente
    - Optimización de performance
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_router = BaseRouter()  # Mantener funcionalidad existente
        
        # Configuración de herramientas
        self.tool_categories = {
            'scheduling': ['agenda_tool_refactored', 'calendar', 'current_datetime_tool'],
            'contact': ['save_contact_tool'],
            'communication': ['email_tool'],
            'information': ['current_datetime_tool', 'week_info_tool', 'check_chile_holiday_tool'],
            'search': ['document_retriever', 'faq_retriever', 'unified_search_tool']
        }
        
        # Configuración de ejecución
        self.execution_strategies = {
            'sequential': {
                'description': 'Ejecutar herramientas una por una',
                'suitable_for': ['agenda_tool', 'save_contact', 'complex_workflows'],
                'max_tools': 3
            },
            'parallel': {
                'description': 'Ejecutar herramientas en paralelo',
                'suitable_for': ['search', 'information_gathering', 'validation'],
                'max_tools': 5
            },
            'conditional': {
                'description': 'Ejecutar según condiciones específicas',
                'suitable_for': ['error_handling', 'fallback_scenarios'],
                'max_tools': 2
            }
        }
    
    def route_from_state(self, state: Dict) -> RoutingDecision:
        """
        Enruta basado en el estado completo con análisis avanzado.
        
        Args:
            state: Estado del grafo con mensajes, herramientas, etc.
            
        Returns:
            RoutingDecision con la decisión de enrutamiento
        """
        try:
            # PASO 0: Detectar bucles de enrutamiento
            if self._detect_routing_loop(state):
                self.logger.warning("🔄 Bucle de enrutamiento detectado, forzando finalización")
                return self._fallback_decision("Bucle de enrutamiento detectado")
            
            # Extraer información del estado
            messages = state.get('messages', [])
            last_message = self._get_last_user_message(messages)
            conversation_history = self._extract_conversation_history(messages)
            
            if not last_message:
                return self._fallback_decision("No hay mensaje del usuario")
            
            # Verificar si ya se ejecutaron herramientas recientemente
            if self._has_recent_tool_execution(messages):
                self.logger.info("⚡ Herramientas ejecutadas recientemente, finalizando conversación")
                return RoutingDecision(
                    route='summarize_conversation',
                    confidence=1.0,
                    tools_required=[],
                    execution_mode='sequential',
                    reasoning="Herramientas ya ejecutadas en esta ronda",
                    intent_match=None,
                    fallback_applied=False
                )
            
            # PASO 1: Detectar intención con análisis avanzado
            intent_match = fuzzy_intent_detector.detect_intent(
                last_message, 
                conversation_history
            )
            
            self.logger.info(f"🎯 Intención detectada: {intent_match.category.value} (confianza: {intent_match.confidence:.2f})")
            
            # PASO 2: Determinar herramientas requeridas
            required_tools = self._determine_required_tools(intent_match, state)
            
            # PASO 3: Seleccionar estrategia de ejecución
            execution_strategy = self._select_execution_strategy(required_tools, intent_match)
            
            # PASO 4: Tomar decisión de enrutamiento
            routing_decision = self._make_routing_decision(
                intent_match, required_tools, execution_strategy, state
            )
            
            # PASO 5: Validar y aplicar fallback si es necesario
            validated_decision = self._validate_and_fallback(routing_decision, state)
            
            self.logger.info(f"🔀 Decisión de enrutamiento: {validated_decision.route} ({validated_decision.execution_mode})")
            self.logger.info(f"🔧 Herramientas: {validated_decision.tools_required}")
            
            return validated_decision
            
        except Exception as e:
            self.logger.error(f"Error en router inteligente V2: {str(e)}")
            return self._fallback_decision(f"Error: {str(e)}")
    
    def _get_last_user_message(self, messages: List) -> Optional[str]:
        """Extrae el último mensaje del usuario."""
        for message in reversed(messages):
            if hasattr(message, 'type') and message.type == 'human':
                return getattr(message, 'content', '')
            elif isinstance(message, dict) and message.get('type') == 'human':
                return message.get('content', '')
        return None
    
    def _extract_conversation_history(self, messages: List) -> List[str]:
        """Extrae historial de conversación para análisis contextual."""
        history = []
        for message in messages[-10:]:  # Últimos 10 mensajes
            content = ""
            if hasattr(message, 'content'):
                content = message.content
            elif isinstance(message, dict):
                content = message.get('content', '')
            
            if content and isinstance(content, str):
                history.append(content)
        
        return history
    
    def _determine_required_tools(self, intent_match: IntentMatch, state: Dict) -> List[str]:
        """Determina herramientas requeridas basado en intención y contexto."""
        
        # Herramientas base según intención
        base_tools = fuzzy_intent_detector.get_required_tools(intent_match)
        
        # Análisis contextual para herramientas adicionales
        additional_tools = []
        
        # Si es agendamiento, verificar si necesitamos contacto
        if intent_match.category in [IntentCategory.BOOKING, IntentCategory.SCHEDULE_CONFIRM]:
            # Verificar si ya tenemos información de contacto
            messages = state.get('messages', [])
            has_contact_info = self._has_contact_info_in_conversation(messages)
            
            if not has_contact_info:
                additional_tools.append('save_contact_tool')
        
        # Si menciona fechas/horarios específicos, agregar herramientas temporales
        last_message = self._get_last_user_message(state.get('messages', []))
        if last_message and self._mentions_specific_time(last_message):
            additional_tools.extend(['current_datetime_tool', 'week_info_tool'])
        
        # Combinar y deduplicar
        all_tools = list(set(base_tools + additional_tools))
        
        # Filtrar herramientas disponibles en el proyecto
        available_tools = self._filter_available_tools(all_tools, state)
        
        return available_tools
    
    def _has_contact_info_in_conversation(self, messages: List) -> bool:
        """Verifica si ya hay información de contacto en la conversación."""
        contact_indicators = ['nombre', 'email', 'teléfono', 'telefono', 'contacto', '@']
        
        for message in messages[-5:]:  # Verificar últimos 5 mensajes
            content = ""
            if hasattr(message, 'content'):
                content = message.content.lower()
            elif isinstance(message, dict):
                content = message.get('content', '').lower()
            
            if any(indicator in content for indicator in contact_indicators):
                return True
        
        return False
    
    def _mentions_specific_time(self, text: str) -> bool:
        """Verifica si el texto menciona horarios específicos."""
        time_patterns = [
            r'\b\d{1,2}:\d{2}\b',  # HH:MM
            r'\b\d{1,2}\s*(am|pm|hrs|horas)\b',  # 2 PM, 14 hrs
            r'\b(mañana|tarde|noche)\b',
            r'\b(lunes|martes|miércoles|jueves|viernes|sábado|domingo)\b'
        ]
        
        import re
        for pattern in time_patterns:
            if re.search(pattern, text.lower()):
                return True
        
        return False
    
    def _filter_available_tools(self, tools: List[str], state: Dict) -> List[str]:
        """Filtra herramientas según disponibilidad en el proyecto."""
        # Obtener herramientas disponibles del estado o proyecto
        available_tools = []
        
        # En el futuro, esto vendría del estado o configuración del proyecto
        # Por ahora, usar lista predeterminada
        default_available = [
            'agenda_tool_refactored', 'save_contact_tool', 'current_datetime_tool',
            'week_info_tool', 'check_chile_holiday_tool', 'test_calendar_connectivity'
        ]
        
        for tool in tools:
            if tool in default_available:
                available_tools.append(tool)
        
        return available_tools
    
    def _select_execution_strategy(self, tools: List[str], intent_match: IntentMatch) -> str:
        """Selecciona estrategia de ejecución basada en herramientas e intención."""
        
        # Para agendamiento, siempre secuencial
        if intent_match.category in [IntentCategory.BOOKING, IntentCategory.SCHEDULE_CONFIRM]:
            return 'sequential'
        
        # Para consultas simples, paralelo si es posible
        if intent_match.category == IntentCategory.SCHEDULE_INQUIRY:
            if len(tools) <= 2:
                return 'parallel'
            else:
                return 'sequential'
        
        # Para herramientas bloqueantes, secuencial
        blocking_tools = ['save_contact_tool', 'agenda_tool_refactored']
        if any(tool in blocking_tools for tool in tools):
            return 'sequential'
        
        # Default: paralelo para múltiples herramientas de información
        if len(tools) > 1:
            return 'parallel'
        
        return 'sequential'
    
    def _make_routing_decision(self, intent_match: IntentMatch, tools: List[str], 
                             execution_strategy: str, state: Dict) -> RoutingDecision:
        """Toma la decisión final de enrutamiento."""
        
        # Mapear estrategia a ruta
        route_mapping = {
            'sequential': 'tools_sequential',
            'parallel': 'tools_parallel',
            'conditional': 'tools_conditional'
        }
        
        route = route_mapping.get(execution_strategy, 'tools_sequential')
        
        # Lógica simplificada: SIEMPRE permitir que el agent maneje si hay pocas herramientas o conversación corta
        messages = state.get('messages', [])
        conversation_length = len(messages)
        
        # Para conversaciones cortas (≤ 4 mensajes), SIEMPRE ir a tools
        if conversation_length <= 4:
            if not tools:
                tools = ['current_datetime_tool']  # Herramienta básica para contexto
            route = 'tools_sequential'
            reasoning = f"Conversación corta ({conversation_length} mensajes) - permitir agent"
        # Para conversaciones más largas, evaluar según herramientas e intención
        elif not tools:
            route = 'summarize_conversation'
            reasoning = "No se requieren herramientas específicas"
        elif intent_match.confidence < 0.1 and intent_match.category == IntentCategory.UNKNOWN:
            # Solo ir a resumen si realmente no hay nada claro
            route = 'summarize_conversation'
            reasoning = f"Muy baja confianza en intención ({intent_match.confidence:.2f})"
        else:
            reasoning = f"Intención {intent_match.category.value} detectada con {len(tools)} herramientas"
        
        return RoutingDecision(
            route=route,
            confidence=intent_match.confidence,
            tools_required=tools,  # tools ya fue actualizado arriba si era necesario
            execution_mode=execution_strategy,
            reasoning=reasoning,
            intent_match=intent_match,
            fallback_applied=False
        )
    
    def _validate_and_fallback(self, decision: RoutingDecision, state: Dict) -> RoutingDecision:
        """Valida la decisión y aplica fallback si es necesario."""
        
        # Validación 1: Verificar que las herramientas sean válidas
        if decision.tools_required:
            valid_tools = self._validate_tools(decision.tools_required)
            if not valid_tools:
                self.logger.warning("Ninguna herramienta válida encontrada, aplicando fallback")
                return self._fallback_decision("Herramientas no válidas")
        
        # Validación 2: Verificar coherencia de ruta y herramientas
        if decision.route.startswith('tools') and not decision.tools_required:
            self.logger.warning("Ruta de herramientas sin herramientas, aplicando fallback")
            return self._fallback_decision("Incoherencia ruta-herramientas")
        
        # Validación 3: Límite de herramientas por estrategia
        max_tools = self.execution_strategies.get(decision.execution_mode, {}).get('max_tools', 5)
        if len(decision.tools_required) > max_tools:
            self.logger.warning(f"Demasiadas herramientas ({len(decision.tools_required)} > {max_tools})")
            decision.tools_required = decision.tools_required[:max_tools]
            decision.reasoning += f" (limitado a {max_tools} herramientas)"
        
        return decision
    
    def _validate_tools(self, tools: List[str]) -> bool:
        """Valida que las herramientas sean accesibles."""
        # En el futuro, esto verificaría contra configuración real del proyecto
        valid_tool_names = [
            'agenda_tool_refactored', 'save_contact_tool', 'current_datetime_tool',
            'week_info_tool', 'check_chile_holiday_tool', 'test_calendar_connectivity'
        ]
        
        return any(tool in valid_tool_names for tool in tools)
    
    def _detect_routing_loop(self, state: Dict) -> bool:
        """Detecta bucles de enrutamiento analizando patrones específicos de mensajes."""
        messages = state.get('messages', [])
        
        if len(messages) < 4:  # Necesitamos al menos 4 mensajes para detectar un patrón
            return False
        
        # Contar diferentes tipos de mensajes en los últimos 6 mensajes
        recent_messages = messages[-6:]
        ai_with_tools_count = 0
        tool_response_count = 0
        ai_without_tools_count = 0
        human_count = 0
        
        for message in recent_messages:
            if hasattr(message, 'type'):
                if message.type == 'ai' and hasattr(message, 'tool_calls') and message.tool_calls:
                    ai_with_tools_count += 1
                elif message.type == 'ai':
                    ai_without_tools_count += 1
                elif message.type == 'tool':
                    tool_response_count += 1
                elif message.type == 'human':
                    human_count += 1
        
        # Detectar patrones específicos de bucle:
        # 1. Muchos tool calls sin respuestas completas de AI
        if ai_with_tools_count >= 3 and ai_without_tools_count == 0:
            self.logger.warning(f"🔍 Patrón de bucle detectado: {ai_with_tools_count} AI con tools, {ai_without_tools_count} AI sin tools")
            return True
        
        # 2. Ratio anormal de tool calls vs mensajes humanos
        if ai_with_tools_count >= 2 and human_count <= 1:
            self.logger.warning(f"🔍 Ratio anormal detectado: {ai_with_tools_count} tool calls, {human_count} mensajes humanos")
            return True
        
        # 3. Verificar duplicación de tool calls (mismo tool llamado múltiples veces seguidas)
        last_tool_calls = []
        for message in reversed(recent_messages[-3:]):  # Solo últimos 3 mensajes
            if (hasattr(message, 'type') and message.type == 'ai' and 
                hasattr(message, 'tool_calls') and message.tool_calls):
                for tc in message.tool_calls:
                    if hasattr(tc, 'function') and hasattr(tc.function, 'name'):
                        last_tool_calls.append(tc.function.name)
                    elif isinstance(tc, dict) and 'function' in tc:
                        last_tool_calls.append(tc['function'].get('name', 'unknown'))
        
        # Si hay 2 o más llamadas al mismo tool consecutivas
        if len(last_tool_calls) >= 2:
            for i in range(len(last_tool_calls) - 1):
                if last_tool_calls[i] == last_tool_calls[i + 1]:
                    self.logger.warning(f"🔍 Tool duplicado detectado: {last_tool_calls[i]}")
                    return True
        
        return False
    
    def _has_recent_tool_execution(self, messages: List) -> bool:
        """
        Verifica si se ejecutaron herramientas recientemente Y si el AI ya respondió.
        Solo retorna True si hay tool results Y una respuesta AI subsecuente.
        """
        if len(messages) < 3:
            return False
        
        # Buscar en los últimos 4 mensajes un patrón completo:
        # AI con tool_calls -> ToolMessage -> AI response
        recent_messages = messages[-4:]
        
        has_tool_result = False
        has_ai_response_after_tools = False
        
        for i, message in enumerate(recent_messages):
            # Encontrar ToolMessage (resultado de herramienta)
            if hasattr(message, 'type') and message.type == 'tool':
                has_tool_result = True
                
                # Verificar si hay una respuesta AI después del ToolMessage
                for j in range(i + 1, len(recent_messages)):
                    next_msg = recent_messages[j]
                    if (hasattr(next_msg, 'type') and next_msg.type == 'ai' and
                        (not hasattr(next_msg, 'tool_calls') or not next_msg.tool_calls)):
                        has_ai_response_after_tools = True
                        break
        
        # Solo considerar que las herramientas fueron ejecutadas completamente
        # si hay tanto result como respuesta AI
        return has_tool_result and has_ai_response_after_tools
    
    def _fallback_decision(self, reason: str) -> RoutingDecision:
        """Crea decisión de fallback cuando falla la detección principal."""
        self.logger.warning(f"Aplicando fallback: {reason}")
        
        return RoutingDecision(
            route='summarize_conversation',
            confidence=0.0,
            tools_required=[],
            execution_mode='sequential',
            reasoning=f"Fallback aplicado: {reason}",
            intent_match=None,
            fallback_applied=True
        )
    
    def get_routing_stats(self) -> Dict[str, any]:
        """Obtiene estadísticas del router para monitoreo."""
        return {
            'version': '2.0',
            'features': [
                'fuzzy_intent_detection',
                'typo_correction',
                'contextual_analysis',
                'explainable_decisions',
                'smart_fallback'
            ],
            'supported_intents': [intent.value for intent in IntentCategory],
            'execution_strategies': list(self.execution_strategies.keys())
        }

# Instancia global del router mejorado
intelligent_router_v2 = IntelligentRouterV2()