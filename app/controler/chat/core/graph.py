import logging
from collections import OrderedDict
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph
from langgraph.graph.graph import END, START
from app.controler.chat.classes.chat_state import ChatState
from app.controler.chat.core.edge import invoke_tools_summary
from app.controler.chat.core.nodes import (
    create_agent,
    summarize_conversation,
    tools_node,
    get_date_range, 
    TIMEZONE
)
from app.controler.chat.core.state import CustomState
from app.controler.chat.core.utils import decorate_message
from app.controler.chat.store.persistence import Persist
from app.controler.chat.store.persistence_state import MemoryStatePersistence
import uuid
from app.controler.chat.classes.token_metrics import TokenMetrics
from app.controler.chat.services.token_metrics_service import TokenMetricsService
from app.controler.chat.classes.token_counter import TokenCounter
from app.controler.chat.classes.model_costs import ModelCosts
from fastapi import BackgroundTasks

import asyncio
import datetime

class Graph():
    state: ChatState
    workflow: StateGraph
    database: Persist
    MAX_KEYS = 5

    def __init__(self, project_id: str, user_id: str, username: str, number_phone_agent: str, source_id: str, source: str):
        self.logger = logging.getLogger(__name__)
        logging.info("init graph for project_id: %s and user_id: %s", project_id, user_id)
        self.state = ChatState(project_id, user_id)
        self.workflow = StateGraph(CustomState)
        self.database = Persist()
        self.database_state = MemoryStatePersistence()
        self.project_id = project_id
        self.user_id = user_id
        self.username = username
        self.number_phone_agent = number_phone_agent
        self.source_id = source_id
        self.source = source
        self.token_counter = TokenCounter()
        self.token_metrics_service = TokenMetricsService()
        self.model_costs = ModelCosts()
        memory = self.__set_memory()
        self.__set_nodes()
        self.__set_edges()
        self.graph = self.workflow.compile(checkpointer=memory)

    def __set_nodes(self):
        """ Define the nodes of the graph and set the entry point"""
        self.logger.info("init nodes")
        tools_node_set = tools_node(
            self.state.project_id, 
            self.state.user_id, 
            self.username, 
            self.number_phone_agent)
        self.logger.info("init agent")
        agent = create_agent(self.state.user_id, self.username,
                             self.number_phone_agent,self.source_id)
        workflow = self.workflow
        workflow.add_node("agent", agent)
        workflow.add_node("tools", tools_node_set)
        workflow.add_node("summarize_conversation", summarize_conversation)

    def __set_edges(self):
        """ Define the edges and conditionals of the graph"""
        self.logger.info("init edges")
        workflow = self.workflow
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", invoke_tools_summary)
        workflow.add_edge("tools", "agent")
        workflow.add_edge("summarize_conversation", END)

    def __set_memory(self):
        """Load the memory of recent chats from the database if exists, with Redis cache."""
        self.logger.info("init memory")
        memory = MemorySaver()
        self.logger.info(f"Buscando estado de memoria para project_id: {self.state.project_id}, user_id: {self.state.user_id}")
        state = self.database_state.fetch_state(
            self.state.project_id, self.state.user_id)
        if state:
            self.logger.info(f"Estado recuperado: {type(state)}, keys: {list(state.keys()) if isinstance(state, dict) else 'N/A'}")
            if isinstance(state.get("state"), dict):
                 memory.storage[self.state.user_id] = state["state"]
                 self.logger.info(f"Loaded state from DB for user {self.state.user_id}, memory keys: {list(state['state'].keys())}")
            else:
                 self.logger.warning(f"Formato de estado inválido recuperado para {self.state.user_id}. Tipo: {type(state.get('state'))}")
        else:
            self.logger.info(f"No previous state found for user {self.state.user_id}. Starting with empty memory.")
        return memory

    async def _calculate_tokens_async(self, message, project, user_id):
        """Calcula tokens en segundo plano"""
        try:
            system_prompt = project.instructions if project and hasattr(project, 'instructions') else ""
            system_tokens = self.token_counter.count_system_prompt_tokens(system_prompt)
            input_tokens = self.token_counter.count_message_tokens(message, 'high')
            
            current_checkpoints = self.graph.checkpointer.get({"configurable": {"thread_id": user_id}})
            context_tokens = 0
            previous_summary_content = ""
            previous_summary_tokens = 0  # Inicializar al principio para evitar UnboundLocalError
            
            if current_checkpoints:
                state_values_for_context = current_checkpoints.values if hasattr(current_checkpoints, 'values') else current_checkpoints
                messages_from_state = []
                try:
                    if isinstance(state_values_for_context, dict):
                        latest_checkpoint_data = list(state_values_for_context.get('', {}).values())[-1] if state_values_for_context.get('') else None
                        if isinstance(latest_checkpoint_data, dict):
                            messages_from_state = latest_checkpoint_data.get("messages", [])
                            previous_summary_content = latest_checkpoint_data.get("summary", "")
                except Exception as e:
                    self.logger.warning(f"Error extracting messages from checkpoint: {e}")
                
                if messages_from_state:
                    context_tokens = self.token_counter.count_conversation_tokens(messages_from_state)
                
                if previous_summary_content:
                    formatted_summary_prompt = f"system: Summary of conversation earlier: {previous_summary_content}"
                    previous_summary_tokens = self.token_counter.count_tokens(formatted_summary_prompt, 'low')
                else:
                    previous_summary_tokens = 0
            
            prompt_memory_tokens = 0
            if hasattr(project, 'prompt_memory') and project.prompt_memory:
                formatted_prompt_memory = f"system: {project.prompt_memory}"
                prompt_memory_tokens = self.token_counter.count_tokens(formatted_prompt_memory, 'low')
            
            project_info_tokens = 0
            if hasattr(project, 'name') and project.name:
                project_info_tokens += self.token_counter.count_tokens(project.name, 'low')
            if hasattr(project, 'personality') and project.personality:
                project_info_tokens += self.token_counter.count_tokens(project.personality, 'low')
            
            date_time_tokens = 0
            try:
                # Originalmente esto usaba TIMEZONE, que ya está importado de nodes
                # El datetime.datetime.now() aquí era naive, y TIMEZONE.astimezone se encargaba.
                # Replicando la lógica original vista en la primera lectura para ser consistente.
                # Aunque un `now(pytz.UTC).astimezone(TIMEZONE)` sería más robusto, se revierte al original.
                now_in_timezone = datetime.datetime.now().astimezone(TIMEZONE)
                now_str = now_in_timezone.isoformat()
                
                date_range = get_date_range()
                date_range_str = ", ".join(date_range)
                date_time_tokens += self.token_counter.count_tokens(now_str, 'low')
                date_time_tokens += self.token_counter.count_tokens(date_range_str, 'low')
                date_time_tokens += self.token_counter.count_tokens("\nConsidera que las fechas de referencia son: ", 'low')
            except Exception as e:
                self.logger.warning(f"Error counting date/time tokens: {e}")
            
            return {
                "system_tokens": system_tokens,
                "input_tokens": input_tokens,
                "context_tokens": context_tokens,
                "previous_summary_tokens": previous_summary_tokens,
                "prompt_memory_tokens": prompt_memory_tokens,
                "project_info_tokens": project_info_tokens,
                "date_time_tokens": date_time_tokens
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating tokens: {e}", exc_info=True)
            return None

    async def execute(self, message, background_tasks: BackgroundTasks):
        """Execute the graph with the given message and return response"""
        try:
            initial_time = datetime.datetime.now()
            conversation_id = str(uuid.uuid4())
            user_id = self.state.user_id
            project = self.database.find_project(self.state.project_id)
            
            model_name = "gpt-4.1-mini"
            if project and hasattr(project, 'model') and project.model and isinstance(project.model, str):
                if project.model in self.model_costs.get_supported_models():
                     model_name = project.model
                else:
                    self.logger.warning(f"Modelo '{project.model}' del proyecto no soportado, usando fallback '{model_name}'.")

            human_message = HumanMessage(content=message)
            decorate_message(human_message, initial_time, conversation_id)
            
            # Ejecutar el cálculo de tokens y la invocación del grafo en paralelo
            token_calculation_task = asyncio.create_task(
                self._calculate_tokens_async(message, project, user_id)
            )
            
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
            
            # Esperar ambas tareas en paralelo
            final_state, token_metrics_result = await asyncio.gather(
                graph_invoke_task,
                token_calculation_task
            )
            
            # Procesar la respuesta inmediatamente
            conversation_messages = final_state.get("messages", [])
            ai_response_obj = None
            if conversation_messages:
                for msg in reversed(conversation_messages):
                    if isinstance(msg, AIMessage):
                        ai_response_obj = msg
                        break
            
            if not ai_response_obj and conversation_messages and isinstance(conversation_messages[-1], SystemMessage):
                ai_response_obj = conversation_messages[-1]

            response_content = "[Error: No se pudo generar respuesta AI]" if not ai_response_obj else (
                ai_response_obj.content if hasattr(ai_response_obj, 'content') else str(ai_response_obj)
            )
            
            response = {
                'response': response_content,
                "message_id": "message_id", 
                "user_id": user_id
            }

            # Agregar tareas en segundo plano usando BackgroundTasks
            background_tasks.add_task(self._process_background_tasks, 
                final_state=final_state,
                token_metrics_result=token_metrics_result,
                ai_response_obj=ai_response_obj,
                model_name=model_name,
                initial_time=initial_time,
                conversation_id=conversation_id
            )

            return response
            
        except Exception as e:
            self.logger.error(f"Error during execution: {e}", exc_info=True)
            return {
                'response': "[Error: No se pudo ejecutar la gráfica]",
                "message_id": "message_id",
                "user_id": self.state.user_id
            }

    async def _process_background_tasks(self, final_state, token_metrics_result, ai_response_obj, model_name, initial_time, conversation_id):
        """Procesa tareas en segundo plano usando BackgroundTasks"""
        try:
            self.logger.info(f"Iniciando _process_background_tasks para user {self.state.user_id}")
            
            # Optimizar estado de memoria
            self.logger.info(f"Obteniendo estado de memoria de checkpointer storage...")
            final_memory_state_dict = self.graph.checkpointer.storage.get(self.state.user_id)
            self.logger.info(f"Estado de memoria obtenido: {type(final_memory_state_dict)}, keys: {list(final_memory_state_dict.keys()) if isinstance(final_memory_state_dict, dict) else 'N/A'}")
            
            if final_memory_state_dict:
                state_to_optimize = final_memory_state_dict.get('', {})
                self.logger.info(f"Estado a optimizar: {type(state_to_optimize)}, keys: {list(state_to_optimize.keys()) if isinstance(state_to_optimize, dict) else 'N/A'}")
                
                if isinstance(state_to_optimize, dict):
                    nested_dict = OrderedDict(state_to_optimize)
                    original_keys = len(nested_dict)
                    while len(nested_dict) > self.MAX_KEYS:
                        nested_dict.popitem(last=False)
                    self.logger.info(f"Optimización completada: {original_keys} -> {len(nested_dict)} keys")
                    
                    final_memory_state_dict[''] = nested_dict
                    chat_state_to_save = ChatState(project_id=self.state.project_id, user_id=self.state.user_id)
                    chat_state_to_save.state = final_memory_state_dict
                    
                    self.logger.info(f"Guardando estado de memoria...")
                    await asyncio.to_thread(self.database_state.save_state, chat_state_to_save)
                    self.logger.info(f"Estado de memoria guardado exitosamente para user {self.state.user_id}")
                else:
                    self.logger.warning(f"Estado de memoria no válido para user {self.state.user_id}. Tipo: {type(state_to_optimize)}")
            else:
                self.logger.warning(f"No se encontró estado de memoria final para user {self.state.user_id}")

            # Procesar métricas si están disponibles
            if token_metrics_result and ai_response_obj:
                output_tokens_count = self.token_counter.count_message_tokens(
                    ai_response_obj.content if hasattr(ai_response_obj, 'content') else str(ai_response_obj),
                    model_name
                )
                
                total_input_tokens_approx = sum([
                    token_metrics_result.get("system_tokens", 0),
                    token_metrics_result.get("input_tokens", 0),
                    token_metrics_result.get("context_tokens", 0),
                    token_metrics_result.get("prompt_memory_tokens", 0),
                    token_metrics_result.get("project_info_tokens", 0),
                    token_metrics_result.get("previous_summary_tokens", 0),
                    token_metrics_result.get("date_time_tokens", 0)
                ])
                
                total_output_tokens_approx = output_tokens_count
                
                total_cost_val, cost_breakdown_val = self.model_costs.calculate_cost(
                    input_tokens=total_input_tokens_approx,
                    output_tokens=total_output_tokens_approx,
                    model_name=model_name
                )
                
                metrics_obj = TokenMetrics(
                    project_id=self.state.project_id,
                    user_id=self.state.user_id,
                    conversation_id=conversation_id,
                    message_id="message_id",
                    timestamp=initial_time,
                    tokens={
                        "system_prompt": token_metrics_result.get("system_tokens", 0),
                        "input": token_metrics_result.get("input_tokens", 0),
                        "output": output_tokens_count,
                        "context": token_metrics_result.get("context_tokens", 0),
                        "tools_input": 0,
                        "tools_output": 0,
                        "tools_total": 0,
                        "prompt_memory": token_metrics_result.get("prompt_memory_tokens", 0),
                        "new_summary": 0,
                        "project_info": token_metrics_result.get("project_info_tokens", 0),
                        "previous_summary": token_metrics_result.get("previous_summary_tokens", 0),
                        "date_time": token_metrics_result.get("date_time_tokens", 0),
                        "total_input_approx": total_input_tokens_approx,
                        "total_output_approx": total_output_tokens_approx,
                        "total": total_input_tokens_approx + total_output_tokens_approx
                    },
                    cost=total_cost_val,
                    source=self.source_id,
                    cost_breakdown=cost_breakdown_val
                )
                
                await asyncio.to_thread(self.token_metrics_service.save_metrics, metrics_obj)
                
            # Persistir conversación en segundo plano
            await asyncio.to_thread(self.database.persist_conversation, final_state)
            
        except Exception as e:
            self.logger.error(f"Error en tareas en segundo plano: {e}", exc_info=True)