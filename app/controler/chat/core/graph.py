import logging
import asyncio
import datetime
import uuid
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph
from langgraph.graph.graph import END, START
from fastapi import BackgroundTasks

from app.controler.chat.classes.chat_state import ChatState
from app.controler.chat.core.edge import invoke_tools_summary
from app.controler.chat.core.nodes import create_agent, summarize_conversation, tools_node
from app.controler.chat.core.state import CustomState
from app.controler.chat.core.utils import decorate_message
from app.controler.chat.services.graph_config_service import GraphConfigService
from app.controler.chat.services.token_calculation_service import TokenCalculationService
from app.controler.chat.services.memory_optimization_service import MemoryOptimizationService
from app.controler.chat.services.background_processing_service import BackgroundProcessingService
from app.controler.chat.services.streaming_service import StreamingService

class Graph():
    """Grafo simplificado enfocado en orquestación según LangGraph mejores prácticas"""
    
    def __init__(self, project_id: str, user_id: str, username: str, number_phone_agent: str, source_id: str, source: str):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing graph for project_id: %s and user_id: %s", project_id, user_id)
        
        # Propiedades básicas
        self.state = ChatState(project_id, user_id)
        self.project_id = project_id
        self.user_id = user_id
        self.username = username
        self.number_phone_agent = number_phone_agent
        self.source_id = source_id
        self.source = source
        
        # Servicios especializados
        self.config_service = GraphConfigService()
        self.token_service = TokenCalculationService()
        self.memory_service = MemoryOptimizationService()
        self.background_service = BackgroundProcessingService()
        self.streaming_service = StreamingService()
        
        # Configuración del grafo
        self.workflow = StateGraph(CustomState)
        self._setup_graph()
    
    def _setup_graph(self):
        """Configura el grafo con nodos, aristas y memoria"""
        memory = self._setup_memory()
        self._setup_nodes()
        self._setup_edges()
        self.graph = self.workflow.compile(checkpointer=memory)

    def _setup_nodes(self):
        """Define los nodos del grafo"""
        self.logger.info("Setting up nodes")
        
        # Configurar nodos con parámetros específicos
        tools_node_set = tools_node(
            self.state.project_id, 
            self.state.user_id, 
            self.username, 
            self.number_phone_agent
        )
        
        agent = create_agent(
            self.state.user_id, 
            self.username,
            self.number_phone_agent,
            self.source_id
        )
        
        # Agregar nodos al workflow
        self.workflow.add_node("agent", agent)
        self.workflow.add_node("tools", tools_node_set)
        self.workflow.add_node("summarize_conversation", summarize_conversation)

    def _setup_edges(self):
        """Define las aristas y condicionales del grafo"""
        self.logger.info("Setting up edges")
        
        self.workflow.add_edge(START, "agent")
        self.workflow.add_conditional_edges("agent", invoke_tools_summary)
        self.workflow.add_edge("tools", "agent")
        self.workflow.add_edge("summarize_conversation", END)

    def _setup_memory(self):
        """Configura la memoria con estado inicial desde la base de datos"""
        self.logger.info("Setting up memory")
        
        memory = MemorySaver()
        
        # Cargar estado inicial usando el servicio de memoria
        initial_state = self.memory_service.load_initial_state(
            self.state.project_id, 
            self.state.user_id
        )
        
        if initial_state:
            memory.storage.update(initial_state)
            
        return memory



    async def execute(self, message: str, background_tasks: BackgroundTasks):
        """Ejecuta el grafo con el mensaje dado - Versión simplificada según LangGraph"""
        try:
            initial_time = datetime.datetime.now()
            conversation_id = str(uuid.uuid4())
            user_id = self.state.user_id
            
            # Obtener proyecto y configuración usando servicio
            project = await self.config_service.get_project_cached(self.state.project_id)
            model_name = self.config_service.get_model_name(project)
            
            # Preparar mensaje
            human_message = HumanMessage(content=message)
            decorate_message(human_message, initial_time, conversation_id)
            
            # Ejecutar el grafo y calcular tokens en paralelo
            graph_invoke_task = asyncio.create_task(
                asyncio.to_thread(
                    self.graph.invoke,
                    {
                        "messages": [human_message],
                        "user_id": user_id,
                        "project": project,
                        "exec_init": initial_time,
                        "conversation_id": conversation_id,
                        "username": self.username,
                        "source_id": self.source_id,
                        "source": self.source
                    },
                    config={"configurable": {"thread_id": user_id}}
                )
            )
            
            token_calculation_task = asyncio.create_task(
                self.token_service.calculate_tokens_async(message, project, user_id, self.graph)
            )
            
            # Esperar resultados en paralelo
            final_state, token_metrics_result = await asyncio.gather(
                graph_invoke_task,
                token_calculation_task
            )
            
            # Extraer respuesta AI
            ai_response_obj = self._extract_ai_response(final_state)
            response_content = self._get_response_content(ai_response_obj)
            
            # Procesar tareas en segundo plano
            background_tasks.add_task(
                self.background_service.process_all_background_tasks,
                final_state=final_state,
                token_metrics_result=token_metrics_result,
                ai_response_obj=ai_response_obj,
                model_name=model_name,
                initial_time=initial_time,
                conversation_id=conversation_id,
                project_id=self.state.project_id,
                user_id=user_id,
                source_id=self.source_id,
                graph=self.graph
            )

            return {
                'response': response_content,
                "message_id": "message_id", 
                "user_id": user_id
            }
            
        except Exception as e:
            self.logger.error(f"Error during execution: {e}", exc_info=True)
            return {
                'response': "[Error: No se pudo ejecutar el grafo]",
                "message_id": "message_id",
                "user_id": self.state.user_id
            }
    
    def _extract_ai_response(self, final_state):
        """Extrae la respuesta AI del estado final"""
        conversation_messages = final_state.get("messages", [])
        
        if conversation_messages:
            for msg in reversed(conversation_messages):
                if isinstance(msg, AIMessage):
                    return msg
            
            # Fallback a SystemMessage si no hay AIMessage
            if isinstance(conversation_messages[-1], SystemMessage):
                return conversation_messages[-1]
        
        return None
    
    def _get_response_content(self, ai_response_obj):
        """Obtiene el contenido de la respuesta AI"""
        if not ai_response_obj:
            return "[Error: No se pudo generar respuesta AI]"
        
        return (ai_response_obj.content 
                if hasattr(ai_response_obj, 'content') 
                else str(ai_response_obj))
    
    async def execute_stream(self, message: str, background_tasks: BackgroundTasks):
        """
        🆕 NUEVO: Ejecuta el grafo con streaming para respuestas en tiempo real
        ✅ Mantiene toda la funcionalidad actual + streaming
        """
        try:
            initial_time = datetime.datetime.now()
            conversation_id = str(uuid.uuid4())
            user_id = self.state.user_id
            
            # Obtener proyecto y configuración (igual que execute normal)
            project = await self.config_service.get_project_cached(self.state.project_id)
            model_name = self.config_service.get_model_name(project)
            
            # Preparar mensaje (igual que execute normal)
            human_message = HumanMessage(content=message)
            decorate_message(human_message, initial_time, conversation_id)
            
            # Estado inicial para el streaming
            initial_state = {
                "messages": [human_message],
                "user_id": user_id,
                "project": project,
                "exec_init": initial_time,
                "conversation_id": conversation_id,
                "username": self.username,
                "source_id": self.source_id,
                "source": self.source
            }
            
            config = {"configurable": {"thread_id": user_id}}
            
            # Iniciar cálculo de tokens en paralelo (no bloqueante)
            token_calculation_task = asyncio.create_task(
                self.token_service.calculate_tokens_async(message, project, user_id, self.graph)
            )
            
            # Variables para acumular respuesta completa
            full_response_content = ""
            final_state = None
            ai_response_obj = None
            
            # 🎯 STREAMING: Usar el servicio de streaming híbrido (real + simulado)
            async for chunk in self.streaming_service.stream_graph_response_hybrid(
                self.graph, initial_state, config
            ):
                
                # Procesar chunks de contenido
                if chunk["type"] == "content_chunk":
                    full_response_content += chunk["content"]
                    
                    # Enviar chunk inmediatamente
                    yield {
                        "type": "content_chunk",
                        "content": chunk["content"],
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "is_complete": False
                    }
                
                # Procesar actualizaciones de estado
                elif chunk["type"] == "status_update":
                    yield {
                        "type": "status_update",
                        "status": chunk["status"],
                        "node": chunk["node"],
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "is_complete": False
                    }
                
                # Procesar finalización
                elif chunk["type"] == "completion":
                    # Obtener estado final del grafo
                    final_state = await asyncio.to_thread(
                        self.graph.get_state,
                        config
                    )
                    
                    # Extraer respuesta AI para tareas en segundo plano
                    ai_response_obj = self._extract_ai_response(final_state.values)
                    
                    yield {
                        "type": "completion",
                        "response": full_response_content or self._get_response_content(ai_response_obj),
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "is_complete": True
                    }
                
                # Procesar errores
                elif chunk["type"] == "error":
                    yield {
                        "type": "error",
                        "error": chunk["error"],
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "is_complete": True
                    }
                    return
            
            # Esperar y procesar tareas en segundo plano (igual que execute normal)
            try:
                token_metrics_result = await token_calculation_task
                
                if final_state and ai_response_obj:
                    background_tasks.add_task(
                        self.background_service.process_all_background_tasks,
                        final_state=final_state.values,
                        token_metrics_result=token_metrics_result,
                        ai_response_obj=ai_response_obj,
                        model_name=model_name,
                        initial_time=initial_time,
                        conversation_id=conversation_id,
                        project_id=self.state.project_id,
                        user_id=user_id,
                        source_id=self.source_id,
                        graph=self.graph
                    )
            except Exception as bg_error:
                self.logger.warning(f"Background task error in streaming: {bg_error}")
            
        except Exception as e:
            self.logger.error(f"Error during streaming execution: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": "[Error: No se pudo ejecutar el grafo en streaming]",
                "conversation_id": str(uuid.uuid4()),
                "user_id": self.state.user_id,
                "is_complete": True
            }

