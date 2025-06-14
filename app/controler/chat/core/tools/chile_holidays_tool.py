from typing import Dict
import dateparser
from datetime import datetime
import logging
from langchain.tools import tool

logger = logging.getLogger(__name__)

# Diccionario con los feriados de Chile 2025
FERIADOS_2025 = {
    "2025-01-01": "Año Nuevo (Irrenunciable)",
    "2025-04-18": "Viernes Santo",
    "2025-04-19": "Sábado Santo",
    "2025-05-01": "Día Nacional del Trabajo (Irrenunciable)",
    "2025-05-21": "Día de las Glorias Navales",
    "2025-06-20": "Día Nacional de los Pueblos Indígenas",
    "2025-06-29": "San Pedro y San Pablo",
    "2025-06-29": "Elecciones Primarias Presidenciales y Parlamentarias (Irrenunciable)",
    "2025-07-16": "Día de la Virgen del Carmen",
    "2025-08-15": "Asunción de la Virgen",
    "2025-09-18": "Independencia Nacional (Irrenunciable)",
    "2025-09-19": "Día de las Glorias del Ejército (Irrenunciable)",
    "2025-10-12": "Encuentro de Dos Mundos",
    "2025-10-31": "Día de las Iglesias Evangélicas y Protestantes",
    "2025-11-01": "Día de Todos los Santos",
    "2025-11-16": "Elecciones Presidenciales y Parlamentarias (Irrenunciable)",
    "2025-12-08": "Inmaculada Concepción",
    "2025-12-14": "Elecciones Presidenciales (Segunda Vuelta) (Irrenunciable)",
    "2025-12-25": "Navidad (Irrenunciable)"
}

# Feriados específicos por región
FERIADOS_ESPECIFICOS = {
    "2025-06-07": "Asalto y Toma del Morro de Arica (Región de Arica y Parinacota)",
    "2025-08-20": "Nacimiento del Prócer de la Independencia (Comunas de Chillán y Chillán Viejo)",
    "2025-12-31": "Feriado Bancario (Trabajadores de Instituciones Bancarias)"
}

def normalize_date(text: str) -> datetime | None:
    """
    Normaliza una fecha en texto a objeto datetime usando configuración para Chile.
    
    Args:
        text: Texto que contiene una fecha en español
        
    Returns:
        datetime object o None si no se puede parsear
    """
    try:
        return dateparser.parse(
            text,
            languages=["es"],
            settings={
                "TIMEZONE": "America/Santiago",
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DAY_OF_MONTH": "first",
                "RELATIVE_BASE": datetime.now()
            }
        )
    except Exception as e:
        logger.error(f"Error parseando fecha '{text}': {str(e)}")
        return None

@tool(parse_docstring=False)
def check_chile_holiday_tool(query: str) -> str:
    """Verifica si una fecha específica es feriado en Chile.
    
    Esta herramienta puede interpretar fechas en lenguaje natural en español,
    como "mañana", "18 de septiembre", "25 de diciembre", etc.
    
    Args:
        query: Texto que contiene la fecha a verificar (ej: "¿es feriado mañana?", "18 de septiembre")
        
    Returns:
        Información sobre si la fecha es feriado o no en Chile
    """
    try:
        logger.info(f"Verificando feriado para: '{query}'")
        
        # Limpiar la consulta
        clean_query = query.lower()
        for phrase in ["es feriado", "¿es feriado", "es un feriado", "feriado", "¿", "?"]:
            clean_query = clean_query.replace(phrase, "").strip()
        
        if not clean_query:
            return "Por favor especifica una fecha para verificar si es feriado."
        
        fecha = normalize_date(clean_query)
        
        if not fecha:
            return f"No pude entender la fecha '{query}'. Por favor intenta con formatos como '18 de septiembre', 'mañana', '25/12/2025', etc."

        fecha_str = fecha.strftime("%Y-%m-%d")
        fecha_sola = fecha.date()
        
        # Formatear la fecha en español
        meses = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
            7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        
        dias_semana = {
            0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 
            4: "viernes", 5: "sábado", 6: "domingo"
        }
        
        fecha_formateada = f"{dias_semana[fecha_sola.weekday()]} {fecha_sola.day} de {meses[fecha_sola.month]} de {fecha_sola.year}"
        
        # Verificar si es feriado general
        if fecha_str in FERIADOS_2025:
            return f"✅ Sí, el {fecha_formateada} es feriado en Chile: **{FERIADOS_2025[fecha_str]}**."
        
        # Verificar si es feriado específico
        if fecha_str in FERIADOS_ESPECIFICOS:
            return f"✅ Sí, el {fecha_formateada} es feriado específico en Chile: **{FERIADOS_ESPECIFICOS[fecha_str]}**."
        
        # Verificar si es fin de semana
        if fecha_sola.weekday() >= 5:  # 5=sábado, 6=domingo
            return f"❌ El {fecha_formateada} no es feriado en Chile, pero es {dias_semana[fecha_sola.weekday()]} (fin de semana)."
        
        return f"❌ El {fecha_formateada} no es feriado en Chile. Es un día hábil normal."
        
    except Exception as e:
        logger.error(f"Error en check_chile_holiday_tool: {str(e)}")
        return f"Ocurrió un error al verificar la fecha: {str(e)}"

@tool(parse_docstring=False)  
def next_chile_holidays_tool(query: str = "") -> str:
    """Muestra los próximos feriados de Chile.
    
    Args:
        query: Opcional - número de feriados a mostrar (ej: "5") o vacío para mostrar los próximos 3
        
    Returns:
        Lista de los próximos feriados en Chile
    """
    try:
        # Determinar cuántos feriados mostrar
        num_holidays = 3  # Por defecto
        if query.strip().isdigit():
            num_holidays = min(int(query.strip()), 10)  # Máximo 10
        
        today = datetime.now().date()
        proximos_feriados = []
        
        # Combinar feriados generales y específicos
        todos_feriados = {**FERIADOS_2025, **FERIADOS_ESPECIFICOS}
        
        # Buscar feriados futuros
        for fecha_str, motivo in sorted(todos_feriados.items()):
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            if fecha > today:
                proximos_feriados.append((fecha, motivo))
                if len(proximos_feriados) >= num_holidays:
                    break
        
        if not proximos_feriados:
            return "No se encontraron próximos feriados en el calendario de Chile."
        
        # Formatear respuesta
        meses = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
            7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        
        dias_semana = {
            0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 
            4: "viernes", 5: "sábado", 6: "domingo"
        }
        
        resultado = f"🇨🇱 **Próximos {len(proximos_feriados)} feriados en Chile:**\n\n"
        
        for fecha, motivo in proximos_feriados:
            dia_semana = dias_semana[fecha.weekday()]
            fecha_formateada = f"{dia_semana} {fecha.day} de {meses[fecha.month]} de {fecha.year}"
            
            # Calcular días restantes
            dias_restantes = (fecha - today).days
            if dias_restantes == 0:
                tiempo_restante = "hoy"
            elif dias_restantes == 1:
                tiempo_restante = "mañana"
            else:
                tiempo_restante = f"en {dias_restantes} días"
            
            resultado += f"• **{motivo}**: {fecha_formateada} ({tiempo_restante})\n"
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error en next_chile_holidays_tool: {str(e)}")
        return f"Ocurrió un error al obtener los próximos feriados: {str(e)}" 