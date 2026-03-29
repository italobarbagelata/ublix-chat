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
        """Reglas generales del asistente - OPTIMIZADO para reducir tokens"""
        return """
ZONA HORARIA: America/Santiago (Chile)
FORMATO FECHAS: DD de mes de YYYY
"""
    
    @staticmethod
    def _get_tool_sections(enabled_tools: List[str]) -> str:
        """Obtiene secciones específicas de herramientas - OPTIMIZADO"""
        sections = []

        # HERRAMIENTAS SIEMPRE DISPONIBLES - SIMPLIFICADO
        sections.append("""
HERRAMIENTAS DISPONIBLES:

save_contact_tool: SOLO usar cuando el usuario PROPORCIONA datos personales.
- "me llamo Juan" → save_contact_tool(name="Juan")
- "mi email es x@gmail.com" → save_contact_tool(email="x@gmail.com")
- "hola" → NO usar (es saludo, no datos)
- NUNCA llamar sin datos reales del usuario

current_datetime_tool: SOLO para preguntas explícitas de fecha/hora.
- "¿qué día es?" → usar
- "¿qué productos tienen?" → NO usar
""")

        # HERRAMIENTA UNIFIED SEARCH - SIMPLIFICADO
        sections.append("""
unified_search_tool: Para buscar productos, servicios, FAQs.
- "¿qué productos tienen?" → unified_search_tool(query="productos")
- "hola" → NO usar (es saludo)
- Si ya buscaste, NO repetir
""")

        # HERRAMIENTAS CONDICIONALES - SIMPLIFICADO
        if "email" in enabled_tools:
            sections.append("\nsend_email: Enviar correos (to, subject, html/text)")

        if "api" in enabled_tools:
            sections.append("\napi_tool: APIs externas del proyecto")

        if "agenda_tool" in enabled_tools:
            sections.append("""
agenda_tool: Gestión de citas
- BUSQUEDA_HORARIOS: Buscar disponibilidad (specific_date opcional)
- AGENDA_COMPLETA: Confirmar cita (requiere start_datetime, attendee_email, attendee_name, title)
- CANCELACION_WORKFLOW: Cancelar cita (requiere event_id)
""")

        if "image_processor" in enabled_tools:
            sections.append("""
image_processor: Cuando detectes ![Imagen](URL), extraer URL y procesar inmediatamente.
""")

        if "holidays" in enabled_tools:
            sections.append("\ncheck_chile_holiday_tool/next_chile_holidays_tool: Verificar feriados Chile")

        if "week_info" in enabled_tools:
            sections.append("\nweek_info_tool: Info de semanas del año")
        
        return "".join(sections)