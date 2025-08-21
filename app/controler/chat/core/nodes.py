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
            logging.debug(f"Resumen de conversación anterior cargado: {len(summary)} caracteres")
        
        prompt_general_skeleton = prompt_general_skeleton.replace("{name}", project_name)
        prompt_general_skeleton = prompt_general_skeleton.replace("{personality}", personality_prompt)
        prompt_general_skeleton = prompt_general_skeleton.replace("{instructions}", instructions)
        prompt_general_skeleton = prompt_general_skeleton.replace("{utc_now}", now.isoformat())
        prompt_general_skeleton = prompt_general_skeleton.replace("{date_range_str}", date_range_str)
        prompt_general_skeleton = prompt_general_skeleton.replace("{now_chile}", now_chile)
        
        # Agregar regla inteligente de unified_search si está disponible
        if "unified_search" in project.enabled_tools:
            prompt_general_skeleton += f"""
            
            🔍 USO INTELIGENTE DE BÚSQUEDA:
            Usa unified_search_tool SOLO cuando:
            - El usuario pregunte sobre información específica (servicios, precios, horarios, procedimientos)
            - Necesites datos del conocimiento base (FAQs, documentos, productos)
            - La consulta requiera información técnica o detalles del servicio
            
            NO uses unified_search_tool para:
            - Saludos simples (hola, buenos días, etc.)
            - Confirmaciones (sí, no, ok, gracias)
            - Preguntas sobre envío de imágenes o documentos
            - Continuación de conversaciones previas sin nueva información solicitada
            - Si ya buscaste lo mismo en los últimos 3 mensajes
            """
        
        prompt_general_skeleton += f"""
        
        🎯 PRIORIDADES DEL ASISTENTE (SEGUIR EN ESTE ORDEN):
        1. EVALUAR: ¿Requiere búsqueda? Si es pregunta técnica/servicio → unified_search_tool
        2. AGENDAMIENTO: agenda_tool para horarios, save_contact_tool para datos
        3. RESPUESTAS: Máximo 250 caracteres, directo y conciso
        4. HERRAMIENTAS: Solo las estrictamente necesarias
        
        CONTEXTO TEMPORAL Y GEOGRÁFICO:
        - Zona horaria: America/Santiago (Chile)

        
        FORMATO DE URLs:
        - Usar: [texto](url)
        - Ejemplo: [Ver producto](https://www.ublix.app/producto/123)

        🚨 GESTIÓN DE DATOS DE CONTACTO (save_contact_tool):
        - Usa esta herramienta para guardar o actualizar la información del usuario (nombre, email, teléfono, o campos personalizados definidos en las instrucciones).
        - Puedes llamarla sin parámetros para verificar los datos que ya tienes.
        - Las instrucciones del proyecto te indicarán qué datos solicitar y cuándo.
        
        
        📅 GESTIÓN DE HORARIOS DE CALENDARIO - REGLAS CRÍTICAS:
        - MÁXIMO 3 opciones por respuesta
        - Formato horarios: TEXTO PLANO sin markdown (sin asteriscos/negritas)
        - Ejemplo correcto: "1. Lunes 11 de agosto de 2025 a las 09:00"
        - PROHIBIDO: **09:00** o cualquier markdown
        - Si hay más horarios: mencionar "hay más opciones disponibles"
        
        🚨 EJECUCIÓN DE AGENDA_TOOL:
        - EJECUTA agenda_tool INMEDIATAMENTE sin avisos previos
        - PROHIBIDO decir "Voy a buscar horarios" o "Un momento por favor"
        - NO expliques que vas a buscar - EJECUTA DIRECTAMENTE la herramienta
        - Usa los resultados para mostrar los horarios con formato correcto
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
                Herramienta de búsqueda principal en la base de conocimiento del proyecto (FAQs, documentos, productos).
                Usar con la consulta exacta del usuario sin modificar para obtener los mejores resultados.
                """ 
        if "agenda_tool" in project.enabled_tools:
            prompt_general_skeleton += f"""
            AGENDA_TOOL (agenda_tool):
            Herramienta para agendar citas. Tiene dos modos de operación principales definidos por `workflow_type`:
            
            1. `BUSQUEDA_HORARIOS`: Busca horarios disponibles. 
               - Requiere: `start_datetime` (fecha para buscar) y `title` (consulta del usuario)
               - Úsalo cuando el usuario: consulta disponibilidad, pregunta por horarios, compara opciones
            
            2. `AGENDA_COMPLETA`: Confirma y agenda UNA SOLA cita final.
               - Requiere: `start_datetime` exacto elegido + información del contacto
               - IMPORTANTE: SOLO usar cuando el usuario confirmó UN horario específico
               - NUNCA llamar múltiples veces en una sola respuesta
               - Si el contacto tiene campos adicionales, debes pasarlos también
            
            REGLAS CRÍTICAS DE AGENDAMIENTO:
            - AGENDA_COMPLETA se ejecuta SOLO UNA VEZ por conversación
            - Si el usuario menciona múltiples horarios, pregúntale cuál prefiere
            - Si no estás seguro de cuál horario quiere, usa BUSQUEDA_HORARIOS
            - Confirma EXPLÍCITAMENTE antes de usar AGENDA_COMPLETA
            - NUNCA confirmes al usuario que la cita fue agendada sin ejecutar primero agenda_tool(AGENDA_COMPLETA)
            - OBLIGATORIO: Debes ejecutar agenda_tool antes de decir "Su hora ha sido agendada"
            
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
        
        #log prompt
        #logging.info(f"{unique_id} Prompt:\n{prompt_general_skeleton}")

        # Invocar modelo
        response = model_with_tools.invoke(messages)
        decorate_message(response, state["exec_init"], state["conversation_id"])
        
        # Log de herramientas ejecutadas si las hay
        has_tool_calls = hasattr(response, 'tool_calls') and response.tool_calls
        if has_tool_calls:
            for tc in response.tool_calls:
                tool_name = tc.get('name', 'unknown') if isinstance(tc, dict) else getattr(tc, 'name', 'unknown')
                conv_logger.log_herramienta_ejecutada(tool_name)

        return {"messages": [response]}

    return agent

def get_tools_summary(enabled_tools: list) -> str:
    """
    Genera un resumen dinámico de las herramientas habilitadas basado en enabled_tools
    """
    tools_descriptions = {
        "unified_search": "unified_search_tool: Búsqueda unificada en documentos, FAQs y productos",
        "retriever": "document_retriever: Búsqueda en documentos específicos del proyecto",
        "faq_retriever": "faq_retriever: Búsqueda en preguntas frecuentes",
        "products_search": "search_products_unified: Búsqueda de productos en el catálogo",
        "calendar": "google_calendar_tool: Gestión completa de calendario Google",
        "email": "send_email: Envío de emails profesionales",
        "contact": "save_contact_tool: Gestión de información de contacto",
        "tienda": "Herramientas de tienda: buscar_productos_tienda, consultar_info_tienda, gestionar_carrito",
        "openai_vector": "openai_vector_search: Búsqueda vectorial en documentos",
        "api": "API Tools: Herramientas dinámicas generadas según configuración del proyecto",
        "image_processor": "image_processor: Análisis y procesamiento de imágenes",
        "mongo_db": "mongo_db_tool: Operaciones en base de datos MongoDB",
        "agenda_tool": "agenda_tool: Gestión de horarios y agendamiento con Google Calendar",
        "agenda_smart_booking_tool": "agenda_smart_booking_tool: Gestión de horarios y agendamiento con Google Calendar"
    }
    
    # Herramientas que siempre están disponibles
    always_available = [
        "save_contact_tool: Gestión de contactos"
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
    unique_id = state.get("unique_id", "unknown")
    
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
