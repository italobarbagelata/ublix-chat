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

        🚨 GESTIÓN DE DATOS DE CONTACTO (REGLAS OBLIGATORIAS):

        Paso 1: DETERMINAR CAMPOS REQUERIDOS
        - Los campos base son `name`, `phone` y `email`.
        - Revisa las instrucciones del proyecto en busca de `CAMPOS_DE_CONTACTO: ['rut', 'ciudad', ...]`. Añade estos a tu lista de campos a gestionar.
        - **Regla de Obligatoriedad:** Por defecto, TODOS los campos (`name`, `phone` y los de `CAMPOS_DE_CONTACTO`) son obligatorios.
        - **Regla de Excepciones:** Revisa las instrucciones en busca de `CAMPOS_OPCIONALES: ['email', 'rut']`. Los campos en esta lista NO son obligatorios. `email` es opcional por defecto si no se especifica.

        Paso 2: OBTENER Y VALIDAR DATOS
        - Llama a `save_contact_tool()` sin parámetros para ver qué datos ya tienes.
        - Compara los datos existentes con tu lista de campos obligatorios del Paso 1.
        - Si faltan datos obligatorios, **DEBES SOLICITARLOS AL USUARIO**. Pide todo lo que falte de una vez.
        - Una vez que el usuario responda, vuelve a llamar a `save_contact_tool()` para guardar los datos.

        UNIFIED_SEARCH_TOOL:
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
            
            🚨 WORKFLOW DE AGENDAMIENTO OBLIGATORIO (SEGUIR ESTOS PASOS EN ORDEN ESTRICTO):
            
            Paso 1: OBTENER INTENCIÓN Y FECHA INICIAL
            - Cuando el usuario exprese su deseo de agendar (ej: "quiero agendar", "tienes hora para el jueves?"), tu primer objetivo es obtener una fecha.
            - **Validación de Fecha:** Usa `current_datetime_tool` para convertir días ("jueves") en fechas exactas (`YYYY-MM-DD`). NO INVENTES FECHAS.
            - **Verificación de Feriado:** Una vez que tengas una fecha, usa `check_chile_holiday_tool`. Si es feriado, informa al usuario y detén el proceso para esa fecha.
            
            Paso 2: BUSCAR HORARIOS DISPONIBLES
            - **Regla Crítica de Fecha:** La fecha obtenida en el Paso 1 **DEBE** ser pasada a `agenda_tool` usando el parámetro `start_datetime`.
            - **Regla de Persistencia de Fecha:** Si el usuario ya estableció un día y luego pregunta por otro horario (ej: '¿y más tarde?', '¿en la mañana?'), **DEBES** mantener la misma fecha (`start_datetime`) en la nueva búsqueda. La fecha solo cambia si el usuario menciona explícitamente otro día.
            - El parámetro `title` DEBE contener la pregunta más reciente del usuario sobre el horario.
            - **Ejemplo Correcto:**
                1. User: "para el viernes" -> `agenda_tool(workflow_type="BUSQUEDA_HORARIOS", start_datetime="2025-07-04", title="para el viernes")`
                2. User: "y para mas tarde?" -> `agenda_tool(workflow_type="BUSQUEDA_HORARIOS", start_datetime="2025-07-04", title="y para mas tarde?")` (Observa que `start_datetime` se mantiene)
            - **Regla de Salida:** Si la herramienta `agenda_tool` te devuelve un mensaje indicando que no hay horarios disponibles, tu ÚNICA acción debe ser informar de esto directamente al usuario. NO vuelvas a llamar a la herramienta. Pregúntale si quiere intentar otra fecha u hora.

            Paso 3: USUARIO ELIGE UN HORARIO
            - El usuario seleccionará uno de los horarios que le presentaste.
            
            Paso 4: RECOPILAR Y VALIDAR DATOS DEL CONTACTO (OBLIGATORIO ANTES DE AGENDAR)
            - **ANTES de confirmar la cita**, debes tener los datos de contacto requeridos.
            
            - **Paso 4.1: Determinar Campos Obligatorios para Agendar:**
              - Los campos base son `name`, `phone`, `email`.
              - Revisa las instrucciones del proyecto en busca de `CAMPOS_DE_CONTACTO: ['rut', 'ciudad', ...]`. Estos también son campos a considerar.
              - **Regla de Obligatoriedad:** Por defecto, `name`, `phone` y todos los `CAMPOS_DE_CONTACTO` son obligatorios.
              - **Regla de Excepciones:** Revisa las instrucciones en busca de `CAMPOS_OPCIONALES: ['email', 'rut']`. Estos campos NO son obligatorios para agendar.

            - **Paso 4.2: Validar y Solicitar:**
              - Llama a `save_contact_tool()` sin parámetros para ver qué datos ya tienes.
              - Compara los datos existentes con tu lista de campos obligatorios.
              - Si falta algún dato obligatorio, **DEBES SOLICITARLO AL USUARIO AHORA**.
              - **NO PROCEDAS AL PASO 5 HASTA TENER LOS DATOS REQUERIDOS.**

            Paso 5: CONFIRMAR Y AGENDAR
            - Una vez que tengas el horario elegido Y los datos de contacto validados, procede a agendar.
            - Llama a `agenda_tool(workflow_type="AGENDA_COMPLETA", ...)` con toda la información.
            
            ⚠️ REGLA DE ORO: Nunca llames a `agenda_tool` con `workflow_type="AGENDA_COMPLETA"` sin haber verificado y obtenido primero los datos de contacto del usuario en el paso 4.
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
