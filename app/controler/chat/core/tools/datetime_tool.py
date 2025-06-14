from typing import Dict
import dateparser
from datetime import datetime, timedelta
import logging
from langchain.tools import tool
import locale
import pytz

logger = logging.getLogger(__name__)

# Configurar locale para español
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES')
    except:
        logger.warning("No se pudo configurar locale en español")

@tool(parse_docstring=False)
def current_datetime_tool(query: str) -> str:
    """Proporciona información sobre fecha y hora actual, días de la semana, y cálculos de fechas básicos.
    
    Esta herramienta maneja consultas como:
    - ¿Qué día es hoy?
    - ¿Qué fecha es mañana?
    - ¿Qué hora es?
    - ¿Cuántos días faltan para el viernes?
    - ¿Qué día de la semana es el 25 de diciembre?
    
    Args:
        query: Pregunta sobre fecha, hora, día de la semana o cálculos de tiempo
        
    Returns:
        Información específica sobre fechas y tiempo
    """
    try:
        logger.info(f"Procesando consulta de fecha/tiempo: '{query}'")
        
        query_lower = query.lower().strip()
        ahora = datetime.now(pytz.timezone('America/Santiago'))
        
        # Mapeo de días de la semana en español
        dias_semana = {
            0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 
            4: "viernes", 5: "sábado", 6: "domingo"
        }
        
        # Mapeo de meses en español
        meses = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
            7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        
        # ¿Qué día es hoy?
        if any(palabra in query_lower for palabra in ["qué día es hoy", "que día es hoy", "día de hoy", "hoy qué día", "qué día es", "que día es"]):
            dia_nombre = dias_semana[ahora.weekday()]
            fecha_formateada = f"{ahora.day} de {meses[ahora.month]} de {ahora.year}"
            hora_formateada = ahora.strftime("%H:%M")
            return f"Hoy es **{dia_nombre}** {fecha_formateada} y son las **{hora_formateada}** horas."
        
        # ¿Qué fecha es hoy?
        if any(palabra in query_lower for palabra in ["qué fecha es hoy", "que fecha es hoy", "fecha de hoy", "fecha actual"]):
            dia_nombre = dias_semana[ahora.weekday()]
            fecha_formateada = f"{ahora.day} de {meses[ahora.month]} de {ahora.year}"
            return f"La fecha de hoy es **{dia_nombre} {fecha_formateada}**."
        
        # ¿Qué hora es?
        if any(palabra in query_lower for palabra in ["qué hora es", "que hora es", "hora actual", "la hora"]):
            hora_formateada = ahora.strftime("%H:%M")
            return f"Son las **{hora_formateada}** horas."
        
        # Mañana
        if "mañana" in query_lower:
            manana = ahora + timedelta(days=1)
            dia_nombre = dias_semana[manana.weekday()]
            fecha_formateada = f"{manana.day} de {meses[manana.month]} de {manana.year}"
            return f"Mañana es **{dia_nombre}** {fecha_formateada}."
        
        # Ayer
        if "ayer" in query_lower:
            ayer = ahora - timedelta(days=1)
            dia_nombre = dias_semana[ayer.weekday()]
            fecha_formateada = f"{ayer.day} de {meses[ayer.month]} de {ayer.year}"
            return f"Ayer fue **{dia_nombre}** {fecha_formateada}."
        
        # ¿Cuántos días faltan para [día de la semana]?
        if "cuántos días faltan" in query_lower or "cuantos días faltan" in query_lower:
            for i, dia in enumerate(dias_semana.values()):
                if dia in query_lower:
                    dias_hasta = (i - ahora.weekday()) % 7
                    if dias_hasta == 0:
                        return f"Hoy es {dia}."
                    elif dias_hasta == 1:
                        return f"Falta **1 día** para el {dia} (mañana)."
                    else:
                        return f"Faltan **{dias_hasta} días** para el {dia}."
            
            # Si no encontró un día específico, intentar parsear una fecha
            try:
                fecha_objetivo = dateparser.parse(
                    query_lower.replace("cuántos días faltan para", "").replace("cuantos días faltan para", "").strip(),
                    languages=["es"],
                    settings={"TIMEZONE": "America/Santiago"}
                )
                if fecha_objetivo:
                    diferencia = (fecha_objetivo.date() - ahora.date()).days
                    if diferencia == 0:
                        return "Esa fecha es hoy."
                    elif diferencia == 1:
                        return "Esa fecha es mañana."
                    elif diferencia > 0:
                        return f"Faltan **{diferencia} días** para esa fecha."
                    else:
                        return f"Esa fecha fue hace **{abs(diferencia)} días**."
            except:
                pass
        
        # ¿Qué fecha es el próximo [día de la semana]?
        if "próximo" in query_lower or "proximo" in query_lower:
            for i, dia in enumerate(dias_semana.values()):
                if dia in query_lower:
                    # Calcular el próximo día de la semana
                    dias_hasta = (i - ahora.weekday()) % 7
                    if dias_hasta == 0:
                        dias_hasta = 7  # Si es hoy, tomamos el próximo
                    fecha_futura = ahora + timedelta(days=dias_hasta)
                    fecha_formateada = f"{fecha_futura.day} de {meses[fecha_futura.month]} de {fecha_futura.year}"
                    return f"El próximo {dia} será el **{fecha_formateada}**."
        
        # ¿Qué día de la semana es [fecha]?
        if "qué día de la semana" in query_lower or "que día de la semana" in query_lower:
            # Extraer la fecha de la consulta
            fecha_texto = query_lower.replace("¿qué día de la semana es", "").replace("¿que día de la semana es", "")
            fecha_texto = fecha_texto.replace("qué día de la semana es", "").replace("que día de la semana es", "")
            fecha_texto = fecha_texto.replace("el ", "").replace("?", "").strip()
            
            logger.info(f"Procesando fecha específica: '{fecha_texto}'")
            
            try:
                fecha_parseada = dateparser.parse(
                    fecha_texto,
                    languages=["es"],
                    settings={"TIMEZONE": "America/Santiago"}
                )
                
                logger.info(f"Fecha parseada: {fecha_parseada}")
                
                if fecha_parseada:
                    dia_nombre = dias_semana[fecha_parseada.weekday()]
                    fecha_formateada = f"{fecha_parseada.day} de {meses[fecha_parseada.month]} de {fecha_parseada.year}"
                    
                    # Calcular diferencia con hoy
                    diferencia = (fecha_parseada.date() - ahora.date()).days
                    if diferencia == 0:
                        extra = " (hoy)"
                    elif diferencia == 1:
                        extra = " (mañana)"
                    elif diferencia == -1:
                        extra = " (ayer)"
                    elif diferencia > 0:
                        extra = f" (en {diferencia} días)"
                    else:
                        extra = f" (hace {abs(diferencia)} días)"
                    
                    return f"El {fecha_formateada} es **{dia_nombre}**{extra}."
            except Exception as e:
                logger.error(f"Error parseando fecha específica: {e}")
                pass
        
        # Intento genérico de parsear cualquier fecha mencionada
        try:
            fecha_parseada = dateparser.parse(
                query,
                languages=["es"],
                settings={"TIMEZONE": "America/Santiago"}
            )
            if fecha_parseada:
                dia_nombre = dias_semana[fecha_parseada.weekday()]
                fecha_formateada = f"{fecha_parseada.day} de {meses[fecha_parseada.month]} de {fecha_parseada.year}"
                
                # Calcular diferencia con hoy
                diferencia = (fecha_parseada.date() - ahora.date()).days
                if diferencia == 0:
                    extra = " (hoy)"
                elif diferencia == 1:
                    extra = " (mañana)"
                elif diferencia == -1:
                    extra = " (ayer)"
                elif diferencia > 0:
                    extra = f" (en {diferencia} días)"
                else:
                    extra = f" (hace {abs(diferencia)} días)"
                
                return f"La fecha {fecha_formateada} es **{dia_nombre}**{extra}."
        except:
            pass
        
        # Si no se pudo procesar la consulta
        return "No pude entender tu consulta sobre fechas. Prueba preguntas como: '¿Qué día es hoy?', '¿Qué fecha es mañana?', '¿Cuántos días faltan para el viernes?', etc."
        
    except Exception as e:
        logger.error(f"Error en current_datetime_tool: {str(e)}")
        return f"Ocurrió un error al procesar la consulta de fecha/tiempo: {str(e)}"

@tool(parse_docstring=False)
def week_info_tool(query: str) -> str:
    """Proporciona información sobre la semana actual, próxima semana, semanas del mes, etc.
    
    Maneja consultas como:
    - ¿En qué semana del año estamos?
    - ¿Cuándo empieza la próxima semana?
    - ¿Qué días tiene esta semana?
    
    Args:
        query: Pregunta sobre información de semanas
        
    Returns:
        Información sobre semanas
    """
    try:
        ahora = datetime.now()
        query_lower = query.lower().strip()
        
        # Mapeo de días de la semana
        dias_semana = {
            0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 
            4: "viernes", 5: "sábado", 6: "domingo"
        }
        
        meses = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
            7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        
        # ¿En qué semana del año estamos?
        if "semana del año" in query_lower:
            semana_año = ahora.isocalendar()[1]
            return f"Estamos en la **semana {semana_año}** del año {ahora.year}."
        
        # ¿Cuándo empieza/termina la semana?
        if "empieza" in query_lower and "semana" in query_lower:
            # Calcular el lunes de esta semana
            dias_hasta_lunes = ahora.weekday()
            lunes = ahora - timedelta(days=dias_hasta_lunes)
            lunes_formateado = f"{lunes.day} de {meses[lunes.month]}"
            return f"Esta semana empezó el **lunes {lunes_formateado}**."
        
        if "termina" in query_lower and "semana" in query_lower:
            # Calcular el domingo de esta semana
            dias_hasta_domingo = 6 - ahora.weekday()
            domingo = ahora + timedelta(days=dias_hasta_domingo)
            domingo_formateado = f"{domingo.day} de {meses[domingo.month]}"
            return f"Esta semana termina el **domingo {domingo_formateado}**."
        
        # ¿Qué días tiene esta semana?
        if "días" in query_lower and "semana" in query_lower:
            # Calcular todos los días de esta semana
            dias_hasta_lunes = ahora.weekday()
            lunes = ahora - timedelta(days=dias_hasta_lunes)
            
            resultado = "📅 **Días de esta semana:**\n\n"
            for i in range(7):
                dia = lunes + timedelta(days=i)
                dia_nombre = dias_semana[i]
                fecha_formateada = f"{dia.day} de {meses[dia.month]}"
                
                if dia.date() == ahora.date():
                    resultado += f"• **{dia_nombre.title()} {fecha_formateada}** ← *Hoy*\n"
                else:
                    resultado += f"• {dia_nombre.title()} {fecha_formateada}\n"
            
            return resultado
        
        # Próxima semana
        if "próxima semana" in query_lower or "proxima semana" in query_lower:
            # Calcular el lunes de la próxima semana
            dias_hasta_proximo_lunes = 7 - ahora.weekday()
            proximo_lunes = ahora + timedelta(days=dias_hasta_proximo_lunes)
            lunes_formateado = f"{proximo_lunes.day} de {meses[proximo_lunes.month]}"
            return f"La próxima semana empieza el **lunes {lunes_formateado}**."
        
        return "No pude entender tu consulta sobre semanas. Prueba preguntas como: '¿En qué semana del año estamos?', '¿Qué días tiene esta semana?', etc."
        
    except Exception as e:
        logger.error(f"Error en week_info_tool: {str(e)}")
        return f"Ocurrió un error al procesar la consulta sobre semanas: {str(e)}" 