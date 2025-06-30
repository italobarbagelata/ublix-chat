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
        
        
        
        #prompt_general_skeleton = prompt_general_skeleton.replace("{instructions}", instructions)
        instructions_message = SystemMessage(content=instructions)
        messages.insert(0, instructions_message)
        
        prompt_general_skeleton = prompt_general_skeleton.replace("{utc_now}", now.isoformat())
        prompt_general_skeleton = prompt_general_skeleton.replace("{date_range_str}", date_range_str)
        prompt_general_skeleton = prompt_general_skeleton.replace("{now_chile}", now_chile)
        
        prompt_general_skeleton += f"""        
        CONTEXTO TEMPORAL Y GEOGRÁFICO:
        - Zona horaria: America/Santiago (Chile)
        - Fecha y hora actual: {now_chile}
        - Fechas de referencia próximas: {date_range_str}
        
        FORMATO DE URLs:
        - Usar markdown: [texto](url)
        - Ejemplo: [Ver producto](https://www.ublix.app/producto/123)

        ANTES DE PREGUNTAR CUALQUIER INFORMACIÓN:
        1. EJECUTA save_contact_tool() SIN PARÁMETROS para obtener datos existentes del usuario.
        2. SIEMPRE debes obtener y guardar TODOS los campos configurados en la tabla de contactos, solicitando al usuario la información faltante.
        3. SOLO si existe una instrucción explícita en el proyecto que indique que NO se debe guardar un campo específico, NO lo solicites ni lo guardes.
        4. Si el usuario no entrega la información, vuelve a pedirla de forma cordial y profesional.
        
        🚨 REGLA CRÍTICA: SIEMPRE ejecutar save_contact_tool() al inicio para obtener datos del usuario
        
        HERRAMIENTAS DISPONIBLES:
        {get_tools_summary(project.enabled_tools if project.enabled_tools else [])}        
        """
            
        if "email" in project.enabled_tools:
                prompt_general_skeleton += f"""
                EMAIL (send_email):
                API: Resend | Params: from_email, to, subject, html/text, cc, bcc, reply_to
                Default from: "noreply@ublix.app" | Multi emails: "email1@domain.com, email2@domain.com"
                Use when: user wants to send email, mentions "enviar email", "mandar correo"
                Examples: send_email(to="user@domain.com", subject="Test", html="<h1>Hola</h1>")
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
                INSTRUCCIÓN CRÍTICA - OBLIGATORIA:
                - ANTES de responder CUALQUIER consulta del usuario, SIEMPRE ejecuta unified_search_tool
                - NO respondas NUNCA sin haber buscado primero con unified_search_tool
                - Usa unified_search_tool con la consulta exacta del usuario
                - Esta herramienta busca automáticamente en FAQs, documentos y productos
                - Solo después de obtener resultados, procede a responder
                - Si no hay resultados relevantes, entonces puedes responder basándote en tu conocimiento
                - Esta regla es ABSOLUTA y no tiene excepciones
                - unified_search_tool es la HERRAMIENTA PRINCIPAL de búsqueda híbrida
                """ 
        if "agenda_tool" in project.enabled_tools:
            prompt_general_skeleton += f"""
            AGENDA_TOOL - HERRAMIENTA PROFESIONAL DE AGENDAMIENTO:
            
            🚨 WORKFLOW DE AGENDAMIENTO OBLIGATORIO (SEGUIR PASOS EN ORDEN):
            
            Paso 1: VERIFICAR FERIADO (OBLIGATORIO)
            - Si el usuario menciona una fecha para agendar, TU PRIMERA ACCIÓN SIEMPRE DEBE SER llamar a `check_chile_holiday_tool`.
            - NO respondas, NO saludes, NO intentes buscar horarios. Llama a la herramienta PRIMERO.
            - Ejemplo: Si el usuario dice "agendar para el 2 de julio", tu llamas a `check_chile_holiday_tool(date='2 de julio')`.
            
            Paso 2: ANALIZAR RESPUESTA DEL VERIFICADOR
            - SI la herramienta responde que ES FERIADO: Informa al usuario que no se puede agendar y sugiere elegir otra fecha. NO continúes al paso 3.
            - SI la herramienta responde que NO ES FERIADO: Continúa al paso 3.
            
            Paso 3: BUSCAR/AGENDAR HORARIOS
            - USA `agenda_tool` para buscar horarios o agendar la cita.
            - NUNCA inventes fechas ni horarios. SOLO muestra lo que `agenda_tool` te devuelva.

            📋 OTROS WORKFLOWS PRINCIPALES:
            1. BUSCAR HORARIOS: agenda_tool(workflow_type="BUSQUEDA_HORARIOS", title="consulta del usuario")
               → Para buscar y mostrar horarios disponibles.
               → Ejemplo: "¿qué horarios tienes?", "cuándo puedes atenderme?"
            
            2. AGENDAR CITA: agenda_tool(workflow_type="AGENDA_COMPLETA", title="motivo de la cita", start_datetime="YYYY-MM-DDTHH:MM:SS", ...)
               → Para agendar una cita detallada.
               → REQUISITO OBLIGATORIO: fecha/hora específica (start_datetime).
                → PARÁMETROS OPCIONALES RECOMENDADOS:
                  - attendee_email: para notificar al cliente.
                  - attendee_name: para personalizar el evento.
                  - attendee_phone: para tener contacto directo.
                  - description: para añadir notas o un temario.
                  - end_datetime: para definir una duración específica.
                  - conversation_summary: para enviar contexto a sistemas externos (webhooks).
                → Usa include_meet=False para citas que no requieran videollamada (ej: presenciales o telefónicas).
            
            3. OTROS WORKFLOWS:
               - ACTUALIZACION_COMPLETA: Modificar eventos existentes.
               - CANCELACION_WORKFLOW: Cancelar eventos.
               - COMUNICACION_EVENTO: Consultar detalles de eventos.
            
            🔄 FLUJO RECOMENDADO:
            1. Usuario pregunta por horarios → Usar BUSQUEDA_HORARIOS.
            2. Usuario elige un horario → Usar AGENDA_COMPLETA para confirmar la cita.
            3. Si se requiere notificar al cliente, solicita su email antes de agendar.
            
            ⚠️ IMPORTANTE: agenda_tool se conecta con Google Calendar, puede enviar emails y puede crear videollamadas de Google Meet.

            REGLAS DE INTERACCIÓN PARA AGENDAMIENTO:

            - Si el usuario consulta por horarios pero NO indica una fecha específica, SIEMPRE pídele que indique el día y el mes.
                - Ejemplo de respuesta: "¿Podrías indicarme el día y el mes exactos para buscar horarios disponibles?"

            - Si el usuario solo menciona el día (ej: "el 15"), asume el mes actual, pero SIEMPRE confirma con el usuario antes de continuar.
                - Ejemplo: "¿Te refieres al 15 de [mes actual]? Por favor confirma el mes."

            - Si el usuario menciona "mañana" o "próxima semana", solicita que indique el día y el mes exactos para evitar confusiones.
                - Ejemplo: "Para buscar horarios, por favor indícame el día y el mes exactos."

            - Nunca inventes fechas ni asumas información sin confirmación del usuario.

            - Si el usuario no entrega la información mínima (día y mes para buscar, o fecha/hora para agendar), no muestres horarios y solicita los datos faltantes de forma amable.

            - Prioriza siempre la CLARIDAD y la CONFIRMACIÓN antes de agendar.
            """
            
            

                
        messages.insert(0, SystemMessage(content=prompt_general_skeleton))

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
