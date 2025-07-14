"""
🗓️ UTILIDADES COMUNES PARA HERRAMIENTAS DE CALENDARIO

Centraliza código duplicado y funciones de formateo para evitar repetición
en calendar_tool.py y otras herramientas de calendario.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from .timezone_config import get_sistema_timezone, get_sistema_timezone_offset

logger = logging.getLogger(__name__)

# 🌎 Zona horaria de Chile - USANDO TIMEZONE FIJO DEL SISTEMA
from datetime import timezone, timedelta
def get_chile_tz_fixed():
    """Obtiene timezone fijo de Chile basado en la configuración global del sistema."""
    offset_hours = get_sistema_timezone_offset()
    return timezone(timedelta(hours=offset_hours))

# 🌎 Zona horaria de Chile - DINÁMICO basado en configuración global
def get_chile_tz():
    """Obtiene timezone de Chile actualizado basado en configuración global."""
    return get_chile_tz_fixed()

# Para compatibilidad, pero ahora es dinámico
CHILE_TZ = get_chile_tz_fixed()  # Se actualizará al cambiar timezone_config.py

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
    Normaliza una fecha/hora a la zona horaria de Chile de forma robusta usando zoneinfo.
    
    Args:
        datetime_str: String de fecha/hora en formato ISO
    
    Returns:
        String de fecha/hora normalizado a zona horaria de Chile
    """
    try:
        logger.info(f"Normalizing timezone for: {datetime_str} using zoneinfo")
        
        # Parsear la fecha. fromisoformat maneja offsets.
        # El replace de 'Z' es por compatibilidad con versiones antiguas de Python
        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))

        if dt.tzinfo:
            # USAR TIMEZONE GLOBAL DEL SISTEMA
            # Forzar consistencia usando la constante global configurada
            offset_hours = dt.utcoffset().total_seconds() / 3600
            sistema_offset = get_sistema_timezone_offset()
            
            # Si es un timezone chileno (-3 o -4 horas), normalizar al timezone del sistema
            if offset_hours in [-3, -4]:
                if offset_hours == sistema_offset:
                    logger.info(f"Timezone ya coincide con sistema ({offset_hours:+.0f}h), manteniendo original")
                    result = dt.isoformat()
                else:
                    logger.info(f"Timezone chileno detectado ({offset_hours:+.0f}h), normalizando a timezone del sistema ({sistema_offset:+.0f}h)")
                    # CORRECCIÓN: Mantener la misma hora local, solo cambiar el offset
                    # En lugar de convertir a UTC y cambiar horas, solo cambiar el timezone
                    dt_naive = dt.replace(tzinfo=None)  # Remover timezone pero mantener hora local
                    sistema_tz_str = get_sistema_timezone()
                    result = dt_naive.isoformat() + sistema_tz_str
                    logger.info(f"Normalizado a timezone del sistema manteniendo hora local: {result}")
            else:
                # Convertir cualquier otro timezone al timezone del sistema
                dt_utc = dt.astimezone(ZoneInfo('UTC'))
                from datetime import timedelta
                sistema_offset = get_sistema_timezone_offset()
                dt_sistema = dt_utc.replace(tzinfo=None) + timedelta(hours=sistema_offset)
                sistema_tz_str = get_sistema_timezone()
                result = dt_sistema.isoformat() + sistema_tz_str
                logger.info(f"Timezone no chileno, convertido a timezone del sistema: {result}")
        else:
            # Si es 'naive' (sin zona horaria), aplicar timezone del sistema
            from datetime import timedelta
            sistema_tz_str = get_sistema_timezone()
            result = dt.isoformat() + sistema_tz_str
            logger.info(f"Fecha naive, aplicando timezone del sistema: {result}")

        logger.info(f"Normalized result: {result}")
        
        return result
    except Exception as e:
        logger.error(f"Error normalizing timezone for {datetime_str}: {e}")
        # Fallback simple para evitar romper la ejecución
        return datetime_str

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