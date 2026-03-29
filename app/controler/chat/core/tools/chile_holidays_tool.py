from typing import Dict
import dateparser
from datetime import datetime
import logging
from langchain_core.tools import tool
import holidays

logger = logging.getLogger(__name__)


def normalize_date(text: str) -> datetime | None:
    """
    Normaliza una fecha en texto a objeto datetime usando configuración para Chile.
    """
    try:
        # Usamos una fecha base en el futuro para que dateparser no asuma años pasados
        # si el usuario no especifica el año.
        base_date = datetime.now()
        if base_date.month > 10: # Si estamos a fin de año, es más probable que se refieran al siguiente
            base_date = base_date.replace(year=base_date.year + 1)

        return dateparser.parse(
            text,
            languages=["es"],
            settings={
                "TIMEZONE": "America/Santiago",
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": base_date
            }
        )
    except Exception as e:
        logger.error(f"Error parseando fecha '{text}': {str(e)}")
        return None

@tool(parse_docstring=False)
def check_chile_holiday_tool(query: str) -> str:
    """Verifica si una fecha específica es feriado en Chile.

    Esta herramienta puede interpretar fechas en lenguaje natural en español,
    como "mañana", "18 de septiembre", "2 de julio", etc.
    Siempre debes indicar la fecha que quieres consultar.

    Args:
        query: Texto que contiene la fecha a verificar (ej: "es feriado el 2 de julio", "18 de septiembre")

    Returns:
        Una cadena de texto indicando si la fecha es feriado o no.
        - "STATUS: ES FERIADO | MOTIVO: [Razón del feriado]"
        - "STATUS: NO ES FERIADO"
        - "STATUS: ERROR | MENSAJE: [Detalle del error]"
    """
    try:
        logger.info(f"Verificando feriado para: '{query}'")

        clean_query = query.lower()
        for phrase in ["es feriado", "¿es feriado", "es un feriado", "feriado", "¿", "?"]:
            clean_query = clean_query.replace(phrase, "").strip()

        if not clean_query:
            return "STATUS: ERROR | MENSAJE: Por favor especifica una fecha para verificar."

        fecha = normalize_date(clean_query)

        if not fecha:
            return f"STATUS: ERROR | MENSAJE: No pude entender la fecha '{query}'."

        # Obtener los feriados de Chile para el año de la fecha consultada
        # Usamos subdiv='RM' para obtener solo los feriados nacionales (evitando regionales/opcionales)
        chile_holidays = holidays.country_holidays('CL', subdiv='RM', years=fecha.year)

        holiday_reason = chile_holidays.get(fecha.date())

        if holiday_reason:
            return f"STATUS: ES FERIADO | MOTIVO: {holiday_reason}"
        else:
            return "STATUS: NO ES FERIADO"

    except Exception as e:
        logger.error(f"Error en check_chile_holiday_tool: {str(e)}")
        return f"STATUS: ERROR | MENSAJE: Ocurrió un error al verificar la fecha: {str(e)}"

@tool(parse_docstring=False)
def next_chile_holidays_tool(query: str = "") -> str:
    """Muestra los próximos feriados de Chile.

    Args:
        query: Opcional - número de feriados a mostrar (ej: "5") o vacío para mostrar los próximos 3

    Returns:
        Lista de los próximos feriados en Chile.
    """
    try:
        num_holidays = 3
        if query.strip().isdigit():
            num_holidays = min(int(query.strip()), 10)

        today = datetime.now().date()
        current_year = today.year
        
        # Consultamos feriados del año actual y el siguiente para tener margen
        chile_holidays = holidays.country_holidays('CL', years=[current_year, current_year + 1])
        
        future_holidays = {date: name for date, name in chile_holidays.items() if date >= today}
        
        # Ordenar y tomar los próximos N
        sorted_holidays = sorted(future_holidays.items())
        proximos_feriados = sorted_holidays[:num_holidays]

        if not proximos_feriados:
            return "No se encontraron próximos feriados."

        resultado = f"🇨🇱 Próximos {len(proximos_feriados)} feriados en Chile:\n"
        for fecha, motivo in proximos_feriados:
            resultado += f" - {fecha.strftime('%Y-%m-%d')}: {motivo}\n"

        return resultado

    except Exception as e:
        logger.error(f"Error en next_chile_holidays_tool: {str(e)}")
        return f"Ocurrió un error al obtener los próximos feriados: {str(e)}" 