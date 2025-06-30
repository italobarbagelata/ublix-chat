"""
🗓️ UTILIDADES COMUNES PARA HERRAMIENTAS DE CALENDARIO

Centraliza código duplicado y funciones de formateo para evitar repetición
en calendar_tool.py y otras herramientas de calendario.
"""

import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# 🌎 Zona horaria de Chile
CHILE_TZ = pytz.timezone('America/Santiago')

# 📅 MAPEOS CENTRALIZADOS - Eliminan duplicación de código
DIAS_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

MESES_ES = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
           'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

DIAS_MAP = {
    'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2,
    'jueves': 3, 'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6
}

DIAS_SEMANA_EN_ES = {
    'Monday': 'lunes', 'Tuesday': 'martes', 'Wednesday': 'miércoles', 
    'Thursday': 'jueves', 'Friday': 'viernes', 'Saturday': 'sábado', 'Sunday': 'domingo'
}

MESES_EN_ES = {
    'January': 'enero', 'February': 'febrero', 'March': 'marzo', 'April': 'abril',
    'May': 'mayo', 'June': 'junio', 'July': 'julio', 'August': 'agosto',
    'September': 'septiembre', 'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
}

def normalize_to_chile_timezone(datetime_str: str) -> str:
    """
    Normaliza una fecha/hora a la zona horaria de Chile
    
    Args:
        datetime_str: String de fecha/hora en formato ISO
    
    Returns:
        String de fecha/hora normalizado a zona horaria de Chile
    """
    try:
        logger.info(f"Normalizing timezone for: {datetime_str}")
        
        # Si ya tiene zona horaria
        if datetime_str.endswith('Z'):
            # UTC -> Chile
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            dt_utc = pytz.UTC.localize(dt.replace(tzinfo=None))
            dt_chile = dt_utc.astimezone(CHILE_TZ)
        elif '+' in datetime_str[-6:] or '-' in datetime_str[-6:]:
            # Ya tiene zona horaria -> Chile
            dt = datetime.fromisoformat(datetime_str)
            dt_chile = dt.astimezone(CHILE_TZ)
        else:
            # Sin zona horaria -> asumir que es hora de Chile
            dt_naive = datetime.fromisoformat(datetime_str)
            dt_chile = CHILE_TZ.localize(dt_naive)
        
        result = dt_chile.isoformat()
        logger.info(f"Normalized result: {result}")
        
        # Verificar que el resultado no tenga formato inválido (zona horaria + Z)
        if result.endswith('Z') and ('+' in result[:-1] or '-' in result[-10:-1]):
            logger.error(f"Invalid format detected: {result}")
            # Remover la Z si ya tiene zona horaria
            result = result[:-1]
            logger.info(f"Fixed format: {result}")
        
        return result
    except Exception as e:
        logger.error(f"Error normalizing timezone for {datetime_str}: {e}")
        # Si falla, devolver original con zona horaria de Chile
        fallback = datetime_str + '-03:00' if 'T' in datetime_str and not any(x in datetime_str for x in ['Z', '+', '-03:00', '-04:00']) else datetime_str
        logger.info(f"Fallback result: {fallback}")
        return fallback

def format_date_spanish(date: datetime, include_year: bool = True) -> str:
    """
    Formatea una fecha en español usando mapeos centralizados
    
    Args:
        date: Objeto datetime a formatear
        include_year: Si incluir el año en el formato
        
    Returns:
        Fecha formateada en español (ej: "viernes 15 de marzo de 2024")
    """
    try:
        dia_nombre = DIAS_ES[date.weekday()]
        mes_nombre = MESES_ES[date.month]
        
        if include_year:
            return f"{dia_nombre} {date.day} de {mes_nombre} de {date.year}"
        else:
            return f"{dia_nombre} {date.day} de {mes_nombre}"
            
    except (IndexError, AttributeError) as e:
        logger.error(f"Error formatting date {date}: {e}")
        return str(date)

def translate_english_date_to_spanish(english_date_str: str) -> str:
    """
    Traduce una fecha en inglés a español usando mapeos centralizados
    
    Args:
        english_date_str: Fecha en formato inglés (ej: "Monday 15 de March")
        
    Returns:
        Fecha traducida al español
    """
    result = english_date_str
    
    # Traducir días de la semana
    for en_day, es_day in DIAS_SEMANA_EN_ES.items():
        result = result.replace(en_day, es_day)
    
    # Traducir meses
    for en_month, es_month in MESES_EN_ES.items():
        result = result.replace(en_month, es_month)
    
    return result

def get_day_name_spanish(weekday: int) -> str:
    """
    Obtiene el nombre del día en español dado un número de día de la semana
    
    Args:
        weekday: Número del día (0=lunes, 6=domingo)
        
    Returns:
        Nombre del día en español
    """
    try:
        return DIAS_ES[weekday]
    except IndexError:
        logger.error(f"Invalid weekday number: {weekday}")
        return f"día_{weekday}"

def get_month_name_spanish(month: int) -> str:
    """
    Obtiene el nombre del mes en español dado un número de mes
    
    Args:
        month: Número del mes (1-12)
        
    Returns:
        Nombre del mes en español
    """
    try:
        return MESES_ES[month]
    except IndexError:
        logger.error(f"Invalid month number: {month}")
        return f"mes_{month}"

def parse_day_name_to_weekday(day_name: str) -> int:
    """
    Convierte un nombre de día en español a número de día de la semana
    
    Args:
        day_name: Nombre del día en español (ej: "lunes", "miércoles")
        
    Returns:
        Número del día de la semana (0=lunes, 6=domingo) o -1 si no es válido
    """
    return DIAS_MAP.get(day_name.lower(), -1)

def create_slot_dict(slot_start: datetime, slot_end: datetime, duration_hours: float) -> dict:
    """
    Crea un diccionario estándar para slots de horario usando formateo centralizado
    
    Args:
        slot_start: Datetime de inicio del slot
        slot_end: Datetime de fin del slot  
        duration_hours: Duración en horas
        
    Returns:
        Dict con formato estándar para slots
    """
    fecha_esp = format_date_spanish(slot_start, include_year=True)
    time_str = f"{slot_start.strftime('%H:%M')} - {slot_end.strftime('%H:%M')}"
    
    return {
        'start': slot_start,
        'end': slot_end,
        'date_str': fecha_esp,
        'time_str': time_str,
        'duration_hours': duration_hours
    } 