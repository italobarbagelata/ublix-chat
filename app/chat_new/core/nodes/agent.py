"""
Enhanced Agent Node - Advanced Conversational Agent

The AgentNode provides sophisticated conversational capabilities with:
1. Context-aware response generation
2. Dynamic prompt construction
3. Tool integration with intelligent selection
4. Multi-modal input handling
5. Personality and style consistency
6. Response quality monitoring
7. Fallback strategies for complex scenarios

This agent leverages the enhanced state system for optimal performance.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import pytz

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..state import (
    EnhancedState, 
    RouteType, 
    IntentCategory,
    update_conversation_state,
    add_error,
    ErrorSeverity
)
from app.controler.chat.core.llm_adapter import LLMAdapter
from app.controler.chat.core.utils import decorate_message
from ..utils import filter_and_prepare_messages_for_enhanced_agent, ensure_message_compatibility
from app.resources.constants import DEFAULT_PROMPT, MODEL_CHATBOT


class AgentNode:
    """
    Enhanced conversational agent with advanced capabilities.
    
    Features:
    - Context-aware prompt generation
    - Dynamic tool binding based on routing
    - Multi-strategy response generation
    - Quality assessment and refinement
    - Personality consistency
    - Fallback handling
    """
    
    def __init__(self, model_name: str = MODEL_CHATBOT):
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name
        self.timezone = pytz.timezone('America/Santiago')
        
        # Response quality thresholds
        self.min_response_length = 10
        self.max_response_length = 2000
        
        # Fallback strategies
        self.fallback_responses = {
            IntentCategory.GREETING: "¡Hola! Es un gusto saludarte. ¿En qué puedo ayudarte hoy?",
            IntentCategory.SUPPORT: "Estoy aquí para ayudarte. ¿Podrías contarme más detalles sobre lo que necesitas?",
            IntentCategory.GENERAL: "Entiendo. ¿Puedes darme más información para poder ayudarte mejor?"
        }
    
    def __call__(self, state: EnhancedState) -> EnhancedState:
        """
        Main agent execution logic with enhanced context handling.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state with agent response
        """
        try:
            # CRÍTICO: Normalizar estado al inicio para prevenir warnings Pydantic
            from ..utils import normalize_state_messages
            state = normalize_state_messages(state)
            
            self.logger.info(f"{state['unique_id']} AgentNode: Starting enhanced agent processing")
            
            # Step 1: Prepare execution context
            context = self._prepare_execution_context(state)
            
            # Step 2: Build dynamic prompt
            system_prompt = self._build_dynamic_prompt(state, context)
            
            # Step 3: Prepare messages
            messages = self._prepare_messages(state, system_prompt)
            
            # Step 4: Get available tools based on routing
            tools = self._get_tools_for_route(state)
            
            # Step 5: Generate response
            response = self._generate_response(state, messages, tools, context)
            
            # Step 6: Validate and enhance response
            enhanced_response = self._enhance_response(state, response, context)
            
            # Step 7: Update state with response
            state = self._update_state_with_response(state, enhanced_response)
            
            self.logger.info(f"{state['unique_id']} AgentNode: Enhanced agent processing completed")
            return state
            
        except Exception as e:
            self.logger.error(f"{state['unique_id']} AgentNode error: {str(e)}", exc_info=True)
            
            # Use fallback response
            fallback_response = self._get_fallback_response(state)
            state = self._update_state_with_response(state, fallback_response)
            state = add_error(state, e, "Agent processing", ErrorSeverity.HIGH)
            
            return state
    
    def _prepare_execution_context(self, state: EnhancedState) -> Dict[str, Any]:
        """
        Prepare comprehensive execution context for the agent.
        
        Args:
            state: Current enhanced state
            
        Returns:
            Dict with execution context
        """
        
        # Calculate current time in Chile timezone
        utc_now = datetime.now(pytz.UTC)
        chile_time = utc_now.astimezone(self.timezone)
        
        # Build date range for next 15 days
        date_range = []
        for i in range(15):
            future_date = chile_time.date() + pytz.datetime.timedelta(days=i)
            date_range.append(future_date.strftime('%Y-%m-%d'))
        
        # Extract user context
        user_info = state["user"]
        routing_info = state["routing"]
        conversation_info = state["conversation"]
        
        # Build context
        context = {
            # Temporal context
            "current_time": chile_time.isoformat(),
            "timezone": "America/Santiago",
            "date_range": ", ".join(date_range),
            
            # User context
            "user_id": user_info["user_id"],
            "username": user_info["username"],
            "source": user_info["source"],
            "contact_info": user_info["contact_info"],
            "user_preferences": user_info["user_preferences"],
            
            # Project context
            "project": user_info["project"],
            "project_name": user_info["project"].name,
            "personality": getattr(user_info["project"], "personality", ""),
            "instructions": getattr(user_info["project"], "instructions", ""),
            "enabled_tools": getattr(user_info["project"], "enabled_tools", []),
            
            # Conversation context
            "conversation_summary": conversation_info["summary"],
            "turn_count": conversation_info["turn_count"],
            "intent_category": routing_info["intent_category"],
            "current_route": routing_info["current_route"],
            "confidence_score": routing_info["confidence_score"],
            
            # Session context
            "session_metadata": user_info["session_metadata"],
            
            # Execution context
            "unique_id": state["unique_id"],
            "conversation_id": conversation_info["conversation_id"]
        }
        
        return context
    
    def _build_dynamic_prompt(self, state: EnhancedState, context: Dict[str, Any]) -> str:
        """
        Build a dynamic system prompt based on context and routing.
        
        Args:
            state: Current enhanced state
            context: Execution context
            
        Returns:
            str: Dynamic system prompt
        """
        
        # Start with base prompt template
        project = context["project"]
        base_prompt = getattr(project, "prompt", DEFAULT_PROMPT)
        
        # Replace standard placeholders
        prompt = base_prompt.replace("{name}", context["project_name"])
        prompt = prompt.replace("{personality}", context["personality"])
        prompt = prompt.replace("{instructions}", context["instructions"])
        prompt = prompt.replace("{utc_now}", context["current_time"])
        prompt = prompt.replace("{date_range_str}", context["date_range"])
        prompt = prompt.replace("{now_chile}", context["current_time"])
        
        # Add conversation summary if available
        if context["conversation_summary"]:
            summary_section = f"""
            RESUMEN DE CONVERSACIÓN ANTERIOR:
            
            {context["conversation_summary"]}
            
            IMPORTANTE: Usa esta información para NO repetir preguntas que ya fueron respondidas.
            """
            prompt += summary_section
        
        # Add context-specific instructions based on routing
        route_specific = self._get_route_specific_instructions(state, context)
        if route_specific:
            prompt += f"\n\n{route_specific}"
        
        # Add tool-specific instructions
        tool_instructions = self._get_tool_instructions(context["enabled_tools"])
        if tool_instructions:
            prompt += f"\n\n{tool_instructions}"
        
        # Add user context if available
        user_context = self._get_user_context_instructions(context)
        if user_context:
            prompt += f"\n\n{user_context}"
        
        # Add quality guidelines
        quality_guidelines = self._get_quality_guidelines(context)
        prompt += f"\n\n{quality_guidelines}"
        
        return prompt
    
    def _get_route_specific_instructions(self, state: EnhancedState, context: Dict[str, Any]) -> str:
        """Get instructions specific to the current route."""
        
        route = context["current_route"]
        intent = context["intent_category"]
        
        instructions = ""
        
        if route == RouteType.TOOL_EXECUTION:
            instructions += """
            MODO EJECUCIÓN DE HERRAMIENTAS:
            - Tienes acceso a herramientas especializadas para esta consulta
            - Usa las herramientas apropiadas para proporcionar respuestas precisas
            - Explica claramente qué herramientas estás usando y por qué
            - Si una herramienta falla, intenta alternativas o explica la limitación
            """
        
        elif route == RouteType.COMPLEX_WORKFLOW:
            instructions += """
            MODO FLUJO COMPLEJO:
            - Esta consulta requiere múltiples pasos o validaciones
            - Divide el proceso en pasos claros y explícalos al usuario
            - Solicita confirmación antes de acciones importantes
            - Mantén al usuario informado del progreso
            """
        
        elif route == RouteType.CONTEXT_RETRIEVAL:
            instructions += """
            MODO RECUPERACIÓN DE CONTEXTO:
            - Necesitas más información para responder adecuadamente
            - Haz preguntas específicas y útiles
            - Explica por qué necesitas esa información
            - Ofrece opciones o ejemplos cuando sea apropiado
            """
        
        # Add intent-specific instructions
        if intent == IntentCategory.BOOKING:
            instructions += """
            
            MANEJO DE AGENDAMIENTO:
            - Recopila toda la información necesaria antes de agendar
            - Valida fechas y horarios disponibles
            - Confirma detalles antes de crear la cita
            - Proporciona información clara sobre la cita creada
            """
        
        elif intent == IntentCategory.PRODUCT_INQUIRY:
            instructions += """
            
            CONSULTAS DE PRODUCTOS:
            - Busca productos específicos cuando sea posible
            - Proporciona información detallada y precisa
            - Sugiere alternativas si el producto buscado no está disponible
            - Incluye precios y disponibilidad cuando esté disponible
            """
        
        return instructions.strip()
    
    def _get_tool_instructions(self, enabled_tools: List[str]) -> str:
        """Get instructions for available tools."""
        
        instructions = "HERRAMIENTAS DISPONIBLES:\n"
        
        # Core tools (always available)
        instructions += """
        📅 FECHA Y HORA:
        - current_datetime_tool: Obtener fecha y hora actual
        - week_info_tool: Información sobre el día de la semana
        - check_chile_holiday_tool: Verificar si una fecha es feriado en Chile
        - next_chile_holidays_tool: Próximos feriados
        
        👤 GESTIÓN DE CONTACTOS:
        - save_contact_tool: Guardar y gestionar información de contacto del usuario
        """
        
        # Conditional tools based on enabled_tools
        if "unified_search" in enabled_tools:
            instructions += """
        
        🔍 BÚSQUEDA UNIFICADA:
        - unified_search_tool: Búsqueda principal en documentos, FAQs y productos
          USO: Para cualquier consulta de información, úsala ANTES de responder desde conocimiento general
        """
        
        if "agenda_tool" in enabled_tools or "agenda_smart_booking_tool" in enabled_tools:
            instructions += """
        
        📅 AGENDAMIENTO:
        - agenda_tool: Gestión completa de horarios y agendamiento
          FLUJO: 1) Buscar horarios disponibles, 2) Confirmar detalles, 3) Agendar cita
        """
        
        if "email" in enabled_tools:
            instructions += """
        
        📧 EMAIL:
        - send_email: Envío de correos electrónicos
          PARÁMETROS: from_email (por defecto: noreply@ublix.app), to, subject, html/text
        """
        
        if "api" in enabled_tools:
            instructions += """
        
        🔌 API TOOLS:
        - Herramientas API dinámicas específicas del proyecto
        - Configuradas según las necesidades del proyecto
        """
        
        if "products_search" in enabled_tools:
            instructions += """
        
        🛍️ PRODUCTOS:
        - search_products_unified: Búsqueda en catálogo de productos
        """
        
        if "image_processor" in enabled_tools:
            instructions += """
        
        🖼️ PROCESAMIENTO DE IMÁGENES:
        - image_processor: Análisis y procesamiento de imágenes
        """
        
        if "mongo_db" in enabled_tools:
            instructions += """
        
        🗄️ BASE DE DATOS:
        - mongo_db_tool: Operaciones en base de datos MongoDB
        """
        
        return instructions
    
    def _get_user_context_instructions(self, context: Dict[str, Any]) -> str:
        """Get instructions based on user context."""
        
        instructions = ""
        
        # Add contact info context
        if context["contact_info"]:
            instructions += """
            INFORMACIÓN DEL USUARIO:
            - El usuario ya ha proporcionado información de contacto
            - Puedes usar save_contact_tool() sin parámetros para ver la información guardada
            - Personaliza las respuestas usando la información disponible
            """
        
        # Add source-specific context
        source = context["source"]
        if source == "whatsapp":
            instructions += """
            
            CANAL: WhatsApp
            - Mantén respuestas concisas y amigables
            - Usa emojis moderadamente
            - Considera que es un medio informal
            """
        elif source == "instagram":
            instructions += """
            
            CANAL: Instagram
            - Estilo visual y atractivo
            - Respuestas engaging y modernas
            - Considera el contexto de redes sociales
            """
        
        return instructions.strip()
    
    def _get_quality_guidelines(self, context: Dict[str, Any]) -> str:
        """Get quality guidelines for responses."""
        
        return """
        DIRECTRICES DE CALIDAD:
        
        📝 FORMATO DE RESPUESTA:
        - Usa markdown para URLs: [texto](url)
        - Estructura clara con viñetas cuando sea apropiado
        - Emojis moderados para mejor experiencia visual
        
        🎯 CONTENIDO:
        - Respuestas precisas y útiles
        - Evita repetir información ya proporcionada
        - Si no sabes algo, admítelo y busca alternativas
        - Mantén consistencia con la personalidad del proyecto
        
        🔧 USO DE HERRAMIENTAS:
        - Usa herramientas cuando sea apropiado
        - Explica claramente qué herramienta estás usando
        - Si una herramienta falla, intenta alternativas
        
        🚨 IMPORTANTE:
        - SIEMPRE usa save_contact_tool para guardar información de contacto mencionada
        - Para consultas de información, usa unified_search_tool ANTES de responder
        - Para agendamiento, sigue el flujo completo: buscar → confirmar → agendar
        """
    
    def _prepare_messages(self, state: EnhancedState, system_prompt: str) -> List:
        """Prepare messages for the language model."""
        
        # Get filtered messages
        messages = filter_and_prepare_messages_for_enhanced_agent(state)
        # Asegurar compatibilidad con OpenAI
        messages = ensure_message_compatibility(messages)
        
        # Add system message at the beginning
        messages.insert(0, SystemMessage(content=system_prompt))
        
        return messages
    
    def _get_tools_for_route(self, state: EnhancedState) -> List:
        """Get appropriate tools based on the current route."""
        
        from ...tools.registry import get_tool_registry
        
        try:
            registry = get_tool_registry()
            available_tool_names = registry.get_available_tools(state)
            tools = registry.get_tool_instances(available_tool_names)
            
            self.logger.info(f"Loaded {len(tools)} tools for agent: {[getattr(t, 'name', str(t)) for t in tools]}")
            return tools
            
        except Exception as e:
            self.logger.error(f"Failed to get tools: {str(e)}")
            return []
    
    def _generate_response(
        self, 
        state: EnhancedState, 
        messages: List, 
        tools: List,
        context: Dict[str, Any]
    ) -> AIMessage:
        """Generate response using the language model."""
        
        try:
            # Get model with appropriate temperature
            model = LLMAdapter.get_llm(self.model_name, 0)
            
            # Bind tools if available
            if tools:
                model_with_tools = model.bind_tools(tools)
            else:
                model_with_tools = model
            
            # Generate response
            response = model_with_tools.invoke(messages)
            
            # Decorate message with metadata
            decorate_message(
                response, 
                state["exec_init"], 
                context["conversation_id"]
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Response generation failed: {str(e)}")
            raise
    
    def _enhance_response(
        self, 
        state: EnhancedState, 
        response: AIMessage,
        context: Dict[str, Any]
    ) -> AIMessage:
        """Enhance and validate the generated response."""
        
        try:
            # Check response quality
            if not response.content or len(response.content.strip()) < self.min_response_length:
                self.logger.warning("Response too short, using fallback")
                fallback = self._get_fallback_response(state)
                response.content = fallback
            
            elif len(response.content) > self.max_response_length:
                self.logger.warning("Response too long, truncating")
                response.content = response.content[:self.max_response_length - 3] + "..."
            
            # Add response metadata
            response.additional_kwargs["agent_version"] = "enhanced_v2"
            response.additional_kwargs["processing_route"] = context["current_route"].value
            response.additional_kwargs["intent_category"] = context["intent_category"].value
            response.additional_kwargs["confidence_score"] = context["confidence_score"]
            
            return response
            
        except Exception as e:
            self.logger.error(f"Response enhancement failed: {str(e)}")
            return response
    
    def _get_fallback_response(self, state: EnhancedState) -> AIMessage:
        """Get fallback response based on intent."""
        
        intent = state["routing"]["intent_category"]
        fallback_content = self.fallback_responses.get(intent, self.fallback_responses[IntentCategory.GENERAL])
        
        # Create AIMessage with fallback content
        fallback_message = AIMessage(content=fallback_content)
        fallback_message.additional_kwargs = {
            "fallback_used": True,
            "intent_category": intent.value,
            "timestamp": datetime.now().isoformat()
        }
        
        return fallback_message
    
    def _update_state_with_response(self, state: EnhancedState, response: AIMessage) -> EnhancedState:
        """Update state with the generated response."""
        
        # Add response to messages
        state["messages"].append(response)
        state["conversation"]["messages"].append(response)
        
        # Update conversation state
        state = update_conversation_state(state, response)
        
        # Update last AI message in conversation state
        state["conversation"]["last_ai_message"] = response.content
        
        return state


def create_agent_node(model_name: str = MODEL_CHATBOT) -> AgentNode:
    """
    Factory function to create an enhanced AgentNode.
    
    Args:
        model_name: LLM model to use for response generation
        
    Returns:
        AgentNode: Configured enhanced agent node
    """
    return AgentNode(model_name)