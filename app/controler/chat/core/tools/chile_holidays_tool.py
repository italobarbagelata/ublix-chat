from typing import Dict
import dateparser
from datetime import datetime
import holidays
import logging
from langchain.tools import tool

logger = logging.getLogger(__name__)

# Feriados de Chile (expandimos el rango para cubrir más años)
feriados_chile = holidays.Chile(years=range(2020, 2035))

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
                "PREFER_DAY_OF_MONTH": "first",  # Para casos ambiguos, preferir día del mes
                "RELATIVE_BASE": datetime.now()  # Base para fechas relativas
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
        
        # Limpiar la consulta de palabras innecesarias
        clean_query = query.lower()
        for phrase in ["es feriado", "¿es feriado", "es un feriado", "feriado", "¿", "?"]:
            clean_query = clean_query.replace(phrase, "").strip()
        
        if not clean_query:
            return "Por favor especifica una fecha para verificar si es feriado."
        
        fecha = normalize_date(clean_query)
        
        if not fecha:
            return f"No pude entender la fecha '{query}'. Por favor intenta con formatos como '18 de septiembre', 'mañana', '25/12/2024', etc."

        fecha_sola = fecha.date()
        motivo = feriados_chile.get(fecha_sola)
        
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
        
        if motivo:
            return f"✅ Sí, el {fecha_formateada} es feriado en Chile: **{motivo}**."
        else:
            # Verificar si es fin de semana
            if fecha_sola.weekday() >= 5:  # 5=sábado, 6=domingo
                return f"❌ El {fecha_formateada} no es feriado en Chile, pero es {dias_semana[fecha_sola.weekday()]} (fin de semana)."
            else:
                return f"❌ El {fecha_formateada} no es feriado en Chile. Es un día hábil normal."
        
    except Exception as e:
        logger.error(f"Error en check_chile_holiday_tool: {str(e)}")
        return f"Ocurrió un error al verificar la fecha: {str(e)}"

# Función adicional para obtener próximos feriados
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
        
        # Buscar feriados futuros
        for fecha, motivo in sorted(feriados_chile.items()):
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