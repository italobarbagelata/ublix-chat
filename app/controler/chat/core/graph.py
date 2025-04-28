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
import concurrent.futures

class Graph():
    state: ChatState
    workflow: StateGraph
    database: Persist
        
    def __init__(self, project_id, user_id, name, number_phone_agent, source):
        self.logger = logging.getLogger(f"{project_id}_{user_id}")
        self.state = ChatState(project_id, user_id)
        self.workflow = StateGraph(CustomState)
        self.database = Persist()
        self.database_state = MemoryStatePersistence()
        self.name = name
        self.number_phone_agent = number_phone_agent
        self.source = source
        memory = self.__set_memory()
        self.__set_nodes()
        self.__set_edges()
        
        self.graph = self.workflow.compile(checkpointer=memory)

    def __set_nodes(self):
        """ Define the nodes of the graph and set the entry point"""
        tools_node_set = tools_node(
            self.state.project_id, 
            self.state.user_id, 
            self.name, 
            self.number_phone_agent)
        agent = create_agent(self.state.user_id, self.name,
                             self.number_phone_agent,self.source)
        workflow = self.workflow
        workflow.add_node("agent", agent)
        workflow.add_node("tools", tools_node_set)
        workflow.add_node("summarize_conversation", summarize_conversation)

    def __set_edges(self):
        """ Define the edges and conditionals of the graph"""
        workflow = self.workflow
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", invoke_tools_summary)
        workflow.add_edge("tools", "agent")
        workflow.add_edge("summarize_conversation", END)

    def __set_memory(self):
        """Load the memory of recent chats from the database if exists, with Redis cache."""
        memory = MemorySaver()
        state = self.database_state.fetch_state(
            self.state.project_id, self.state.user_id)
        if state:
            if isinstance(state.get("state"), dict):
                 memory.storage[self.state.user_id] = state["state"]
            else:
                 self.logger.warning(f"Formato de estado inválido para {self.state.user_id}")

        return memory

    async def execute(self, message):
        """ Execute the graph with the given message and return response """
        project = self.database.find_project(self.state.project_id)
        user_id = self.state.user_id
        initial_time = self.state.datetime
        conversation_id = str(uuid.uuid4())

        human_message = HumanMessage(content=message)
        decorate_message(human_message, initial_time, conversation_id)

        final_state = self.graph.invoke(
            {
                "messages": [human_message],
                "user_id": user_id,
                "project": project,
                "exec_init": initial_time,
                "conversation_id": conversation_id
            },
            config={"configurable": {"thread_id": user_id}}
        )

        final_memory_state_dict = self.graph.checkpointer.storage.get(user_id)
        if final_memory_state_dict:
             state_to_optimize = final_memory_state_dict.get('', {})
             if isinstance(state_to_optimize, dict):
                 nested_dict = OrderedDict(state_to_optimize)
                 MAX_KEYS = 5
                 while len(nested_dict) > MAX_KEYS:
                     nested_dict.popitem(last=False)
                 final_memory_state_dict[''] = nested_dict
                 self.state.state = final_memory_state_dict

        background_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        try:
            background_executor.submit(self.database_state.save_state, self.state)
        except Exception as e:
             self.logger.error(f"Error guardando estado: {e}", exc_info=True)

        try:
            background_executor.submit(self.database.update_summary, final_state)
        except Exception as e:
            self.logger.error(f"Error actualizando resumen: {e}", exc_info=True)

        conversation = final_state.get("messages", [])
        ai_response = conversation[-1] if conversation and isinstance(conversation[-1], SystemMessage) else None
        if not ai_response:
             ai_response = next((msg for msg in reversed(conversation) if isinstance(msg, AIMessage)), None)
        
        if not ai_response:
             response_content = "[Error: No se pudo generar respuesta AI]"
        else:
             response_content = ai_response.content

        response = {
            'response': response_content,
            "message_id": "message_id",
            "user_id": user_id
        }

        return response
