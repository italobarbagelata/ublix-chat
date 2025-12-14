"""
Templates modulares para construcción de prompts
"""
from typing import List, Dict, Any

class PromptTemplateBuilder:
    """Construye prompts modulares basados en herramientas habilitadas"""
    
    @staticmethod
    def build_system_prompt(
        project: Any,
        summary: str,
        utc_now: str,
        date_range_str: str,
        now_chile: str
    ) -> str:
        """
        Construye el prompt del sistema principal (SIMPLIFICADO)

        Args:
            project: Objeto del proyecto con configuración
            summary: Resumen de conversación anterior
            utc_now: Tiempo UTC actual en ISO format
            date_range_str: String con rango de fechas
            now_chile: Tiempo actual en Chile

        Returns:
            str: Prompt del sistema completo
        """
        from app.resources.constants import DEFAULT_PROMPT

        # Usar el prompt base por defecto
        base_prompt = DEFAULT_PROMPT

        # Reemplazar placeholders básicos
        base_prompt = base_prompt.replace("{name}", project.name if project else "Asistente")
        base_prompt = base_prompt.replace("{utc_now}", utc_now)
        base_prompt = base_prompt.replace("{date_range_str}", date_range_str)
        base_prompt = base_prompt.replace("{now_chile}", now_chile)

        # Agregar instrucciones específicas del proyecto
        if project and project.instructions and project.instructions.strip():
            base_prompt += f"""

INSTRUCCIONES ESPECÍFICAS DEL PROYECTO:

{project.instructions}
"""

        # Agregar resumen si existe
        if summary and summary.strip():
            base_prompt += f"""

RESUMEN DE CONVERSACIÓN ANTERIOR:

{summary}

IMPORTANTE: Usa esta información para NO repetir preguntas que ya fueron respondidas.
"""

        # Agregar secciones específicas por herramienta
        if project and hasattr(project, 'enabled_tools'):
            base_prompt += PromptTemplateBuilder._get_tool_sections(project.enabled_tools)

        # Agregar reglas centrales
        base_prompt += PromptTemplateBuilder._get_core_rules()

        return base_prompt
    
    @staticmethod
    def _get_core_rules() -> str:
        """Reglas generales del asistente (NO específicas de herramientas)"""
        return """
        
        PRIORIDADES DEL ASISTENTE:
        1. RESPUESTAS: Máximo 250 caracteres, directo y conciso
        2. HERRAMIENTAS: Solo usar cuando sea ABSOLUTAMENTE necesario
        3. NUNCA llamar la misma herramienta más de 1 vez por conversación
        4. Si ya tienes la información, NO vuelvas a buscarla
        5. Para preguntas de PRODUCTOS → unified_search_tool (NO datetime)
        6. Para preguntas de FECHA/HORA → current_datetime_tool (máximo 1 vez)
        7. IDIOMA: Responder en el mismo idioma del usuario
        
        CONTEXTO TEMPORAL Y GEOGRÁFICO:
        - Zona horaria: America/Santiago (Chile)
        - Fechas en formato: DD de mes de YYYY
        
        FORMATO DE RESPUESTAS:
        - URLs: [texto](url)
        - Ejemplo: [Ver producto](https://www.ublix.app/producto/123)
        - Horarios: TEXTO PLANO sin markdown (sin asteriscos/negritas)
        - Listas numeradas simples cuando sea necesario
        """
    
    @staticmethod
    def _get_tool_sections(enabled_tools: List[str]) -> str:
        """Obtiene secciones específicas de herramientas habilitadas"""
        sections = []
        
        # HERRAMIENTAS SIEMPRE DISPONIBLES
        sections.append("""
        
        CURRENT_DATETIME_TOOL (current_datetime_tool):
        - SOLO usar cuando el usuario EXPLÍCITAMENTE pregunte por fecha/hora ("qué día es", "qué hora es")
        - NUNCA llamar para preguntas sobre productos, servicios o información general
        - MÁXIMO 1 llamada por conversación (si ya la usaste, NO vuelvas a llamarla)
        - Si el usuario pregunta sobre productos → usa unified_search_tool, NO current_datetime_tool
        - Ejemplo CORRECTO: "¿qué día es hoy?" → current_datetime_tool
        - Ejemplo INCORRECTO: "¿qué parlantes venden?" → NO uses current_datetime_tool
        
        SAVE_CONTACT_TOOL (save_contact_tool):
        HERRAMIENTA CRÍTICA - SIEMPRE disponible para gestión de contactos.

        ⚠️ USO OBLIGATORIO AUTOMÁTICO:
        DEBES ejecutar save_contact_tool INMEDIATAMENTE cuando el usuario mencione:
        - Su nombre (ej: "me llamo Juan", "soy María", "Juan Pérez")
          → save_contact_tool(name="Juan")
        - Su email (ej: "juan@gmail.com", "mi email es...")
          → save_contact_tool(email="juan@gmail.com")
        - Su teléfono (ej: "912345678", "mi número es...")
          → save_contact_tool(phone_number="912345678")
        - Información personal configurada (edad, ciudad, presupuesto, etc.)
          → save_contact_tool(additional_fields='{"edad": 30, "ciudad": "Santiago"}')

        REGLAS DE EJECUCIÓN:
        1. EJECUTAR INMEDIATAMENTE sin preguntar permiso
        2. EJECUTAR SILENCIOSAMENTE (sin mensaje "guardando...")
        3. NO mencionar que guardaste la info, responder naturalmente
        4. Si el usuario da múltiples datos, guardar todos en una sola llamada

        EJEMPLOS:
        Usuario: "me llamo juan"
        → Ejecutar: save_contact_tool(name="juan")
        → Responder: "Mucho gusto, Juan. ¿En qué puedo ayudarte?"

        Usuario: "soy María González, mi email es maria@gmail.com"
        → Ejecutar: save_contact_tool(name="María González", email="maria@gmail.com")
        → Responder: "Hola María, ¿cómo puedo ayudarte hoy?"

        ESTADOS DEL LEAD DISPONIBLES:
        - "nuevo_chat": Al iniciar conversación (Paso 1)
        - "eligiendo_servicio": Cuando muestra interés (Paso 2)  
        - "eligiendo_horario": Al mostrar horarios disponibles (Paso 3)
        - "esperando_confirmacion": Cuando el usuario elige un horario específico (Paso 4)
        - "recopilando_datos": Al solicitar información personal después de elegir horario (Paso 4-5)
        - "reservado": Al confirmar cita final con todos los datos (Paso 6)
        
        - Las instrucciones del proyecto definen qué datos solicitar y cuándo usar cada estado
        """)

        # HERRAMIENTA UNIFIED SEARCH (SIEMPRE ACTIVA)
        sections.append("""

        USO INTELIGENTE DE BÚSQUEDA (unified_search_tool):
        Esta herramienta SIEMPRE está disponible para buscar en FAQs, documentos y productos.

        Usa unified_search_tool CUANDO:
        - El usuario pregunte sobre productos, servicios, precios, horarios, procedimientos
        - Necesites información de catálogo o inventario
        - Consultas sobre características técnicas o detalles específicos
        - El usuario pregunte "qué", "cuál", "cuánto", "dónde" sobre tus servicios/productos

        NO uses unified_search_tool para:
        - Saludos simples (hola, buenos días, etc.)
        - Confirmaciones (sí, no, ok, gracias)
        - Preguntas sobre envío de imágenes o documentos
        - Si ya buscaste lo mismo en el último mensaje

        IMPORTANTE: Usa la consulta del usuario DIRECTAMENTE, no reformules.
        Ejemplo: Si pregunta "qué parlantes venden?" → busca "parlantes"

        FORMATO DE RESPUESTA PARA PRODUCTOS:
        Cuando unified_search_tool devuelva productos, responde en este formato EXACTO:
        "Aquí están los productos que encontré:
        [
          {
            "name": "Nombre del producto",
            "description": "Descripción corta",
            "price": 50000,
            "currency": "CLP",
            "image": "URL de la imagen",
            "url": "URL del producto",
            "sku": "SKU123",
            "stock": 10
          }
        ]"
        """)

        # HERRAMIENTAS CONDICIONALES
        
        if "email" in enabled_tools:
            sections.append("""
                EMAIL (send_email):
                Herramienta para enviar correos.
                - Parámetros: from_email, to, subject, html/text, cc, bcc, reply_to.
                - El `from_email` por defecto es "noreply@ublix.app".
                - El parámetro `to` puede recibir múltiples correos separados por coma.
                """)
        
        if "api" in enabled_tools:
            sections.append("""
                API TOOLS DINÁMICAS (api_tool):
                Herramientas API personalizadas configuradas específicamente para este proyecto.
                Las funciones disponibles se generan dinámicamente basadas en las configuraciones de API almacenadas.
                Cada API tiene su propia configuración de endpoints, parámetros y métodos HTTP.
                Usa estas herramientas cuando necesites interactuar con APIs externas específicas del proyecto.
                """)
        
        if "agenda_tool" in enabled_tools:
            sections.append("""
            
            AGENDA_TOOL (agenda_tool):
            Herramienta para gestión de citas con workflows específicos:
            
            WORKFLOWS DISPONIBLES (workflow_type):
            1. BUSQUEDA_HORARIOS: Buscar disponibilidad
               - Parámetros: specific_date="YYYY-MM-DD" o sin fecha para próximos días
               - Mostrar MÁXIMO 3 opciones, formato texto plano
               - Mencionar si hay más opciones disponibles
            
            2. AGENDA_COMPLETA: Confirmar y agendar cita DEFINITIVA
               - Requiere: start_datetime, attendee_email, attendee_name, title
               - EJECUTAR UNA SOLA VEZ cuando el usuario confirme UN horario específico
               - NUNCA agendar sin confirmación explícita del usuario
            
            3. CANCELACION_WORKFLOW: Cancelar cita existente
               - Requiere: event_id
            
            REGLAS CRÍTICAS:
            - EJECUTAR INMEDIATAMENTE sin avisos tipo "voy a buscar"
            - Usar current_datetime_tool ANTES si mencionan días de la semana
            - PROHIBIDO decir "cita agendada" sin ejecutar AGENDA_COMPLETA primero
            - Las instrucciones del proyecto definen el flujo específico
            """)
        
        if "image_processor" in enabled_tools:
            sections.append("""
            
            IMAGE_PROCESSOR (image_processor):
            Procesa imágenes para extraer texto visible.
            
            DETECCIÓN AUTOMÁTICA OBLIGATORIA:
            - Patrón a detectar: ![Imagen](URL)
            - Extraer URL y llamar INMEDIATAMENTE: image_processor(image_url="URL")
            - PROHIBIDO responder sin procesar primero
            - SIEMPRE mencionar el texto extraído en tu respuesta
            - Seguir instrucciones del proyecto con el texto obtenido
            """)
        
        if "holidays" in enabled_tools:
            sections.append("""
            
            HOLIDAYS TOOLS (check_chile_holiday_tool, next_chile_holidays_tool):
            - check_chile_holiday_tool: Verifica si una fecha es feriado
            - next_chile_holidays_tool: Lista próximos feriados de Chile
            - USAR ANTES de agendar para evitar días feriados
            """)
        
        if "week_info" in enabled_tools:
            sections.append("""
            
            WEEK_INFO_TOOL (week_info_tool):
            - Información sobre semanas del año
            - "¿En qué semana estamos?", "días de esta semana"
            - Útil para contexto temporal en conversaciones
            """)
        
        return "".join(sections)