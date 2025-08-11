"""
Agente especializado para streaming que devuelve chunks en tiempo real
"""
import logging
import datetime
import pytz
from langchain_core.messages import SystemMessage, HumanMessage
from app.controler.chat.core.state import CustomState  
from app.controler.chat.core.utils import decorate_message
from app.controler.chat.core.llm_adapter import LLMAdapter
from app.controler.chat.core.tools import agent_tools
from app.controler.chat.core.nodes import filter_and_prepare_messages_for_agent_node, get_date_range, TIMEZONE
from app.resources.constants import DEFAULT_PROMPT, MODEL_CHATBOT

def create_streaming_agent(user_id, name, number_phone_agent, source):
    """
    Factory function que crea un agente con soporte nativo para streaming.
    
    Args:
        user_id (str): ID del usuario que interactúa con el agente
        name (str): Nombre del usuario o agente
        number_phone_agent (str): Número de teléfono asociado al agente
        source (str): Fuente de la conversación
        
    Returns:
        function: Función del agente que procesa el estado y hace streaming
    """
    def streaming_agent(state: CustomState):
        """
        Función principal del agente con streaming real del modelo LLM.
        
        Args:
            state (CustomState): Estado actual del grafo de conversación
            
        Returns:
            dict: Diccionario con la respuesta del agente (streaming se maneja por separado)
        """
        # Calcular fechas actualizadas en cada interacción
        utc_now = datetime.datetime.now(pytz.UTC)
        now = utc_now.astimezone(TIMEZONE)
        date_range = [(now.date() + datetime.timedelta(days=x)).strftime('%Y-%m-%d') for x in range(15)]
        date_range_str = ", ".join(date_range)

        project_id = state["project"].id
        project = state["project"]
        MODEL_CHATBOT = project.model if project else MODEL_CHATBOT

        # 🎯 CLAVE: Inicializar modelo con streaming habilitado
        model = LLMAdapter.get_llm(MODEL_CHATBOT)  # Sin temperature para compatibilidad
        
        # Verificar si el modelo soporta streaming
        if hasattr(model, 'streaming') and not model.streaming:
            # Habilitar streaming si está disponible
            try:
                model.streaming = True
                logging.info(f"Streaming habilitado para modelo {MODEL_CHATBOT}")
            except Exception as e:
                logging.warning(f"No se pudo habilitar streaming en modelo: {e}")
        
        summary = state.get("summary", "")
        # Filtra y prepara los mensajes para el agente
        messages = filter_and_prepare_messages_for_agent_node(state)
        
        # Obtiene las herramientas disponibles para el agente
        tools = agent_tools(project_id, user_id, name, number_phone_agent, project)
        logging.info(f"Herramientas disponibles para el agente: {[getattr(tool, 'name', getattr(tool, '__name__', str(tool))) for tool in tools]}")
        
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

        # 🚀 AQUÍ ESTÁ LA DIFERENCIA: Para streaming, solo invocamos normalmente
        # El streaming se maneja en el servicio de streaming usando astream()
        response = model_with_tools.invoke(messages)
        decorate_message(response, state["exec_init"], state["conversation_id"])

        return {"messages": [response]}

    return streaming_agent


def create_agent_with_streaming_support(user_id, name, number_phone_agent, source):
    """
    Función que crea el agente que mejor soporte streaming según el modelo configurado
    """
    return create_streaming_agent(user_id, name, number_phone_agent, source) 