import logging
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import ToolNode
from langchain_core.messages import RemoveMessage, SystemMessage
import pytz
import concurrent.futures
from app.controler.chat.core.state import CustomState
from app.controler.chat.core.tools import agent_tools
from app.controler.chat.core.tools_cache import ToolsCache, cached_tools
from app.controler.chat.core.utils import decorate_message, filter_and_prepare_messages_for_agent_node, filter_and_prepare_messages_for_summary_node
from app.controler.chat.store.persistence import Persist
from app.controler.chat.core.llm_adapter import LLMAdapter
from dotenv import load_dotenv
from app.resources.constants import DEFAULT_PROMPT, MODEL_CHATBOT
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
        project_id = state["project"].id
        model = LLMAdapter.get_llm(MODEL_CHATBOT, 0)
        summary = Persist().get_summary(state)
        messages = filter_and_prepare_messages_for_agent_node(state)
        
        tools = await agent_tools(project_id, user_id, name, number_phone_agent, unique_id, project)
        
        model_with_tools = model.bind_tools(tools)
        project_name = project.name
        personality_prompt = project.personality
        instructions = project.instructions
        
        prompt_general_skeleton = project.prompt if project else DEFAULT_PROMPT
        
        if summary and summary.strip():
            prompt_general_skeleton += f"""
            RESUMEN DE CONVERSACIÓN ANTERIOR:
            
            {summary}
            
            IMPORTANTE: Usa esta información para NO repetir preguntas que ya fueron respondidas.
            """
            logging.info(f"summary: {summary}")
        
        prompt_general_skeleton = prompt_general_skeleton.replace("{name}", project_name)
        prompt_general_skeleton = prompt_general_skeleton.replace("{personality}", personality_prompt)
        prompt_general_skeleton = prompt_general_skeleton.replace("{instructions}", instructions)
        prompt_general_skeleton = prompt_general_skeleton.replace("{utc_now}", now.isoformat())
        prompt_general_skeleton = prompt_general_skeleton.replace("{date_range_str}", date_range_str)
        prompt_general_skeleton = prompt_general_skeleton.replace("{now_chile}", now_chile)
        
        prompt_general_skeleton += f"""        
        CONTEXTO TEMPORAL Y GEOGRÁFICO:
        - Zona horaria: America/Santiago (Chile)

        
        FORMATO DE URLs:
        - Usar markdown: [texto](url)
        - Ejemplo: [Ver producto](https://www.ublix.app/producto/123)

        🚨 GESTIÓN DE DATOS DE CONTACTO (save_contact_tool):
        - Usa esta herramienta para guardar o actualizar la información del usuario (nombre, email, teléfono, o campos personalizados definidos en las instrucciones).
        - Puedes llamarla sin parámetros para verificar los datos que ya tienes.
        - Las instrucciones del proyecto te indicarán qué datos solicitar y cuándo.
        """
            
        if "email" in project.enabled_tools:
                prompt_general_skeleton += f"""
                EMAIL (send_email):
                Herramienta para enviar correos.
                - Parámetros: from_email, to, subject, html/text, cc, bcc, reply_to.
                - El `from_email` por defecto es "noreply@ublix.app".
                - El parámetro `to` puede recibir múltiples correos separados por coma.
                """   
        if "api" in project.enabled_tools:
                prompt_general_skeleton += f"""
                API TOOLS DINÁMICAS (api_tool):
                Herramientas API personalizadas configuradas específicamente para este proyecto.
                Las funciones disponibles se generan dinámicamente basadas en las configuraciones de API almacenadas.
                Cada API tiene su propia configuración de endpoints, parámetros y métodos HTTP.
                Usa estas herramientas cuando necesites interactuar con APIs externas específicas del proyecto.
                """
        if "unified_search" in project.enabled_tools:
                prompt_general_skeleton += f"""
                UNIFIED SEARCH (unified_search_tool):
                Herramienta de búsqueda principal. Úsala para responder a las consultas de los usuarios buscando en la base de conocimiento del proyecto (FAQs, documentos, productos).
                Para obtener los mejores resultados, úsala con la consulta del usuario sin modificar.
                Las instrucciones del proyecto pueden requerir que uses esta herramienta antes de intentar responder desde tu conocimiento general.
                """ 
        if "agenda_tool" in project.enabled_tools:
            prompt_general_skeleton += f"""
            AGENDA_TOOL (agenda_tool):
            Herramienta para agendar citas. Tiene dos modos de operación principales definidos por `workflow_type`:
            1. `BUSQUEDA_HORARIOS`: Busca horarios disponibles. Requiere `start_datetime` (la fecha para buscar) y `title` (la consulta del usuario, ej: "horas para la tarde").
            2. `AGENDA_COMPLETA`: Confirma y agenda una cita. Requiere todos los detalles del evento, incluyendo el `start_datetime` exacto elegido por el usuario y la información del contacto. **Si el contacto tiene campos adicionales (additional_fields), debes pasarlos también en este workflow.**
            
            Usa `current_datetime_tool` y `check_chile_holiday_tool` para validar fechas antes de buscar horarios.
            Las instrucciones específicas del proyecto te indicarán el flujo exacto a seguir para solicitar datos y confirmar la cita.
            """
        if "image_processor" in project.enabled_tools:
            prompt_general_skeleton += f"""
            IMAGE_PROCESSOR (image_processor):
            Herramienta para procesar imágenes enviadas por el usuario.
            - Parámetros: image_url (URL de la imagen a procesar)
            - Función: Extrae todo el texto visible en la imagen
            
            🚨 DETECCIÓN AUTOMÁTICA DE IMÁGENES - OBLIGATORIO:
            - Cuando detectes el patrón ![Imagen](URL) en un mensaje, es OBLIGATORIO llamar a image_processor
            - NO respondas sobre la imagen sin usar la herramienta primero
            - SIEMPRE debes detectar este patrón y extraer la URL
            - Llama inmediatamente a image_processor con la URL extraída
            - CRÍTICO: SIEMPRE usa el resultado del image_processor en tu respuesta
            - PROHIBIDO decir "no he podido leer la imagen" - usa siempre el texto extraído
            - Menciona qué texto encontraste y luego sigue las instrucciones específicas del proyecto
            
            Ejemplo de uso:
            1. Usuario envía imagen → aparece como ![Imagen](https://storage.url/imagen.jpg)
            2. Extraer URL: https://storage.url/imagen.jpg
            3. Llamar: image_processor(image_url="https://storage.url/imagen.jpg")
            4. Usar el texto extraído según las instrucciones del proyecto
            """
            
            
        # Log para debug de imágenes y prompt
        #for msg in messages:
        #    if hasattr(msg, 'content') and '![Imagen](' in str(msg.content):
        #        logging.info(f"🖼️ IMAGEN DETECTADA EN MENSAJE: {msg.content}")
        
        # Log del prompt específico del proyecto cuando hay imágenes
        #if any('![Imagen](' in str(msg.content) for msg in messages if hasattr(msg, 'content')):
        #    logging.info(f"📝 PROMPT ESPECÍFICO DEL PROYECTO:\n{project.prompt}")
        #    logging.info(f"📝 PROMPT COMPLETO FINAL:\n{prompt_general_skeleton}")
                
        messages.insert(0, SystemMessage(content=prompt_general_skeleton))

        logging.info(f"🔧 TOOLS DISPONIBLES: {[getattr(tool, 'name', getattr(tool, '__name__', str(tool))) for tool in tools]}")
        response = model_with_tools.invoke(messages)
        decorate_message(response, state["exec_init"], state["conversation_id"])

        return {"messages": [response]}

    return agent

def get_tools_summary(enabled_tools: list) -> str:
    """
    Genera un resumen dinámico de las herramientas habilitadas basado en enabled_tools
    """
    tools_descriptions = {
        "unified_search": "🔍 unified_search_tool: Búsqueda unificada en documentos, FAQs y productos",
        "retriever": "📚 document_retriever: Búsqueda en documentos específicos del proyecto",
        "faq_retriever": "❓ faq_retriever: Búsqueda en preguntas frecuentes",
        "products_search": "🛍️ search_products_unified: Búsqueda de productos en el catálogo",
        "calendar": "📅 google_calendar_tool: Gestión completa de calendario Google",
        "email": "📧 send_email: Envío de emails profesionales",
        "contact": "👤 save_contact_tool: Gestión de información de contacto",
        "tienda": "🏪 Herramientas de tienda: buscar_productos_tienda, consultar_info_tienda, gestionar_carrito",
        "openai_vector": "🤖 openai_vector_search: Búsqueda vectorial en documentos",
        "api": "🔌 API Tools: Herramientas dinámicas generadas según configuración del proyecto",
        "image_processor": "🖼️ image_processor: Análisis y procesamiento de imágenes",
        "mongo_db": "🗄️ mongo_db_tool: Operaciones en base de datos MongoDB",
        "agenda_tool": "🗓️ agenda_tool: Gestión de horarios y agendamiento con Google Calendar",
        "agenda_smart_booking_tool": "🗓️ agenda_smart_booking_tool: Gestión de horarios y agendamiento con Google Calendar"
    }
    
    # Herramientas que siempre están disponibles
    always_available = [
        "📅 current_datetime_tool, week_info_tool: Información de fecha y hora actual",
        "🎌 check_chile_holiday_tool, next_chile_holidays_tool: Verificación de feriados chilenos",
        "👤 save_contact_tool: Gestión de contactos"
    ]
    
    summary = []
    
    # Añadir herramientas habilitadas
    for tool in enabled_tools:
        if tool in tools_descriptions:
            summary.append(f"  • {tools_descriptions[tool]}")
    
    # Añadir herramientas siempre disponibles
    for tool in always_available:
        summary.append(f"  • {tool}")
    
    if summary:
        return "Las siguientes herramientas están disponibles:\n" + "\n".join(summary)
    else:
        return "Solo las herramientas básicas de fecha y contacto están disponibles."

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
