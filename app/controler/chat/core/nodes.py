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
from app.resources.constants import DEFAULT_PROMPT, DEFAULT_PROMPT_MEMORY, MODEL_CHATBOT
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
        MANEJO DE FECHAS Y HORAS:
        - Zona horaria: Chile (UTC-3)
        - Hora actual: {now_chile}
        - Fechas de referencia: {date_range_str}
        
        Reglas:
        - Usar current_datetime_tool para validar fechas
        - Verificar feriados con check_chile_holiday_tool
        - Formato: DD-MM-YYYY HH:mm
        - Prohibido calcular fechas manualmente
        """
        
        prompt_general_skeleton += f"""
        MANEJO DE CONTACTOS:
        - DETECTAR AUTOMÁTICAMENTE cuando el usuario proporcione:
          * Nombre completo (ej: "pedrito morales")
          * Email (ej: "sabado@fa.cl")
          * Teléfono (ej: "+56424231552")
        - Usar save_contact_tool con los datos detectados
        - Ejemplo: si el usuario escribe "pedrito morales sabado@fa.cl +56424231552"
          → save_contact_tool(name="Pedrito Morales", email="sabado@fa.cl", phone_number="+56424231552")
        - Continuar con la conversación
        """
        
        
        prompt_general_skeleton += f"""
        FORMATO DE URLs:
        - Usar markdown: [texto](url)
        - Ejemplo: [Ver producto](https://ejemplo.com/producto)
        """
                
        logging.info(f"project: {project.enabled_tools}")
        
        if(project.enabled_tools):
            if "products_search" in project.enabled_tools:
                prompt_general_skeleton += f"""
                BÚSQUEDA DE PRODUCTOS:
                - Usa search_products_unified para buscar productos
                - Parámetros: query (texto de búsqueda), category (opcional), limit=15
                - Muestra: título, precio (CLP), descripción, stock e imágenes
                - Formatea URLs con markdown: [texto](url)
                - Si no hay resultados, sugiere términos alternativos
                """
            if "retriever" in project.enabled_tools:
                prompt_general_skeleton += f"""
                RETRIEVER:
                - Usa document_retriever para buscar información específica
                - Parámetros: query (texto de búsqueda)
                - Devuelve: documentos relevantes con título, contenido y relevancia
                - Usar cuando: necesites información precisa sobre el proyecto
                """
            if "calendar" in project.enabled_tools:
                prompt_general_skeleton += f"""
                CALENDAR:
                Herramienta: google_calendar_tool
                
                Funcionalidades disponibles:
                1. Listar eventos:
                   - list_events|days=7 (lista eventos de los próximos 7 días)
                
                2. Buscar eventos:
                   - search_events|title=Reunión|date=2024-03-20
                
                3. Crear evento:
                   - create_event|title=Reunión|start=2024-03-20T15:00:00|end=2024-03-20T16:00:00|description=Detalles|attendees=email1@ejemplo.com,email2@ejemplo.com
                   - Opcional: force_create=true para crear a pesar de conflictos
                
                4. Verificar disponibilidad:
                   - check_availability|start=2024-03-20T15:00:00|end=2024-03-20T16:00:00
                
                5. Obtener detalles:
                   - get_event|event_id=abc123
                
                6. Actualizar evento:
                   - update_event|event_id=abc123|title=Nuevo título|description=Nueva descripción
                
                7. Eliminar evento:
                   - delete_event|event_id=abc123
                
                REGLAS IMPORTANTES PARA AGENDAMIENTO:
                - SIEMPRE verificar disponibilidad antes de crear eventos
                - NUNCA agendar si la hora ya está ocupada
                - SIEMPRE verificar si es feriado antes de agendar
                - Usar check_availability primero para confirmar que el horario está libre
                - Usar check_chile_holiday_tool para verificar si la fecha es feriado
                - NO agendar eventos en feriados chilenos
                - Si hay conflictos, mostrar los eventos existentes y sugerir horarios alternativos
                - Si es feriado, informar al usuario y sugerir otra fecha
                - Solo usar force_create=true si el usuario explícitamente lo solicita
                - El sistema verifica automáticamente conflictos al crear eventos
                
                FLUJO DE VALIDACIÓN PARA AGENDAR:
                1. Verificar si la fecha es feriado: check_chile_holiday_tool
                2. Si NO es feriado, verificar disponibilidad: check_availability
                3. Si está disponible, proceder con create_event
                4. Si hay conflictos o es feriado, sugerir alternativas
                
                Notas importantes:
                - Todas las fechas se manejan en zona horaria de Chile (UTC-3)
                - Se verifica automáticamente conflictos de horario
                - Formato de fecha: YYYY-MM-DDThh:mm:ss
                - Para eventos con invitados, separar emails por coma
                - NUNCA digas "el horario está disponible" sin ejecutar check_availability primero
                - NUNCA agendes en feriados sin verificar primero con check_chile_holiday_tool
                """
            if "tienda" in project.enabled_tools:
                prompt_general_skeleton += f"""
                TIENDA:
                - Herramientas disponibles:
                  * buscar_productos_tienda: busca productos por nombre, talla, color
                  * consultar_info_tienda: información sobre contacto, devoluciones, envíos
                  * gestionar_carrito: ver, agregar, eliminar productos, aplicar cupones
                - Usar cuando: necesites buscar productos o gestionar compras
                """
            if "openai_vector" in project.enabled_tools:
                prompt_general_skeleton += f"""
                OPENAI VECTOR:
                - Usa openai_vector_search para buscar información en documentos
                - Parámetros: query (texto de búsqueda)
                - Devuelve: 
                  * Contenido relevante de los documentos
                  * Nombre del archivo fuente
                  * Puntuación de relevancia
                  * Citas y referencias
                - Usar cuando: necesites información específica de documentos subidos
                - Formato de respuesta:
                  * Título con la consulta
                  * Resultados ordenados por relevancia
                  * Fuentes citadas cuando aplique
                """
            if "api" in project.enabled_tools:
                prompt_general_skeleton += f"""
                API:
                Herramienta: api_tool
                
                Características:
                - Integración con APIs externas configuradas en el proyecto
                - Funciones específicas generadas para cada API
                - Manejo automático de errores y timeouts
                
                Uso:
                - Consultar la API específica según el contexto
                - Proporcionar parámetros en el formato requerido
                - Procesar la respuesta según el formato de la API
                
                Consideraciones:
                - Verificar autenticación y headers requeridos
                - Respetar límites de rate y timeouts
                - Manejar errores según el tipo de API
                """
            if "email" in project.enabled_tools:
                prompt_general_skeleton += f"""
                EMAIL (send_email):
                API: Resend | Params: from_email, to, subject, html/text, cc, bcc, reply_to
                Default from: "noreply@ublix.app" | Multi emails: "email1@domain.com, email2@domain.com"
                Use when: user wants to send email, mentions "enviar email", "mandar correo"
                Examples: send_email(to="user@domain.com", subject="Test", html="<h1>Hola</h1>")
                """
            if "image_processor" in project.enabled_tools:
                prompt_general_skeleton += f"""
                PROCESAMIENTO DE IMÁGENES:
                Herramienta: image_processor
                - Parámetro: image_url (URL de la imagen a procesar)
                - Ejecutar automáticamente cuando el mensaje contenga una imagen
                - Devuelve el texto extraído como string plano
                - NUNCA digas que recibiste una imagen o una url de una imagen
                """

        
        PROMPT_GENERAL = prompt_general_skeleton
        
        #logging.info(f"PROMPT_GENERAL: {PROMPT_GENERAL}")
        
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