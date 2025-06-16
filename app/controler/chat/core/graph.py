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
from uuid import uuid4

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
        workflow.add_conditional_edges("agent", invoke_tools_summary)
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
        
    async def execute(self, message, debug=False):
        unique_id = self.unique_id
        logging.info(unique_id + " Execution init!")
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

        logging.info(unique_id + " Invoking graph!")

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

        logging.info(unique_id + " Execution finished")

        # Procesar el estado de memoria
        final_memory_state = self.graph.checkpointer.storage.get(user_id)
        self.state.state = final_memory_state

        # Procesar el diccionario de estado
        state_dict = self.state.state
        nested_dict = state_dict.get('', {})

        if not isinstance(nested_dict, OrderedDict):
            nested_dict = OrderedDict(nested_dict)

        MAX_KEYS = 1
        while len(nested_dict) > MAX_KEYS:
            nested_dict.popitem(last=False)

        state_dict[''] = nested_dict
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

        logging.info(unique_id + " Execution finished")
        logging.info(unique_id + " Response: " + ai_response.content)

        response = {
            'response': ai_response.content,
            "message_id": "message_id",
            "user_id": user_id,
        }

        return response

    async def execute_stream(self, message, background_tasks):
        """
        Ejecuta el grafo en modo streaming, devolviendo chunks de respuesta en tiempo real.
        
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
            # Preparar datos iniciales
            user_id = self.state.user_id
            initial_time = self.state.datetime
            conversation_id = str(uuid4())
            
            # Crear mensaje humano
            human_message = HumanMessage(content=message)
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
                
            MAX_KEYS = 1
            while len(nested_dict) > MAX_KEYS:
                nested_dict.popitem(last=False)
                
            state_dict[''] = nested_dict
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
            
        except Exception as e:
            logging.error(f"Error en streaming: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
                "is_complete": True
            }
        
        
        
        
        