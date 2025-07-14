import logging
import asyncio
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph
from langgraph.graph.graph import END, START
from concurrent.futures import ThreadPoolExecutor
from app.controler.chat.classes.chat_state import ChatState
from app.controler.chat.core.edge import invoke_tools_summary
from app.controler.chat.core.nodes import create_agent, resume_conversation, tools_node
from app.controler.chat.core.state import CustomState
from app.controler.chat.core.utils import decorate_message
from app.controler.chat.store.persistence import Persist
from app.controler.chat.store.persistence_state import MemoryStatePersistence
from collections import OrderedDict
from app.controler.chat.core.generate_summary import generate_summary, SummaryPayload
from app.controler.chat.core.intelligent_memory import IntelligentMemoryManager
from app.controler.chat.core.robust_error_handler import error_handler, RetryConfig, CircuitBreakerOpenError
from uuid import uuid4
from datetime import datetime
import time

# 🚀 RESPUESTAS INMEDIATAS - Placeholders para diferentes tipos de consultas
IMMEDIATE_RESPONSES = {
    "agenda": "📅 Revisando tu agenda...",
    "productos": "🛍️ Buscando productos...",
    "informacion": "🔍 Buscando información...",
    "email": "📧 Preparando email...",
    "api": "🔌 Consultando datos...",
    "default": "⏳ Procesando tu mensaje..."
}

def detect_query_type(message: str) -> str:
    """Detecta el tipo de consulta para enviar respuesta inmediata apropiada"""
    message_lower = message.lower()
    
    # Palabras clave para agenda
    agenda_keywords = ['agenda', 'cita', 'reunión', 'reunión', 'horario', 'agendar', 'calendario', 'disponible']
    if any(keyword in message_lower for keyword in agenda_keywords):
        return "agenda"
    
    # Palabras clave para productos
    product_keywords = ['producto', 'precio', 'comprar', 'vender', 'catálogo', 'tienda', 'oferta']
    if any(keyword in message_lower for keyword in product_keywords):
        return "productos"
    
    # Palabras clave para email
    email_keywords = ['enviar', 'email', 'correo', 'notificar', 'mensaje']
    if any(keyword in message_lower for keyword in email_keywords):
        return "email"
    
    # Palabras clave para información general
    info_keywords = ['qué', 'cómo', 'cuándo', 'dónde', 'información', 'ayuda']
    if any(keyword in message_lower for keyword in info_keywords):
        return "informacion"
    
    return "default"

async def get_user_accumulated_context(user_id: str, project_id: str) -> list:
    """
    🧠 NUEVA FUNCIÓN: Obtiene el contexto acumulado del usuario desde el módulo principal
    """
    try:
        # Import dinámico para evitar circular imports
        from app.controler.chat import get_and_clear_accumulated_context
        return await get_and_clear_accumulated_context(user_id, project_id)
    except Exception as e:
        logging.error(f"Error getting accumulated context: {str(e)}")
        return []

def build_message_with_context(original_message: str, accumulated_context: list) -> str:
    """
    Simplifica el mensaje final: 'mensaje principal extra: extra1 | extra2 | ...'
    """
    if not accumulated_context:
        return original_message
    extras = [ctx.get('message', '') for ctx in accumulated_context if ctx.get('message')]
    extras_str = ' | '.join(extras)
    return f"{original_message} extra: {extras_str}"

class Graph():
    @classmethod
    async def create(cls, project_id, user_id, name, number_phone_agent, source, source_id, unique_id, project):
        self = cls()
        self.state = ChatState(project_id, user_id)
        
        # Propiedades básicas
        self.project_id = project_id
        self.user_id = user_id
        self.name = name
        self.number_phone_agent = number_phone_agent
        self.source_id = source_id
        self.source = source
        self.project = project
        self.workflow = StateGraph(CustomState)
        self.database = Persist()
        self.database_state = MemoryStatePersistence()
        self.logger = logging.getLogger(__name__)
        

        self.unique_id = unique_id
        self.source = source
        self.executor = ThreadPoolExecutor(max_workers=3)
        memory = await self.__set_memory()
        await self.__set_nodes()
        self.__set_edges()
        self.graph = self.workflow.compile(checkpointer=memory)
        return self

    def __init__(self):
        pass    
    
    
    
    async def __set_nodes(self):
        tools_node_set = await tools_node(
            self.state.project_id,
            self.state.user_id,
            self.name,
            self.number_phone_agent,
            self.unique_id,
            self.project
        )
        agent = await create_agent(
            self.state.user_id,
            self.name,
            self.number_phone_agent,
            self.source,
            self.unique_id,
            self.project
        )
        workflow = self.workflow
        workflow.add_node("agent", agent)
        workflow.add_node("tools", tools_node_set)
        workflow.add_node("summarize_conversation", resume_conversation)

        
    def __set_edges(self):
        logging.info(f"* Setting edges for project {self.state.project_id} and user {self.state.user_id}")
        workflow = self.workflow
        workflow.add_edge(START, "agent")
        # FIXED: Add explicit mapping for conditional edges to prevent infinite loops
        workflow.add_conditional_edges("agent", invoke_tools_summary, {
            "tools": "tools",
            "summarize_conversation": "summarize_conversation"
        })
        workflow.add_edge("tools", "agent")
        workflow.add_edge("summarize_conversation", END)
        
    async def __set_memory(self):
        self.logger.info("init memory")
        memory = MemorySaver()
        state = await self.database_state.fetch_state(
            self.state.project_id, self.state.user_id)
        if state:
            if isinstance(state.get("state"), dict):
                 memory.storage[self.state.user_id] = state["state"]
                 self.logger.info(f"Loaded state from DB for user {self.state.user_id}, memory keys: {list(state['state'].keys())}")
            else:
                 self.logger.warning(f"Formato de estado inválido recuperado para {self.state.user_id}. Tipo: {type(state.get('state'))}")
        else:
            self.logger.info(f"No previous state found for user {self.state.user_id}. Starting with empty memory.")
        return memory
    
    @error_handler.with_retry(
        config=RetryConfig(max_retries=2, base_delay=1.0),
        circuit_breaker_key="graph_execution",
        fallback=None
    )
    async def execute_with_immediate_response(self, message, background_tasks):
        """
        🚀 NUEVA FUNCIÓN: Ejecuta con respuesta inmediata
        ✅ MEJORADO: Incluye contexto acumulado de mensajes encolados
        ✅ ROBUSTO: Con retry automático y circuit breaker
        """
        # 1. Obtener contexto acumulado si existe
        accumulated_context = await get_user_accumulated_context(self.user_id, self.project_id)
        
        # 2. Construir mensaje final con contexto
        final_message = build_message_with_context(message, accumulated_context)
        
        # 3. Detectar tipo de consulta y enviar respuesta inmediata
        query_type = detect_query_type(message)
        immediate_response = IMMEDIATE_RESPONSES.get(query_type, IMMEDIATE_RESPONSES["default"])
        
        # 4. Ejecutar el procesamiento real con el mensaje completo
        response = await self.execute(final_message, background_tasks)
        
        # 5. Agregar metadatos de timing y contexto
        response['immediate_response'] = immediate_response
        response['query_type'] = query_type
        response['processing_time'] = response.get('processing_time', 0)
        
        if accumulated_context:
            response['messages_processed'] = len(accumulated_context) + 1
            response['includes_queued_messages'] = True
        
        return response
        
    async def execute(self, message, debug=False):
        unique_id = self.unique_id
        start_time = time.time()
        logging.info(f"{unique_id} Graph execution started for project {self.state.project_id}, user {self.state.user_id}")
        loop = asyncio.get_event_loop()

        # Obtener el proyecto en paralelo mientras preparamos el mensaje
        project_future = loop.run_in_executor(
            self.executor,
            self.database.find_project,
            self.state.project_id
        )

        # Preparar datos iniciales
        user_id = self.state.user_id
        initial_time = self.state.datetime
        conversation_id = str(uuid4())

        human_message = HumanMessage(content=message)
        decorate_message(human_message, initial_time, conversation_id)

        # Esperar por el proyecto
        project = await project_future

        logging.info(f"{unique_id} Invoking LangGraph with initial message: '{message[:100]}...'" if len(message) > 100 else f"{unique_id} Invoking LangGraph with message: '{message}'")

        # Ejecutar el graph (esto no se puede paralelizar fácilmente)
        final_state = await self.graph.ainvoke(
            {
                "messages": [human_message],
                "user_id": user_id,
                "project": project,
                "exec_init": initial_time,
                "conversation_id": conversation_id,
                "unique_id": unique_id,
                "username": self.name,
                "source_id": self.source_id,
                "source": self.source,
                "summary": ""
            },
            {"configurable": {"thread_id": user_id}}
        )

        logging.info(f"{unique_id} Graph execution completed successfully")

        # Procesar el estado de memoria
        final_memory_state = self.graph.checkpointer.storage.get(user_id)
        self.state.state = final_memory_state

        # Procesar el diccionario de estado
        state_dict = self.state.state
        nested_dict = state_dict.get('', {})

        if not isinstance(nested_dict, OrderedDict):
            nested_dict = OrderedDict(nested_dict)

        # 🧠 SISTEMA DE MEMORIA INTELIGENTE AVANZADO
        # Usar el nuevo sistema adaptativo que calcula automáticamente el tamaño óptimo
        state_dict = IntelligentMemoryManager.optimize_memory_state(state_dict)
        
        # Generar analíticas de memoria para monitoreo
        memory_analytics = IntelligentMemoryManager.get_memory_analytics(state_dict)
        logging.debug(f"Memory analytics: {memory_analytics}")
        
        # Obtener sugerencias de optimización
        optimization_suggestions = IntelligentMemoryManager.suggest_memory_optimization(state_dict)
        if optimization_suggestions:
            logging.debug(f"Memory optimization suggestions: {len(optimization_suggestions)} items")
        
        # Crear backup de elementos críticos
        backup_hash = IntelligentMemoryManager.create_memory_backup(state_dict)
        self.state.state = state_dict

        logging.info(unique_id + " saving state")
        # 1. Tareas CRÍTICAS: save_state - usando MemoryStatePersistence asíncrono
        asyncio.create_task(self.database_state.save_state(self.state))
        
        logging.info(unique_id + " sending to summary")
        loop.run_in_executor(
            self.executor,
            generate_summary,
            SummaryPayload(
                project_id=self.state.project_id,
                phone_number=user_id,
                message=message
            )
        )

        conversation = final_state["messages"]
        ai_response = conversation[-1]

        # Calcular tiempo de procesamiento
        processing_time = time.time() - start_time

        logging.info(f"{unique_id} Graph execution completed successfully")
        logging.info(unique_id + " Response: " + ai_response.content)
        logging.info(unique_id + f" Processing time: {processing_time:.2f}s")

        response = {
            'response': ai_response.content,
            "message_id": "message_id",
            "user_id": user_id,
            "processing_time": processing_time
        }

        return response

    async def execute_stream(self, message, background_tasks):
        """
        Ejecuta el grafo en modo streaming, devolviendo chunks de respuesta en tiempo real.
        ✅ MEJORADO: Incluye contexto acumulado de mensajes encolados
        
        Args:
            message (str): Mensaje del usuario
            background_tasks (BackgroundTasks): Tareas en segundo plano de FastAPI
            
        Yields:
            dict: Chunks de respuesta con el formato:
                {
                    "type": "content_chunk" | "error" | "completion",
                    "content": str,  # Solo para content_chunk
                    "error": str,    # Solo para error
                    "is_complete": bool,
                    "message_id": str | None
                }
        """
        unique_id = self.unique_id
        logging.info(f"{unique_id} Iniciando ejecución en modo streaming")
        
        try:
            # 🧠 OBTENER CONTEXTO ACUMULADO - Verificar si hay mensajes adicionales
            accumulated_context = await get_user_accumulated_context(self.user_id, self.project_id)
            
            # 📝 CONSTRUIR MENSAJE FINAL - Incluir contexto si existe
            final_message = build_message_with_context(message, accumulated_context)
            
            # 🚀 RESPUESTA INMEDIATA - Detectar tipo de consulta y enviar respuesta inmediata
            query_type = detect_query_type(message)
            immediate_response = IMMEDIATE_RESPONSES.get(query_type, IMMEDIATE_RESPONSES["default"])
            
            # Enviar respuesta inmediata con información de contexto
            immediate_yield = {
                "type": "immediate_response",
                "content": immediate_response,
                "query_type": query_type,
                "is_complete": False
            }
            
            # Añadir información de contexto si hay mensajes adicionales
            if accumulated_context:
                immediate_yield["messages_processed"] = len(accumulated_context) + 1
                immediate_yield["includes_queued_messages"] = True
                immediate_yield["content"] = f"{immediate_response} (procesando {len(accumulated_context)} mensajes adicionales)"
            
            yield immediate_yield
            
            # Preparar datos iniciales
            user_id = self.state.user_id
            initial_time = self.state.datetime
            conversation_id = str(uuid4())
            
            # Crear mensaje humano con el mensaje final (incluye contexto)
            human_message = HumanMessage(content=final_message)
            decorate_message(human_message, initial_time, conversation_id)
            
            # Estado inicial para el grafo
            initial_state = {
                "messages": [human_message],
                "user_id": user_id,
                "project": self.project,
                "exec_init": initial_time,
                "conversation_id": conversation_id,
                "unique_id": unique_id,
                "username": self.name,
                "source_id": self.source_id,
                "source": self.source,
                "summary": ""
            }
            
            # Configuración para el grafo
            config = {"configurable": {"thread_id": user_id}}
            
            # Usar el servicio de streaming
            from app.controler.chat.services.streaming_service import StreamingService
            streaming_service = StreamingService()
            
            # Stream de respuesta con memoria
            async for chunk in streaming_service.stream_graph_response_with_memory(
                self.graph,
                initial_state,
                config
            ):
                yield chunk
                
            # Guardar estado final
            final_memory_state = self.graph.checkpointer.storage.get(user_id)
            self.state.state = final_memory_state
            
            # Procesar y limpiar el estado
            state_dict = self.state.state
            nested_dict = state_dict.get('', {})
            
            if not isinstance(nested_dict, OrderedDict):
                nested_dict = OrderedDict(nested_dict)
                
            # 🧠 SISTEMA DE MEMORIA INTELIGENTE AVANZADO para streaming
            state_dict = IntelligentMemoryManager.optimize_memory_state(state_dict)
            
            # Log analíticas en modo debug para streaming
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                memory_analytics = IntelligentMemoryManager.get_memory_analytics(state_dict)
                logging.debug(f"Streaming memory analytics: {memory_analytics}")
            self.state.state = state_dict
            
            # Guardar estado y generar resumen en segundo plano
            background_tasks.add_task(self.database_state.save_state, self.state)
            background_tasks.add_task(
                generate_summary,
                SummaryPayload(
                    project_id=self.state.project_id,
                    phone_number=user_id,
                    message=message
                )
            )
            
        except CircuitBreakerOpenError as e:
            logging.error(f"Circuit breaker open during streaming: {str(e)}")
            yield {
                "type": "error",
                "error": "Servicio temporalmente no disponible. Intenta en unos minutos.",
                "error_type": "circuit_breaker",
                "is_complete": True,
                "retry_after": 60
            }
        except Exception as e:
            logging.error(f"Error in streaming execution: {str(e)}", exc_info=True)
            
            # Clasificar tipo de error para mejor manejo
            error_type = type(e).__name__
            user_friendly_message = self._get_user_friendly_error_message(e)
            
            yield {
                "type": "error",
                "error": user_friendly_message,
                "error_type": error_type,
                "is_complete": True,
                "technical_details": str(e) if logging.getLogger().isEnabledFor(logging.DEBUG) else None
            }
    
    def _get_user_friendly_error_message(self, error: Exception) -> str:
        """
        Convierte errores técnicos en mensajes amigables para el usuario.
        
        Args:
            error: Excepción original
            
        Returns:
            Mensaje amigable para el usuario
        """
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Mapeo de errores comunes a mensajes amigables
        if "timeout" in error_message or "timed out" in error_message:
            return "⏱️ La operación está tomando más tiempo del esperado. Por favor intenta nuevamente."
        
        elif "connection" in error_message or "network" in error_message:
            return "🌐 Hay un problema de conexión. Verifica tu conexión a internet e intenta nuevamente."
        
        elif "permission" in error_message or "unauthorized" in error_message:
            return "🔒 No tienes permisos para realizar esta operación. Contacta al administrador."
        
        elif "not found" in error_message or "404" in error_message:
            return "🔍 No se pudo encontrar el recurso solicitado. Verifica la información e intenta nuevamente."
        
        elif "rate limit" in error_message or "too many requests" in error_message:
            return "⚡ Se han realizado demasiadas solicitudes. Por favor espera un momento e intenta nuevamente."
        
        elif "validation" in error_message or "invalid" in error_message:
            return "📝 Los datos proporcionados no son válidos. Verifica la información e intenta nuevamente."
        
        elif error_type in ["KeyError", "AttributeError", "TypeError"]:
            return "⚙️ Ocurrió un error interno. El equipo técnico ha sido notificado."
        
        elif error_type == "ValueError":
            return "Los valores proporcionados no son correctos. Verifica la información e intenta nuevamente."
        
        else:
            return "Ocurrió un error inesperado. Por favor intenta nuevamente o contacta soporte si el problema persiste."
    
    def get_error_stats(self) -> dict:
        """
        Obtiene estadísticas de errores del sistema.
        
        Returns:
            Diccionario con estadísticas de errores
        """
        return {
            'function_stats': error_handler.get_stats(),
            'circuit_breaker_stats': error_handler.get_circuit_breaker_status()
        }
        
        
        