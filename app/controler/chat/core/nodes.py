import logging
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import ToolNode
from langchain_core.messages import RemoveMessage, SystemMessage
import pytz

from app.controler.chat.core.state import CustomState
from app.controler.chat.core.tools import agent_tools
from app.controler.chat.core.utils import decorate_message, filter_and_prepare_messages_for_agent_node, filter_and_prepare_messages_for_summary_node
from app.controler.chat.store.persistence import Persist
from app.controler.chat.core.llm_adapter import LLMAdapter
from dotenv import load_dotenv
from app.resources.constants import DEFAULT_PROMPT, DEFAULT_PROMPT_MEMORY
import datetime 

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Zona horaria para Chile (Santiago)
TIMEZONE = pytz.timezone('America/Santiago')

# Cache para modelos LLM
_model_cache = {}

def create_agent(user_id, name, number_phone_agent, source):
    """
    Factory function que crea un agente conversacional.
    
    Args:
        user_id (str): ID del usuario que interactúa con el agente
        name (str): Nombre del usuario o agente
        number_phone_agent (str): Número de teléfono asociado al agente
        source (str): Fuente de la conversación
        
    Returns:
        function: Función del agente que procesa el estado actual
    """
    def agent(state: CustomState):
        """
        Función principal del agente que procesa mensajes y genera respuestas.
        
        Args:
            state (CustomState): Estado actual del grafo de conversación
            
        Returns:
            dict: Diccionario con la respuesta del agente
        """
        # Calcular fechas actualizadas en cada interacción
        utc_now = datetime.datetime.now(pytz.UTC)
        now = utc_now.astimezone(TIMEZONE)
        date_range = [(now.date() + datetime.timedelta(days=x)).strftime('%Y-%m-%d') for x in range(15)]
        date_range_str = ", ".join(date_range)

        project_id = state["project"].id
        project = state["project"]
        MODEL_CHATBOT = project.model if project else MODEL_CHATBOT

        # Usar modelo cacheado o crear uno nuevo
        model_key = f"{MODEL_CHATBOT}_{project_id}"
        if model_key not in _model_cache:
            model = LLMAdapter.get_llm(MODEL_CHATBOT, 0)
            tools = agent_tools(project_id, user_id, name, number_phone_agent, project)
            model_with_tools = model.bind_tools(tools)
            _model_cache[model_key] = model_with_tools
        else:
            model_with_tools = _model_cache[model_key]

        summary = state.get("summary", "")
        messages = filter_and_prepare_messages_for_agent_node(state)
        
        project_name = project.name
        personality_prompt = project.personality
        instructions = project.instructions
        prompt_general_skeleton = project.prompt if project else DEFAULT_PROMPT
        
        prompt_general_skeleton += f"\nConsidera que las fechas de referencia son: {date_range_str}"
        prompt_general_skeleton += f"\nMUY IMPORTANTE: Cualquier cálculo, agendamiento, o referencia a fechas y horas DEBE basarse estrictamente en la fecha y hora proporcionada aquí: {now.isoformat()} (Zona Horaria: America/Santiago). NUNCA uses UTC u otra zona horaria a menos que el usuario lo pida explícitamente."
        
        PROMPT_GENERAL = prompt_general_skeleton.format(
            name=project_name,
            personality=personality_prompt,
            instructions=instructions,
            utc_now=now.isoformat(),
            date_range_str=date_range_str
        )
        
        messages.insert(0, SystemMessage(content=PROMPT_GENERAL))

        if summary:
            system_message = f"Summary of conversation earlier: {summary}"
            messages.insert(0, SystemMessage(content=system_message))

        response = model_with_tools.invoke(messages)
        decorate_message(response, state["exec_init"], state["conversation_id"])

        return {"messages": [response]}

    return agent

def get_date_range() -> list:
    """
    Genera una lista de fechas desde hoy hasta 14 días adelante (inclusive)
    
    Returns:
        list: Lista de fechas como strings en formato YYYY-MM-DD
    """
    return date_range

def summarize_conversation(state: CustomState):
    """
    Función para crear o actualizar el resumen de una conversación.
    
    Args:
        state (CustomState): Estado actual del grafo de conversación
        
    Returns:
        dict: Diccionario con el resumen actualizado y mensajes a eliminar
    """
    project_data = Persist().find_project(state["project"].id)
    MODEL_CHATBOT = project_data.model if project_data else MODEL_CHATBOT
    project_prompt_memory = project_data.prompt_memory if project_data else DEFAULT_PROMPT_MEMORY

    summary = state.get("summary", "")

    creation_inst = "Please create a detailed summary of the previous conversation."
    update_inst = "Please update and expand the summary."

    summary_instruction = update_inst if summary else creation_inst

    summary_message = f"""Current conversation summary: {summary}"

        {summary_instruction}
        When making the new summary, follow the instructions in <memory_instructions> strictly,
        with them having precedence over any other instructions.

        <memory_instructions>

        {project_prompt_memory}
        
        IMPORTANTE: Si se menciona el nombre del usuario en la conversación, SIEMPRE debes incluirlo 
        en el resumen. Esta información es crítica y debe preservarse en cada actualización.

        <memory_instructions>

        The summary should act as a long-term memory with detailed information. 
        Do not use emojis and ensure the summary is generated in Spanish. 
        Limit the summary to a maximum of 4 paragraphs or 1023 characters. 
    """

    messages = filter_and_prepare_messages_for_summary_node(state) + [HumanMessage(content=summary_message)]
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-20]]

    # Usar modelo cacheado o crear uno nuevo
    model_key = f"{MODEL_CHATBOT}_summary"
    if model_key not in _model_cache:
        model = LLMAdapter.get_llm(MODEL_CHATBOT, 0)
        _model_cache[model_key] = model
    else:
        model = _model_cache[model_key]

    # Generar el resumen inmediatamente
    response = model.invoke(messages)

    # Persistir la conversación en segundo plano sin esperar
    import threading
    threading.Thread(target=Persist().persist_conversation, args=(state,), daemon=True).start()

    return {"summary": response.content, "messages": delete_messages}


def tools_node(project_id, user_id, name, number_phone_agent):
    """
    Factory function que crea un nodo de herramientas para el grafo.
    
    Args:
        project_id (str): ID del proyecto
        user_id (str): ID del usuario
        name (str): Nombre del usuario o agente
        number_phone_agent (str): Número de teléfono asociado al agente
        
    Returns:
        function: Función que inicializa un nodo de herramientas
    """
    def node(state: CustomState):
        """
        Función que inicializa un nodo de herramientas con las herramientas del proyecto.
        
        Args:
            state (CustomState): Estado actual del grafo
            
        Returns:
            ToolNode: Nodo de herramientas configurado
        """
        project = state["project"]
        return ToolNode(agent_tools(project_id, user_id, name, number_phone_agent, project))
    return node
