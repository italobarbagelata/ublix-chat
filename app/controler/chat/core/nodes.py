import logging
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import ToolNode
from langchain_core.messages import RemoveMessage, SystemMessage
import pytz
import concurrent.futures
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


async def create_agent(user_id, name, number_phone_agent, source, unique_id, project):
    async def agent(state: CustomState):
        # Calcular fechas actualizadas en cada interacción
        utc_now = datetime.datetime.now(pytz.UTC)
        now = utc_now.astimezone(TIMEZONE)
        date_range = [(now.date() + datetime.timedelta(days=x)).strftime('%Y-%m-%d') for x in range(15)]
        date_range_str = ", ".join(date_range)

        project_id = state["project"].id
        logging.info(f"{unique_id} project: {project}")
        MODEL_CHATBOT = project.model if project else MODEL_CHATBOT
        logging.info(f"{unique_id} model_chatbot: {MODEL_CHATBOT}")

        # Inicializa el modelo LLM según la configuración
        model = LLMAdapter.get_llm(MODEL_CHATBOT, 0)
        summary = Persist().get_summary(state)
        # Filtra y prepara los mensajes para el agente
        messages = filter_and_prepare_messages_for_agent_node(state)
        
        # Obtiene las herramientas disponibles para el agente
        # tools = asyncio.run(agent_tools(project_id, user_id, name, number_phone_agent, unique_id))
        tools = await agent_tools(project_id, user_id, name, number_phone_agent, unique_id, project)
        
        # Vincula las herramientas al modelo
        model_with_tools = model.bind_tools(tools)
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
    utc_now = datetime.datetime.now(pytz.UTC)
    now = utc_now.astimezone(TIMEZONE)
    date_range = [(now.date() + datetime.timedelta(days=x)).strftime('%Y-%m-%d') for x in range(15)]
    date_range_str = ", ".join(date_range)
    return date_range_str

def resume_conversation(state: CustomState):
    logging.info(str(state))
    logging.info(state["unique_id"] + " Node 2: The resume conversation has been initialized...")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.submit(Persist().persist_conversation, state)

    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-20]]
    logging.info(f"Delete Messages:\n {delete_messages}")

    return {"messages": delete_messages}


async def tools_node(project_id, user_id, name, number_phone_agent, unique_id, project):
    logging.info(unique_id + " Initiating tools node...")
    tools = await agent_tools(project_id, user_id, name, number_phone_agent, unique_id, project)
    return ToolNode(tools)