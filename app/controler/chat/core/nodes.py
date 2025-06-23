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
        

        
        # AGREGAR RESUMEN DE CONVERSACIÓN ANTERIOR
        if summary and summary.strip():
            prompt_general_skeleton += f"""
            
            📋 RESUMEN DE CONVERSACIÓN ANTERIOR:
            {summary}
            
            ⚠️ IMPORTANTE: Usa esta información para NO repetir preguntas que ya fueron respondidas.
            """
        
        # INSTRUCCIÓN CRÍTICA: SIEMPRE usar unified_search antes de responder
        if "unified_search" in project.enabled_tools:
            prompt_general_skeleton += f"""
            
            ⚠️ INSTRUCCIÓN CRÍTICA - OBLIGATORIA:
            - ANTES de responder CUALQUIER consulta del usuario, SIEMPRE ejecuta unified_search_tool
            - NO respondas NUNCA sin haber buscado primero con unified_search_tool
            - Usa unified_search_tool con la consulta exacta del usuario
            - Esta herramienta busca automáticamente en FAQs, documentos y productos
            - Solo después de obtener resultados, procede a responder
            - Si no hay resultados relevantes, entonces puedes responder basándote en tu conocimiento
            - Esta regla es ABSOLUTA y no tiene excepciones
            - unified_search_tool es la HERRAMIENTA PRINCIPAL de búsqueda híbrida
            
            """
        
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
        MEMORIA Y CONTACTOS - REGLAS CRÍTICAS:
        
        ⚠️ ANTES DE PREGUNTAR CUALQUIER INFORMACIÓN:
        1. REVISA el "RESUMEN DE CONVERSACIÓN ANTERIOR" (si existe) para ver qué información ya tienes
        2. REVISA los mensajes anteriores de esta conversación
        3. Si el usuario YA proporcionó información (nombre, email, teléfono), NO la preguntes otra vez
        4. USA la información que ya tienes del resumen y mensajes anteriores
        
        DETECTAR Y GUARDAR AUTOMÁTICAMENTE:
        - Cuando el usuario dé nombre, email o teléfono → usar save_contact_tool inmediatamente
        - Ejemplo: Usuario dice "sebastian" → save_contact_tool(name="Sebastian")
        - Ejemplo: Usuario dice "hokidoki8@gmail.com" → save_contact_tool(email="hokidoki8@gmail.com")
        - Ejemplo: Usuario dice "998766626" → save_contact_tool(phone_number="998766626")
        - NUNCA digas que guardaste el contacto, solo ejecuta la herramienta
        
        CORRECTO: Usar la información del resumen y continuar la conversación desde donde se quedó
        """
        
        
        prompt_general_skeleton += f"""
        FORMATO DE URLs:
        - Usar markdown: [texto](url)
        - Ejemplo: [Ver producto](https://ejemplo.com/producto)
        """
                
        logging.info(f"project: {project.enabled_tools}")
        
        if(project.enabled_tools):
            if "unified_search" in project.enabled_tools:
                prompt_general_skeleton += f"""
                BÚSQUEDA UNIFICADA (unified_search_tool) - HERRAMIENTA PRINCIPAL:
                - Herramienta OBLIGATORIA para buscar en TODOS los tipos de contenido
                - SIEMPRE ejecutar ANTES de responder cualquier consulta del usuario
                - Busca automáticamente en: documentos, FAQs y productos
                - Combina búsqueda semántica y por texto para mejores resultados
                - Prioriza FAQs para respuestas rápidas, luego documentos, luego productos
                - Parámetros: query (obligatorio), content_types (opcional), limit (opcional, default 15), category (opcional)
                - Ejemplo: unified_search_tool(query="política de devoluciones", limit=10)
                - NO usar las herramientas separadas (document_retriever, faq_retriever, search_products_unified)
                - Esta herramienta es MÁS EFICIENTE y RÁPIDA que usar 3 herramientas separadas
                - Es la HERRAMIENTA PRINCIPAL de búsqueda híbrida del sistema
                """
            elif "products_search" in project.enabled_tools:
                prompt_general_skeleton += f"""
                BÚSQUEDA DE PRODUCTOS:
                - Usa search_products_unified para buscar productos
                - Parámetros: query (texto de búsqueda), category (opcional), limit=15
                - Muestra: título, precio (CLP), descripción, stock e imágenes
                - Formatea URLs con markdown: [texto](url)
                - Si no hay resultados, sugiere términos alternativos
                """
            elif "retriever" in project.enabled_tools:
                prompt_general_skeleton += f"""
                RETRIEVER:
                - Usa document_retriever para buscar información específica
                - Parámetros: query (texto de búsqueda)
                - Devuelve: documentos relevantes con título, contenido y relevancia
                - SIEMPRE buscar en documentos cuando el usuario haga consultas sobre el proyecto
                - Usar para: información técnica, procedimientos, políticas, contenido detallado
                """
            elif "faq_retriever" in project.enabled_tools:
                prompt_general_skeleton += f"""
                FAQ RETRIEVER - OBLIGATORIO:
                - SIEMPRE ejecuta faq_retriever ANTES de responder cualquier consulta
                - Usa faq_retriever con la consulta exacta del usuario
                - Parámetros: query (texto de búsqueda), limit (opcional, por defecto 8)
                - Devuelve: FAQs con pregunta, respuesta, título y metadatos
                - NO respondas sin haber buscado primero en FAQs
                - Si no hay FAQs relevantes, entonces puedes responder basándote en tu conocimiento
                - Esta herramienta es PRIORITARIA sobre todas las demás
                """
            if "retriever" in project.enabled_tools and "faq_retriever" in project.enabled_tools and "unified_search" not in project.enabled_tools:
                prompt_general_skeleton += f"""
                ESTRATEGIA DE BÚSQUEDA COMBINADA:
                - SIEMPRE usar AMBAS herramientas (document_retriever Y faq_retriever) cuando el usuario haga consultas
                - Buscar primero en FAQs para respuestas rápidas y directas
                - Buscar en documentos para información más detallada y técnica
                - Combinar los resultados para dar respuestas completas
                - Priorizar FAQs cuando la consulta sea una pregunta directa
                - Usar documentos para complementar con información adicional
                - NO esperar a que el usuario pida específicamente buscar en una herramienta
                - Ser proactivo: buscar automáticamente en ambas fuentes
                """
            if "calendar" in project.enabled_tools:
                prompt_general_skeleton += f"""
                CALENDAR:
                Herramienta: google_calendar_tool
                
                ⚠️ CONFIGURACIÓN ESPECÍFICA DEL PROYECTO:
                - DURACIÓN ESTÁNDAR: Todas las reuniones duran 60 minutos (1 hora)
                - SIEMPRE usar duration=1 en find_available_slots
                - Al crear eventos, calcular hora de fin sumando 60 minutos a la hora de inicio
                
                Funcionalidades disponibles:
                1. Listar eventos:
                   - list_events|days=7 (lista eventos de los próximos 7 días)
                
                2. Buscar eventos:
                   - search_events|title=Reunión|date=2024-03-20
                
                3. Crear evento:
                   - create_event|title=Reunión|start=2024-03-20T15:00:00|end=2024-03-20T16:00:00|description=Detalles|attendees=email1@ejemplo.com,email2@ejemplo.com
                   - Opcional: force_create=true para crear a pesar de conflictos
                   - Opcional: meet=true para agregar Google Meet automáticamente
                   - IMPORTANTE: Cuando se incluyen attendees, Google Calendar envía automáticamente invitaciones por correo
                   - Los invitados reciben recordatorios por email 24 horas antes y popup 10 minutos antes
                   - GOOGLE MEET: Si meet=true, se genera un enlace de Google Meet automáticamente y se incluye en las invitaciones
                
                4. Verificar disponibilidad:
                   - check_availability|start=2024-03-20T15:00:00|end=2024-03-20T16:00:00
                
                8. Buscar horarios disponibles:
                   - find_available_slots|duration=1 (busca las próximas 3 fechas disponibles de 60 minutos)
                   - find_available_slots|duration=1.5|start_hour=10|end_hour=16 (personalizado)
                
                5. Obtener detalles:
                   - get_event|event_id=abc123
                
                6. Actualizar evento:
                   - update_event|event_id=abc123|title=Nuevo título|description=Nueva descripción
                
                7. Eliminar evento:
                   - delete_event|event_id=abc123
                
                REGLAS IMPORTANTES PARA AGENDAMIENTO:
                - SIEMPRE verificar disponibilidad antes de crear eventos
                - NUNCA agendar si la hora ya está ocupada
                - SIEMPRE verificar si es feriado antes de agendar con check_chile_holiday_tool
                - Usar check_availability primero para confirmar que el horario está libre
                - Usar check_chile_holiday_tool para verificar si la fecha es feriado
                - NO agendar eventos en feriados chilenos
                - Si hay conflictos, mostrar los eventos existentes y sugerir horarios alternativos
                - Si es feriado, informar al usuario y sugerir otra fecha
                - Solo usar force_create=true si el usuario explícitamente lo solicita
                - El sistema verifica automáticamente conflictos al crear eventos
                
                FLUJO PARA AGENDAR - REGLAS OBLIGATORIAS:
                
                1. PRIMERO: Cuando el usuario quiera agendar, usa google_calendar_tool con find_available_slots para mostrarle las próximas 3 fechas disponibles:
                   - Ejecuta: google_calendar_tool|find_available_slots|duration=1
                   - IMPORTANTE: SIEMPRE usar duration=1 (60 minutos) para este proyecto
                   - Esto le mostrará 3 opciones siempre enumeradas (1, 2, 3) con fechas y horarios libres de 60 minutos
                
                2. ESPERA que el usuario elija una opción (enumerada 1, 2 o 3) O proponga su propia fecha/hora O pregunte por un día específico.
                
                3. SOLO cuando el usuario responda con una elección específica:
                   a) Si eligió un número (enumerada 1, 2 o 3): Confirma directamente "¿Confirmas que agende para [fecha/hora de la opción elegida]?"
                   b) Si propuso su propia fecha/hora: Verifica feriado (check_chile_holiday_tool) y disponibilidad (check_availability)
                   c) Si pregunta por un día específico (ej: "para el jueves?", "y para el miércoles?", "¿qué tal el viernes?", "tienes para martes?"): 
                      Ejecuta google_calendar_tool|find_available_slots|day=[día]|duration=1
                      Ejemplos: 
                      - "para el jueves?" → google_calendar_tool|find_available_slots|day=jueves|duration=1
                      - "y para el miércoles?" → google_calendar_tool|find_available_slots|day=miércoles|duration=1
                   d) Si hay conflictos o es feriado, muestra las opciones disponibles otra vez
                   e) Si está libre, confirma: "¿Confirmas que agende para [fecha/hora]?"
                
                4. Solo cuando tengas CONFIRMACIÓN y TODOS LOS DATOS, usa create_event con attendees=email_del_usuario.
                   - IMPORTANTE: Los eventos deben durar exactamente 60 minutos
                   - Si el usuario elige una hora (ej: 15:00), el evento va de 15:00 a 16:00
                   - GOOGLE MEET: Agregar meet=true automáticamente para todas las reuniones (es la configuración estándar)
                   - Ejemplo: create_event|title=Reunión|start=2024-03-20T15:00:00|end=2024-03-20T16:00:00|attendees=usuario@email.com|meet=true
                
                ⚠️ CRÍTICO: NUNCA crees eventos sin tener el email del usuario. SIEMPRE incluye el email como attendee.
                ⚠️ CRÍTICO: SIEMPRE empieza mostrando las opciones disponibles con find_available_slots|duration=1. NO preguntes "¿qué día y hora?" sin antes mostrar las opciones.
                
                ⚠️ DETECCIÓN DE DÍAS ESPECÍFICOS:
                Si el usuario menciona un día de la semana específico (lunes, martes, miércoles, jueves, viernes, sábado, domingo), 
                INMEDIATAMENTE usa find_available_slots con el parámetro day. NO uses la búsqueda general.
                Ejemplos de frases que requieren búsqueda específica:
                - "para el jueves?" → day=jueves
                - "y el miércoles?" → day=miércoles  
                - "¿tienes para viernes?" → day=viernes
                - "qué tal martes?" → day=martes
                
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
                - Herramientas disponibles: funciones específicas generadas para cada API configurada
                - Uso: ejecutar automáticamente cuando el usuario solicite información o acciones que requieran APIs externas
                - Parámetros: seguir la documentación específica de cada función API
                - Respuesta: procesar y presentar los datos de forma clara y útil
                - Manejo de errores: informar al usuario si hay problemas de conexión o datos
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