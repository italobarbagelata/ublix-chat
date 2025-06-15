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
        
        now_chile = datetime.datetime.now(pytz.timezone("America/Santiago")).isoformat()
        logging.info(f"now_chile: {now_chile}")

        project_id = state["project"].id
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
        
        prompt_general_skeleton = prompt_general_skeleton.replace("{name}", project_name)
        prompt_general_skeleton = prompt_general_skeleton.replace("{personality}", personality_prompt)
        prompt_general_skeleton = prompt_general_skeleton.replace("{instructions}", instructions)
        prompt_general_skeleton = prompt_general_skeleton.replace("{utc_now}", now.isoformat())
        prompt_general_skeleton = prompt_general_skeleton.replace("{date_range_str}", date_range_str)
        prompt_general_skeleton = prompt_general_skeleton.replace("{now_chile}", now_chile)
        
        prompt_general_skeleton += f"""
        MANEJO DE FECHAS, HORA Y FERIADOS  (INSTRUCCIONES TÉCNICAS):
        
        Zona Horaria y Fechas:
        - Todas las fechas y horas se manejan en zona horaria de Chile (America/Santiago, UTC-3)
        - Hora actual en Chile: {now_chile}
        - Rango de fechas de referencia: {date_range_str}

        Conversión y Validación:
        - Las expresiones relativas como "hoy", "mañana", "próximo lunes" deben convertirse a fechas absolutas.
        - Siempre incluir la fecha completa en formato DD-MM-YYYY y hora en formato 24h.
        - Siempre usar la herramienta current_datetime_tool para obtener la fecha exacta antes de responder.
        - Si el usuario menciona una fecha, siempre usar la herramienta current_datetime_tool para obtener la fecha exacta antes de responder.

        Herramientas disponibles:
        1. `current_datetime_tool`: para obtener información de una fecha específica (día de semana, hora, etc.)
        2. `check_chile_holiday_tool`: para verificar si una fecha es feriado nacional o local (OBLIGATORIO ANTES DE AGENDAR)
        3. `week_info_tool`: para obtener rango semanal y días hábiles
        4. `next_chile_holidays_tool`: para sugerir próximos días no hábiles

        Flujo para procesar una fecha:
        1. Convertir la entrada a fecha absoluta si es relativa (ej. "mañana")
        2. Verificar si la fecha es válida usando `current_datetime_tool`
        3. Validar si es hábil con `check_chile_holiday_tool`
        4. Si la fecha es válida, continuar según las reglas de negocio

        NUNCA calcular fechas manualmente
        SIEMPRE usar las herramientas para validar y responder
        Está terminantemente prohibido asumir el día de la semana de una fecha sin usar la herramienta current_datetime_tool. Siempre debes consultar el día exacto usando esa herramienta antes de responder.
        """
        
        prompt_general_skeleton += f"""
        MANEJO DE INFORMACIÓN DE CONTACTO:
        1. Cuando el usuario proporcione su información de contacto (nombre, email, teléfono):
        - Detecta automáticamente esta información
        - Usa la herramienta save_contact_tool para guardarla
        - Confirma al usuario que has guardado su información
        - Continúa la conversación normalmente
        2. Si el usuario actualiza su información:
        - Detecta los cambios
        - Actualiza la información usando save_contact_tool
        - Confirma la actualización
        3. Mantén un tono profesional al manejar información personal
        4. NO pidas información de contacto si el usuario no la ha proporcionado voluntariamente
        """
        
        PROMPT_GENERAL = prompt_general_skeleton
        
        logging.info(f"PROMPT_GENERAL: {PROMPT_GENERAL}")
        
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