import logging
import asyncio
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph
from langgraph.graph import END, START
from concurrent.futures import ThreadPoolExecutor
from app.controler.chat.classes.chat_state import ChatState
from app.controler.chat.core.edge import invoke_tools_summary
from app.controler.chat.core.nodes import create_agent, resume_conversation, tools_node
from app.controler.chat.core.state import CustomState
from app.controler.chat.core.tools import agent_tools
from app.controler.chat.core.utils import decorate_message
from app.controler.chat.store.persistence import Persist
from app.controler.chat.store.persistence_state import MemoryStatePersistence
from collections import OrderedDict
from app.controler.chat.core.generate_summary import generate_summary, SummaryPayload
from uuid import uuid4
import time
from app.core.logger_config import get_conversation_logger


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
        # OPTIMIZACIÓN: Cargar herramientas UNA SOLA VEZ y pasarlas a los nodos
        # Esto evita múltiples llamadas a agent_tools() durante el ciclo del grafo
        self.logger.debug(f"Cargando herramientas para proyecto {self.state.project_id}")

        tools = await agent_tools(
            self.state.project_id,
            self.state.user_id,
            self.name,
            self.number_phone_agent,
            self.unique_id,
            self.project
        )

        self.logger.debug(f"Herramientas cargadas: {len(tools)}")

        # Crear nodos con herramientas pre-cargadas
        tools_node_set = await tools_node(
            self.state.project_id,
            self.state.user_id,
            self.name,
            self.number_phone_agent,
            self.unique_id,
            self.project,
            tools=tools  # Pasar herramientas pre-cargadas
        )
        agent = await create_agent(
            self.state.user_id,
            self.name,
            self.number_phone_agent,
            self.source,
            self.unique_id,
            self.project,
            tools=tools  # Pasar herramientas pre-cargadas
        )
        workflow = self.workflow
        workflow.add_node("agent", agent)
        workflow.add_node("tools", tools_node_set)
        workflow.add_node("summarize_conversation", resume_conversation)

        
    def __set_edges(self):
        # Configuración interna del grafo - no necesita log
        workflow = self.workflow
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", invoke_tools_summary)
        workflow.add_edge("tools", "agent")
        workflow.add_edge("summarize_conversation", END)
        
    async def __set_memory(self):
        memory = MemorySaver()
        state = await self.database_state.fetch_state(
            self.state.project_id, self.state.user_id)
        if state:
            if isinstance(state.get("state"), dict):
                 memory.storage[self.state.user_id] = state["state"]
                 self.logger.debug(f"Memoria cargada para usuario {self.state.user_id}")
            else:
                 self.logger.warning(f"Estado con formato inválido para usuario {self.state.user_id}")
        else:
            self.logger.debug(f"Primera conversación del usuario {self.state.user_id}")
        return memory
    
        
    async def execute(self, message):
        unique_id = self.unique_id
        start_time = time.time()
        conversation_id = str(uuid4())
        
        # Logger de conversación
        conv_logger = get_conversation_logger(conversation_id, self.state.user_id)
        conv_logger.log_procesamiento_ia()
        
        loop = asyncio.get_event_loop()

        # Preparar datos iniciales
        user_id = self.state.user_id
        initial_time = self.state.datetime

        human_message = HumanMessage(content=message)
        decorate_message(human_message, initial_time, conversation_id)

        # Proyecto ya disponible
        project = self.project

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
                "summary": "",
            },
            {"configurable": {"thread_id": user_id}}
        )

        # Procesar el estado de memoria
        final_memory_state = self.graph.checkpointer.storage.get(user_id)
        self.state.state = final_memory_state

        # Procesar el diccionario de estado
        state_dict = self.state.state
        nested_dict = state_dict.get('', {})

        if not isinstance(nested_dict, OrderedDict):
            nested_dict = OrderedDict(nested_dict)

        # Sistema de memoria simplificado
        self.state.state = state_dict

        # Guardar estado en segundo plano
        asyncio.create_task(self.database_state.save_state(self.state))
        
        # Generar resumen en segundo plano
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
        
        # Log de finalización con el logger de conversación
        conv_logger.log_respuesta_generada(ai_response.content, processing_time)
        conv_logger.log_estado_guardado()

        response = {
            'response': ai_response.content,
            "message_id": "message_id",
            "user_id": user_id,
            "processing_time": processing_time
        }

        return response
        