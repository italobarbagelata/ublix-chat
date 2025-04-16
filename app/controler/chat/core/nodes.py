import concurrent.futures
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
from app.controler.chat.classes.token_counter import TokenCounter

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Zona horaria para Chile (Santiago)
TIMEZONE = pytz.timezone('America/Santiago')

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
        logging.info("========= INICIO DE AGENTE =========")
        project_id = state["project"].id  # Obtiene el ID del proyecto del estado
        project = state["project"]  # Obtiene el objeto proyecto completo
        MODEL_CHATBOT = project.model if project else MODEL_CHATBOT  # Determina el modelo a usar
        logging.info(f"model_chatbot: {MODEL_CHATBOT}")

        # Inicializa el modelo LLM según la configuración
        model = LLMAdapter.get_llm(MODEL_CHATBOT, 0)
        summary = state.get("summary", "")  # Obtiene el resumen de la conversación
        # Filtra y prepara los mensajes para el agente
        messages = filter_and_prepare_messages_for_agent_node(state)

        # Obtiene las herramientas disponibles para el agente
        tools = agent_tools(project_id, user_id, name, number_phone_agent, project)
        logging.info(f"Herramientas disponibles para el agente: {[tool.name for tool in tools]}")
        
        # Vincula las herramientas al modelo
        model_with_tools = model.bind_tools(tools)
        project_name = project.name
        personality_prompt = project.personality
        instructions = project.instructions
        prompt_general_skeleton = project.prompt if project else DEFAULT_PROMPT
        
        # Agrega información de rango de fechas al prompt
        date_range = get_date_range()
        date_range_str = ", ".join(date_range)
        prompt_general_skeleton += f"\nConsidera que las fechas de referencia son: {date_range_str}"

        # Obtiene la fecha actual en la zona horaria de Chile
        now = datetime.datetime.now(TIMEZONE)
        utc_now = now.astimezone(pytz.UTC).isoformat()

        # Formatea el prompt general con los valores específicos del proyecto
        PROMPT_GENERAL = prompt_general_skeleton.format(
            name=project_name,
            personality=personality_prompt,
            instructions=instructions,
            utc_now=utc_now,
            date_range_str=date_range_str
        )

        logging.info("Prompt general configurado")
        
        # Inserta el prompt general como mensaje del sistema al inicio
        messages.insert(0, SystemMessage(content=PROMPT_GENERAL))

        # Si hay un resumen disponible, lo agrega como contexto adicional
        if summary:
            system_message = f"Summary of conversation earlier: {summary}"
            messages.insert(0, SystemMessage(content=system_message))

        logging.info("Enviando mensajes al modelo....")
        # Invoca el modelo con los mensajes preparados
        response = model_with_tools.invoke(messages)
        logging.info("Respuesta recibida del modelo")
        # Agrega metadatos a la respuesta (tiempo de ejecución, ID de conversación)
        decorate_message(response, state["exec_init"], state["conversation_id"])
        logging.info("========= FIN DE AGENTE =========")

        # Devuelve la respuesta como un diccionario con la clave 'messages'
        return {"messages": [response]}

    return agent

def get_date_range() -> list:
    """
    Genera una lista de fechas desde hoy hasta 14 días adelante (inclusive)
    
    Returns:
        list: Lista de fechas como strings en formato YYYY-MM-DD
    """
    today = datetime.datetime.now(TIMEZONE).date()
    date_range = [(today + datetime.timedelta(days=x)).strftime('%Y-%m-%d') for x in range(15)]
    return date_range

def summarize_conversation(state: CustomState):
    """
    Función para crear o actualizar el resumen de una conversación.
    
    Args:
        state (CustomState): Estado actual del grafo de conversación
        
    Returns:
        dict: Diccionario con el resumen actualizado y mensajes a eliminar
    """
    #logging.info(f"State\n{str(state)}")
    logging.info(state.get("unique_id") if state.get("unique_id") else "No Unique Id: " + " Node 2: The summarize_conversation has been initialized...")

    # Inicializar contador de tokens - Solo para logs, no bloquea el proceso principal
    token_counter = TokenCounter()
    
    # Recupera datos del proyecto desde la base de datos
    project_data = Persist().find_project(state["project"].id)
    MODEL_CHATBOT = project_data.model if project_data else MODEL_CHATBOT
    project_prompt_memory = project_data.prompt_memory if project_data else DEFAULT_PROMPT_MEMORY

    # Obtiene el resumen actual si existe
    summary = state.get("summary", "")

    # Determina si debe crear un nuevo resumen o actualizar uno existente
    creation_inst = "Please create a detailed summary of the previous conversation."
    update_inst = "Please update and expand the summary."

    summary_instruction = update_inst if summary else creation_inst

    # Prepara el mensaje para la generación del resumen
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

    # Conteo básico de tokens para logs (no bloqueante) en un hilo separado
    def log_token_counts():
        try:
            # Conteos mínimos para logs, sin afectar rendimiento
            summary_message_tokens = token_counter.count_tokens(summary_message)
            current_summary_tokens = token_counter.count_tokens(summary) if summary else 0
            logging.info(f"Summary message tokens: {summary_message_tokens}")
            logging.info(f"Current summary tokens: {current_summary_tokens}")
        except Exception as e:
            logging.warning(f"Error contando tokens para logs: {e}")
    
    # Ejecutar conteo en segundo plano para logs
    import threading
    threading.Thread(target=log_token_counts, daemon=True).start()

    logging.info("Initializing summarize creation or update...")

    # Filtra y prepara los mensajes para la generación del resumen
    messages = filter_and_prepare_messages_for_summary_node(state) + [HumanMessage(content=summary_message)]
    
    # Marca los mensajes antiguos para eliminación (mantiene solo los últimos 20)
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-20]]
    logging.info(f"Delete Messages:\n{delete_messages}")

    # Utiliza ejecución concurrente para persistir la conversación y generar el resumen
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Guarda la conversación en la base de datos de forma asíncrona (completamente en segundo plano)
        # No esperaremos por su finalización
        executor.submit(Persist().persist_conversation, state)

        # Inicializa el modelo para la generación del resumen
        model_summary = LLMAdapter.get_llm(MODEL_CHATBOT, 0)

        # Genera el resumen y esperamos solo por este resultado
        summary_future = executor.submit(model_summary.invoke, messages)
        logging.info(state.get("unique_id") if state.get("unique_id") else "No Unique Id: " + " Node 2: The summarize_conversation has been sucessfully executed...")

        # Solo esperamos por el resumen, no por la persistencia
        response = summary_future.result()
        # Ya no esperamos por persist_future.result()

    # Registrar conteo del nuevo resumen en segundo plano (no bloqueante)
    def log_new_summary_tokens():
        try:
            new_summary_tokens = token_counter.count_tokens(response.content)
            current_summary_tokens = token_counter.count_tokens(summary) if summary else 0
            token_difference = new_summary_tokens - current_summary_tokens
            logging.info(f"New summary tokens: {new_summary_tokens}")
            logging.info(f"Summary token difference: {token_difference}")
        except Exception as e:
            logging.warning(f"Error contando tokens del nuevo resumen: {e}")
    
    # Ejecutar conteo en segundo plano
    threading.Thread(target=log_new_summary_tokens, daemon=True).start()

    # Devuelve el resumen generado y los mensajes a eliminar
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
