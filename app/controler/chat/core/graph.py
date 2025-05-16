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
)
from app.controler.chat.core.state import CustomState
from app.controler.chat.core.utils import decorate_message
from app.controler.chat.store.persistence import Persist
from app.controler.chat.store.persistence_state import MemoryStatePersistence
import uuid
from app.controler.chat.classes.token_metrics import TokenMetrics
from app.controler.chat.services.token_metrics_service import TokenMetricsService
from app.controler.chat.classes.token_counter import TokenCounter

import concurrent.futures
from app.controler.chat.core.nodes import get_date_range, TIMEZONE 
import datetime
import pytz 
            
class Graph():
    state: ChatState
    workflow: StateGraph
    database: Persist
        
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
        state = self.database_state.fetch_state(
            self.state.project_id, self.state.user_id)
        if state:
            # Asegurarse de que el estado recuperado tenga el formato esperado por MemorySaver
            # MemorySaver espera un dict donde las claves son thread_ids y los valores
            # son dicts internos ({ns: {ts: checkpoint_data}})
            if isinstance(state.get("state"), dict):
                 # Asignar directamente el dict recuperado para este user_id
                 memory.storage[self.state.user_id] = state["state"]
                 self.logger.info(f"Loaded state from DB for user {self.state.user_id}")
            else:
                 self.logger.warning(f"Formato de estado inválido recuperado para {self.state.user_id}. Iniciando memoria vacía.")
        else:
            self.logger.info(f"No previous state found for user {self.state.user_id}. Starting with empty memory.")
            # No es necesario asignar {}, MemorySaver usa defaultdict

        return memory

    async def execute(self, message):
        """ Execute the graph with the given message and return response """
        try:
            # --- Inicialización y Preparación ---
            initial_time = datetime.datetime.now()
            conversation_id = str(uuid.uuid4())
            user_id = self.state.user_id
            project = self.database.find_project(self.state.project_id)
            
            # --- Cálculo de Tokens (Antes de ejecución) ---
            system_tokens = 0
            input_tokens = 0
            context_tokens = 0
            previous_summary_tokens = 0
            
            # --- Preparar Estado Inicial ---
            state = {
                "project": project,
                "user_id": user_id,
                "exec_init": initial_time,
                "messages": [],
                "summary": "",
                "conversation_id": conversation_id,
                "username": self.username,
                "source_id": self.source_id,
                "source": self.source
            }

            # --- Cálculo de Tokens (Antes de la ejecución) --- 
            system_prompt = project.instructions if project and hasattr(project, 'instructions') else ""
            system_tokens = self.token_counter.count_system_prompt_tokens(system_prompt)
            self.logger.info(f"System prompt tokens: {system_tokens}")
            input_tokens = self.token_counter.count_message_tokens(message)
            self.logger.info(f"Input tokens: {input_tokens}")

            # Calcular tokens de contexto ANTES de invocar
            current_checkpoints = self.graph.checkpointer.get({"configurable": {"thread_id": user_id}})
            context_tokens = 0
            previous_summary_content = ""
            if current_checkpoints:
                 self.logger.debug(f"Calculating context tokens from checkpoints: {current_checkpoints}")
                 # La estructura interna puede ser .values[""] o similar
                 state_values_for_context = current_checkpoints.values if hasattr(current_checkpoints, 'values') else current_checkpoints
                 
                 # Adaptar __calculate_context_tokens para que funcione con esta estructura
                 # O extraer mensajes directamente aquí
                 messages_from_state = []
                 try:
                     if isinstance(state_values_for_context, dict):
                         latest_checkpoint_data = list(state_values_for_context.get('', {}).values())[-1] if state_values_for_context.get('') else None
                         if isinstance(latest_checkpoint_data, dict):
                              messages_from_state = latest_checkpoint_data.get("messages", [])
                              # Extraer resumen anterior también si está en el checkpoint
                              previous_summary_content = latest_checkpoint_data.get("summary", "") 
                 except Exception as e:
                     self.logger.warning(f"Could not extract messages/summary reliably from checkpoint state: {e}")
                 
                 if messages_from_state:
                      context_tokens = self.token_counter.count_conversation_tokens(messages_from_state)
                 if previous_summary_content:
                      formatted_summary_prompt = f"system: Summary of conversation earlier: {previous_summary_content}"
                      previous_summary_tokens = self.token_counter.count_tokens(formatted_summary_prompt)

            self.logger.info(f"Context tokens (calculated before invoke): {context_tokens}")
            self.logger.info(f"Previous summary tokens (calculated before invoke): {previous_summary_tokens}")
            
            # Tokens de otros componentes (prompt_memory, project_info, date_time)
            prompt_memory_tokens = 0
            if hasattr(project, 'prompt_memory') and project.prompt_memory:
                formatted_prompt_memory = f"system: {project.prompt_memory}"
                prompt_memory_tokens = self.token_counter.count_tokens(formatted_prompt_memory)
            self.logger.info(f"Prompt memory tokens: {prompt_memory_tokens}")
            project_info_tokens = 0
            if hasattr(project, 'name') and project.name:
                project_info_tokens += self.token_counter.count_tokens(project.name)
            if hasattr(project, 'personality') and project.personality:
                project_info_tokens += self.token_counter.count_tokens(project.personality)
            self.logger.info(f"Project info tokens: {project_info_tokens}")
            date_time_tokens = 0
            try:            
                # Obtener la hora actual en UTC y convertir a zona horaria de Chile
                utc_now = datetime.datetime.now(pytz.UTC)
                now = utc_now.astimezone(TIMEZONE)
                utc_now_str = now.isoformat()
                
                date_range = get_date_range()
                date_range_str = ", ".join(date_range)
                date_time_tokens += self.token_counter.count_tokens(utc_now_str)
                date_time_tokens += self.token_counter.count_tokens(date_range_str)
                date_time_tokens += self.token_counter.count_tokens("\nConsidera que las fechas de referencia son: ")
            except ImportError as e:
                 self.logger.warning(f"No se pudo importar para contar tokens de fecha/hora: {e}")
            self.logger.info(f"Date/Time tokens: {date_time_tokens}")
            # --- Fin Cálculo de Tokens (Antes de ejecución) --- 

            human_message = HumanMessage(content=message)
            decorate_message(human_message, initial_time, conversation_id)
            self.logger.info("Invoking graph synchronously...")

            # Usar invoke (síncrono)
            final_state = self.graph.invoke(
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
            self.logger.info("Graph invocation finished")

            # --- Procesamiento Post-Invocación --- 
            # Recuperar estado directamente del storage de MemorySaver (como en el código original)
            final_memory_state_dict = self.graph.checkpointer.storage.get(user_id)
            if final_memory_state_dict:
                 # Optimización del manejo de memoria (truncado)
                 # Opera sobre el dict recuperado directamente
                 state_to_optimize = final_memory_state_dict.get('', {}) # Asume namespace ''
                 if isinstance(state_to_optimize, dict):
                     nested_dict = OrderedDict(state_to_optimize) # Convertir a OrderedDict para truncar
                     MAX_KEYS = 5 # Mantener los últimos 5 checkpoints
                     while len(nested_dict) > MAX_KEYS:
                         nested_dict.popitem(last=False)
                     
                     # Actualizar el dict original en el storage
                     final_memory_state_dict[''] = nested_dict 
                     # Actualizar el estado en el objeto ChatState para consistencia
                     self.state.state = final_memory_state_dict 
                     self.logger.info(f"Memory optimized, keeping last {len(nested_dict)} checkpoints.")
                 else:
                      self.logger.warning("Could not optimize memory: state under namespace '' is not a dict.")
            else:
                 self.logger.warning(f"Could not retrieve final memory state from storage for user {user_id} after invoke.")
                 # Asignar un estado vacío si no se encontró nada
                 self.state.state = {}

            # --- Ejecutar Guardado de Estado, Resumen y Métricas en Segundo Plano --- 
            # Usar un solo executor para las tareas relacionadas con esta ejecución
            background_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3) # 1 para estado, 1 para resumen, 1 para métricas

            # Enviar guardado de estado a segundo plano
            try:
                self.logger.info(f"Submitting background state save for {user_id}...")
                background_executor.submit(self.database_state.save_state, self.state)
            except Exception as e:
                 # Capturar error al *enviar* la tarea (poco probable pero posible)
                 self.logger.error(f"Error submitting background state save for {user_id}: {e}", exc_info=True)

            # Enviar actualización de resumen a segundo plano
            try:
                self.logger.info(f"Submitting background summary update for {user_id}...")
                background_executor.submit(self.database.update_summary, final_state)
            except Exception as e:
                self.logger.error(f"Error submitting background summary update for {user_id}: {e}", exc_info=True)

            # --- Preparar Respuesta y Métricas --- 
            conversation = final_state.get("messages", [])
            ai_response = conversation[-1] if conversation and isinstance(conversation[-1], SystemMessage) else None # Ajustar tipo esperado si es AIMessage
            if not ai_response:
                 # Buscar AIMessage si SystemMessage no es la respuesta final
                 ai_response = next((msg for msg in reversed(conversation) if isinstance(msg, AIMessage)), None)
            
            if not ai_response:
                 self.logger.error("No valid AI response (AIMessage or SystemMessage) found in final_state messages.")
                 response_content = "[Error: No se pudo generar respuesta AI]"
            else:
                 response_content = ai_response.content

            response = {
                'response': response_content,
                "message_id": "message_id",
                "user_id": user_id
            }

            # --- Calcular y Guardar Métricas (en segundo plano) --- 
            try:
                output_tokens = self.token_counter.count_message_tokens(ai_response) if ai_response else 0
                
                tools_tokens = 0
                tools_input_tokens = 0
                tools_output_tokens = 0
                if "tools" in final_state:
                    tools_result = self.token_counter.count_tools_tokens(final_state["tools"], separate=True)
                    tools_input_tokens = tools_result["input"]
                    tools_output_tokens = tools_result["output"]
                    tools_tokens = tools_input_tokens + tools_output_tokens
                
                new_summary_tokens = 0
                # El resumen podría estar en final_state directamente si es el último nodo
                final_summary_content = final_state.get("summary", "") 
                if final_summary_content:
                    formatted_new_summary = f"assistant: {final_summary_content}"
                    new_summary_tokens = self.token_counter.count_tokens(formatted_new_summary)
                
                total_tokens = (system_tokens + input_tokens + output_tokens + 
                               context_tokens + tools_tokens + prompt_memory_tokens + 
                               project_info_tokens + new_summary_tokens + 
                               previous_summary_tokens + date_time_tokens)

                total_input_tokens_approx = (system_tokens + input_tokens + context_tokens + 
                                             prompt_memory_tokens + project_info_tokens + 
                                             previous_summary_tokens + date_time_tokens + 
                                             tools_input_tokens)
                total_output_tokens_approx = (output_tokens + new_summary_tokens + 
                                              tools_output_tokens)
                INPUT_COST_PER_TOKEN = 0.00000015 # Ajustar tasas según modelo usado (gpt-4o-mini: $0.15/M tokens)
                OUTPUT_COST_PER_TOKEN = 0.0000006 # Ajustar tasas según modelo usado (gpt-4o-mini: $0.60/M tokens)
                input_cost = total_input_tokens_approx * INPUT_COST_PER_TOKEN
                output_cost = total_output_tokens_approx * OUTPUT_COST_PER_TOKEN
                total_cost = input_cost + output_cost

                metrics = TokenMetrics(
                    project_id=self.state.project_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id="message_id",
                    timestamp=initial_time,
                    tokens={
                        "system_prompt": system_tokens,
                        "input": input_tokens,
                        "output": output_tokens,
                        "context": context_tokens,
                        "tools_input": tools_input_tokens,
                        "tools_output": tools_output_tokens,
                        "tools_total": tools_tokens,
                        "prompt_memory": prompt_memory_tokens,
                        "new_summary": new_summary_tokens,
                        "project_info": project_info_tokens,
                        "previous_summary": previous_summary_tokens,
                        "date_time": date_time_tokens,
                        "total_input_approx": total_input_tokens_approx,
                        "total_output_approx": total_output_tokens_approx,
                        "total": total_tokens
                    },
                    cost=total_cost,
                    source=self.source_id
                )
                
                # Enviar cálculo y guardado de métricas a segundo plano usando el mismo executor
                self.logger.info(f"Submitting background metrics save for {user_id}...")
                background_executor.submit(self.token_metrics_service.save_metrics, metrics)
                # Considerar shutdown si es necesario: metrics_executor.shutdown(wait=False)
                self.logger.info(f"Metrics calculation submitted for {user_id}.")

            except Exception as e:
                self.logger.error(f"Error during metrics calculation/submission for {user_id}: {e}", exc_info=True)
                
            # Opcional: Esperar a que terminen las tareas si es crítico (generalmente no para la respuesta del chat)
            # background_executor.shutdown(wait=True) 

            return response
        except Exception as e:
            self.logger.error(f"Error during execution: {e}", exc_info=True)
            return {
                'response': "[Error: No se pudo ejecutar la gráfica]",
                "message_id": "message_id",
                "user_id": self.state.user_id
            }