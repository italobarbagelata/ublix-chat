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
from app.controler.chat.store.persistence_state import MemoryStatePersistence
from app.controler.chat.classes.token_metrics import TokenMetrics
from app.controler.chat.core.llm_adapter import LLMAdapter
from app.controler.chat.core.prompt_templates import PromptTemplateBuilder
from dotenv import load_dotenv
from app.resources.constants import DEFAULT_PROMPT, MODEL_CHATBOT
import datetime
from app.core.logger_config import get_conversation_logger 

load_dotenv()

# La configuración de logging se maneja en logger_config.py

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
        project_id = state["project"].id
        model = LLMAdapter.get_llm(MODEL_CHATBOT)  # Sin temperature para compatibilidad
        summary = Persist().get_summary(state)
        messages = filter_and_prepare_messages_for_agent_node(state)
        
        # Obtener herramientas directamente sin caché
        tools = await agent_tools(
            project_id, user_id, name, number_phone_agent, unique_id, project
        )
        # Log de herramientas disponibles para la conversación
        conv_logger = get_conversation_logger(state.get('conversation_id', unique_id), user_id)
        tool_names = [getattr(t, 'name', 'herramienta') for t in tools]
        conv_logger.log_herramientas_cargadas(tool_names)
        
        model_with_tools = model.bind_tools(tools)
        
        # Usar el template manager para construir el prompt
        prompt_general_skeleton = PromptTemplateBuilder.build_system_prompt(
            project=project,
            summary=summary,
            utc_now=now.isoformat(),
            date_range_str=date_range_str,
            now_chile=now_chile
        )
        
        if summary and summary.strip():
            logging.debug(f"Resumen de conversación anterior cargado: {len(summary)} caracteres")
            
            
        # Log para debug de imágenes y prompt
        #for msg in messages:
        #    if hasattr(msg, 'content') and '![Imagen](' in str(msg.content):
        #        logging.info(f"🖼️ IMAGEN DETECTADA EN MENSAJE: {msg.content}")
        
        # Log del prompt específico del proyecto cuando hay imágenes
        #if any('![Imagen](' in str(msg.content) for msg in messages if hasattr(msg, 'content')):
        #    logging.info(f"📝 PROMPT ESPECÍFICO DEL PROYECTO:\n{project.prompt}")
        #    logging.info(f"📝 PROMPT COMPLETO FINAL:\n{prompt_general_skeleton}")
                
        messages.insert(0, SystemMessage(content=prompt_general_skeleton))
        
        #log prompt
        #logging.info(f"{unique_id} Prompt:\n{prompt_general_skeleton}")

        # Invocar modelo
        response = model_with_tools.invoke(messages)
        decorate_message(response, state["exec_init"], state["conversation_id"])

        # Guardar métricas de tokens para facturación
        try:
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata

                # Obtener el owner_id del proyecto para facturación
                project_owner_id = project.user_id

                # Crear objeto TokenMetrics
                token_metrics = TokenMetrics(
                    project_id=project_id,
                    user_id=user_id,  # Usuario que envió el mensaje (puede ser phone, UUID, etc)
                    conversation_id=state["conversation_id"],
                    message_id=response.id if hasattr(response, 'id') else unique_id,
                    timestamp=datetime.datetime.now(pytz.UTC),
                    tokens={
                        "input": usage.get('input_tokens', 0),
                        "output": usage.get('output_tokens', 0),
                        "total": usage.get('total_tokens', 0),
                        "system_prompt": 0,
                        "context": 0,
                        "tools": 0
                    },
                    source=source,
                    cost=None,  # Se puede calcular después si es necesario
                    project_owner_id=project_owner_id  # Para facturación
                )

                # Guardar en background para no bloquear
                persistence = MemoryStatePersistence()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    executor.submit(persistence.save_token_metrics, token_metrics)

                logging.info(f"Token metrics guardadas: {usage.get('total_tokens', 0)} tokens")
        except Exception as e:
            logging.error(f"Error al guardar token metrics: {e}")

        # Log de herramientas ejecutadas si las hay
        has_tool_calls = hasattr(response, 'tool_calls') and response.tool_calls
        if has_tool_calls:
            for tc in response.tool_calls:
                tool_name = tc.get('name', 'unknown') if isinstance(tc, dict) else getattr(tc, 'name', 'unknown')
                conv_logger.log_herramienta_ejecutada(tool_name)

        return {"messages": [response]}

    return agent



def resume_conversation(state: CustomState):
    # Persistir conversación en segundo plano
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.submit(Persist().persist_conversation, state)

    # Limpiar mensajes antiguos si hay más de 20
    messages = state.get("messages", [])
    if len(messages) > 20:
        delete_messages = [RemoveMessage(id=m.id) for m in messages[:-20]]
        logging.debug(f"Limpieza de memoria: eliminando {len(delete_messages)} mensajes antiguos")
    else:
        delete_messages = []

    return {"messages": delete_messages}

async def tools_node(project_id, user_id, name, number_phone_agent, unique_id, project):
    # Obtener herramientas directamente sin caché
    tools = await agent_tools(
        project_id, user_id, name, number_phone_agent, unique_id, project
    )
    # Log de configuración solo en modo debug
    logging.debug(f"Nodo de herramientas configurado con {len(tools)} herramientas")
    
    # Crear el ToolNode con las herramientas
    return ToolNode(tools)
