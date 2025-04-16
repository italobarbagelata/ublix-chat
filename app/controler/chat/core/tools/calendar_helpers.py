import logging
import re
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

# Zona horaria para Chile (Santiago)
TIMEZONE = pytz.timezone('America/Santiago')

def parse_natural_date(text):
    """
    Convierte una fecha en lenguaje natural a una fecha en formato ISO.
    
    Args:
        text: Texto con la fecha en lenguaje natural
        
    Returns:
        Tupla con la fecha de inicio y fin en formato ISO si se puede interpretar,
        None en caso contrario
    """
    
    text = text.lower()
    logger.info(f"Parseando fecha natural: '{text}'")
    
    now = datetime.now(TIMEZONE)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Buscar día de la semana
    days_map = {
        'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2, 
        'jueves': 3, 'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6
    }
    
    # Mapeo de meses para fechas específicas
    month_map = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }
    
    # Intentar varios patrones de fecha
    
    # 1. Patrón específico: "mañana 27 de marzo"
    specific_date_pattern = r'(mañana|manana|hoy|pasado\s+mañana|pasado\s+manana)?\s*(\d{1,2})\s+de\s+([a-zé]+)'
    specific_match = re.search(specific_date_pattern, text)
    
    if specific_match:
        logger.info(f"Detectado patrón específico de fecha: {specific_match.group(0)}")
        prefix = specific_match.group(1)
        day = int(specific_match.group(2))
        month_name = specific_match.group(3).lower()
        
        logger.info(f"Componentes extraídos: prefix={prefix}, day={day}, month_name={month_name}")
        
        if month_name in month_map:
            month = month_map[month_name]
            # Por defecto usamos el año actual
            year = now.year
            
            # Si el mes ya pasó y estamos hablando de una fecha futura, podría ser el próximo año
            if month < now.month and prefix and ('mañana' in prefix or 'manana' in prefix or 'pasado' in prefix):
                year += 1
            
            try:
                # Crear la fecha base con el día y mes específicos
                date = now.replace(year=year, month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
                logger.info(f"Fecha base creada: {date.strftime('%Y-%m-%d')}")
                
                # En el caso de "mañana 27 de marzo", entender "mañana" como contextual
                # Es decir, no ajustar la fecha basándose en el prefijo, sino mantener el día 27
                # Esto es especialmente útil para casos donde "mañana" es más bien un formalismo
                if prefix and prefix in ['mañana', 'manana'] and day != (now + timedelta(days=1)).day:
                    logger.info(f"Prefijo '{prefix}' interpretado como contextual, manteniendo fecha {date.strftime('%Y-%m-%d')}")
                    # No hacemos nada, mantenemos la fecha específica
                elif prefix:
                    # Para otros casos, ajustar según el prefijo si el día mencionado no coincide con lo esperado
                    if 'mañana' in prefix or 'manana' in prefix:
                        tomorrow = today + timedelta(days=1)
                        if day != tomorrow.day or month != tomorrow.month:
                            # Si la fecha específica no coincide con mañana, priorizar la fecha específica
                            logger.info(f"Prefijo '{prefix}' y fecha específica {day}/{month} no coinciden, manteniendo fecha específica")
                        else:
                            # Si coincide, usar mañana
                            date = tomorrow
                            logger.info(f"Prefijo '{prefix}' coincide con fecha específica, usando {date.strftime('%Y-%m-%d')}")
                    elif 'pasado mañana' in prefix or 'pasado manana' in prefix:
                        # Si dice "pasado mañana", avanzamos 2 días desde hoy
                        day_after_tomorrow = today + timedelta(days=2)
                        if day != day_after_tomorrow.day or month != day_after_tomorrow.month:
                            # Si la fecha específica no coincide con pasado mañana, priorizar la fecha específica
                            logger.info(f"Prefijo '{prefix}' y fecha específica {day}/{month} no coinciden, manteniendo fecha específica")
                        else:
                            # Si coincide, usar pasado mañana
                            date = day_after_tomorrow
                            logger.info(f"Prefijo '{prefix}' coincide con fecha específica, usando {date.strftime('%Y-%m-%d')}")
                    elif 'hoy' in prefix:
                        # Si dice "hoy", usamos la fecha de hoy con la hora especificada
                        if day != today.day or month != today.month:
                            # Si la fecha específica no coincide con hoy, priorizar la fecha específica
                            logger.info(f"Prefijo '{prefix}' y fecha específica {day}/{month} no coinciden, manteniendo fecha específica")
                        else:
                            # Si coincide, usar hoy
                            date = today
                            logger.info(f"Prefijo '{prefix}' coincide con fecha específica, usando {date.strftime('%Y-%m-%d')}")
                
                logger.info(f"Fecha final después de ajustes por prefijo: {date.strftime('%Y-%m-%d')}")
            except ValueError as e:
                # Fecha inválida, como 30 de febrero
                logger.warning(f"Fecha inválida: {day} de {month_name} - Error: {str(e)}")
                return None
        else:
            logger.warning(f"Mes no reconocido: {month_name}")
            return None
    
    # 2. Patrones relativos simples
    elif 'hoy' in text:
        date = today
        logger.info(f"Detectado 'hoy', usando fecha: {date.strftime('%Y-%m-%d')}")
    elif 'mañana' in text or 'manana' in text:
        date = today + timedelta(days=1)
        logger.info(f"Detectado 'mañana', usando fecha: {date.strftime('%Y-%m-%d')}")
    elif 'pasado mañana' in text or 'pasado manana' in text:
        date = today + timedelta(days=2)
        logger.info(f"Detectado 'pasado mañana', usando fecha: {date.strftime('%Y-%m-%d')}")
    
    # 3. Día de la semana
    else:
        for day_name, day_num in days_map.items():
            if day_name in text:
                days_ahead = day_num - today.weekday()
                if days_ahead <= 0:  # Si es el mismo día o anterior, vamos a la próxima semana
                    days_ahead += 7
                date = today + timedelta(days=days_ahead)
                logger.info(f"Detectado día '{day_name}', usando fecha: {date.strftime('%Y-%m-%d')}")
                break
        else:
            # 4. Formatos de fecha explícita
            date_patterns = [
                r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})',  # dd/mm/yyyy, dd-mm-yyyy
                r'(\d{1,2}) de (\w+)( de (\d{2,4}))?'  # dd de mes [de yyyy]
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    logger.info(f"Detectado formato de fecha explícita: {match.group(0)}")
                    if len(match.groups()) >= 3 and ('/' in pattern or '-' in pattern or '.' in pattern):
                        day = int(match.group(1))
                        month = int(match.group(2))
                        year = int(match.group(3))
                        if year < 100:  # Assuming 2-digit year
                            year += 2000
                        try:
                            date = now.replace(year=year, month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
                            logger.info(f"Detectada fecha explícita: {date.strftime('%Y-%m-%d')}")
                            break
                        except ValueError as e:
                            logger.warning(f"Fecha inválida: {day}/{month}/{year} - Error: {str(e)}")
                            continue
                    elif 'de' in pattern:
                        day = int(match.group(1))
                        month_name = match.group(2).lower()
                        year = int(match.group(4)) if match.group(4) else now.year
                        
                        if month_name in month_map:
                            month = month_map[month_name]
                            try:
                                date = now.replace(year=year, month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
                                logger.info(f"Detectada fecha con mes en texto: {date.strftime('%Y-%m-%d')}")
                                break
                            except ValueError as e:
                                logger.warning(f"Fecha inválida: {day} de {month_name} de {year} - Error: {str(e)}")
                                continue
            else:
                # No se pudo encontrar una fecha, usar mañana como fallback (más seguro que 'hoy')
                logger.warning(f"No se pudo interpretar la fecha en: '{text}', usando mañana como fallback")
                date = today + timedelta(days=1)
    
    # Buscar hora en el texto
    time_pattern = r'a las (\d{1,2})(?::(\d{2}))?(?:\s*(am|pm|a\.m\.|p\.m\.|hrs))?'
    match = re.search(time_pattern, text)
    
    # Si no encuentra con "a las", intentar un patrón más simple
    if not match:
        time_pattern = r'(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm|a\.m\.|p\.m\.|hrs))?'
        match = re.search(time_pattern, text)
    
    hour = 9  # Hora por defecto (9 AM)
    minute = 0
    
    if match:
        logger.info(f"Detectado patrón de hora: {match.group(0)}")
        hour_str = match.group(1)
        minute_str = match.group(2)
        ampm = match.group(3) if len(match.groups()) >= 3 else None
        
        hour = int(hour_str)
        logger.info(f"Hora extraída: {hour}, minuto: {minute_str}, am/pm: {ampm}")
        
        # Ajustar para AM/PM
        if ampm:
            if ('pm' in ampm.lower() or 'p.m.' in ampm.lower()) and hour < 12:
                hour += 12
                logger.info(f"Ajustando hora PM: {hour}")
            elif ('am' in ampm.lower() or 'a.m.' in ampm.lower()) and hour == 12:
                hour = 0
                logger.info(f"Ajustando 12 AM a 0: {hour}")
        # Asumir PM para horas entre 1 y 11 sin indicador AM/PM (hora laboral)
        elif 1 <= hour <= 11:
            # Palabras que indican "tarde" o "noche"
            tarde_keywords = ['tarde', 'noche', 'evening', 'night']
            if any(keyword in text for keyword in tarde_keywords):
                hour += 12
                logger.info(f"Asumiendo PM por contexto: {hour}")
        
        if minute_str:
            minute = int(minute_str)
            logger.info(f"Minuto extraído: {minute}")
    else:
        logger.info(f"No se detectó patrón de hora específico, usando hora por defecto: {hour}:{minute}")
    
    # Ajustar la hora en la fecha
    start_time = date.replace(hour=hour, minute=minute)
    logger.info(f"Hora de inicio ajustada: {start_time.strftime('%Y-%m-%d %H:%M')}")
    
    # La cita dura 1 hora por defecto
    end_time = start_time + timedelta(hours=1)
    logger.info(f"Hora de fin calculada: {end_time.strftime('%Y-%m-%d %H:%M')}")
    
    # Convertir a formato ISO
    start_iso = start_time.isoformat().replace('+00:00', 'Z')
    end_iso = end_time.isoformat().replace('+00:00', 'Z')
    
    logger.info(f"Fecha y hora interpretadas - Inicio: {start_iso}, Fin: {end_iso}")
    
    return (start_iso, end_iso)

def extract_calendar_intent(text):
    """
    Extrae la intención relacionada con el calendario del texto.
    
    Args:
        text: Texto con la solicitud del usuario
        
    Returns:
        Diccionario con la acción y los parámetros si es una solicitud de calendario,
        None en caso contrario
    """
    text = text.lower().strip()
    
    # Caso especial: texto es solo un número (1, 2, etc.)
    if text.isdigit():
        return {
            'action': 'seleccionar_calendario',
            'params': {
                'numero': int(text)
            }
        }
    
    # Patrones para detectar intenciones simplificadas
    patterns = {
        'listar_calendarios': [
            r'(agenda|agendar|programar|reservar|visita|cita|quiero|puedo|necesito)',
            r'(calendario|calendarios|agenda|disponibles|listar)',
            r'quiero agendar',
            r'quiero reservar',
            r'necesito una cita',
            r'programar una visita'
        ],
        'seleccionar_calendario': [
            r'(quiero|elijo|selecciono|escojo|usar|prefiero)(\s+el|\s+la|\s+)?\s+(calendario|opción|opcion|agenda)?\s+([0-9]+)',
            r'(quiero|elijo|selecciono|escojo|usar|prefiero)(\s+el|\s+la|\s+)?\s+(calendario|agenda)\s+([a-záéíóúñ\s]+)',
            r'(calendario|opción|opcion|agenda)?\s+([0-9]+)',
            r'^([a-záéíóúñ\s]+)$' # Para aceptar solo el nombre del calendario como entrada
        ],
        'crear_visita': [
            r'(agendar|programar|crear|reservar)(\s+una|\s+un|\s+)?\s+(visita|cita|evento|reunión|reunion)',
            r'(datos|información|informacion|detalles)(\s+de|\s+para)?\s+(visita|cita|evento)',
            r'(nombre|título|titulo)\s+([a-záéíóúñ\s]+)',
            r'(fecha|hora|día|dia|momento)\s+([a-záéíóúñ0-9\s\:\-\/\.]+)'
        ]
    }
    
    # Detectar primero si es solo un nombre de calendario
    # Esta verificación tiene prioridad para resolver el problema de selección
    text_trimmed = text.strip()
    # Si es una sola palabra o un nombre corto, probablemente es una selección de calendario
    if len(text_trimmed.split()) <= 3 and not any(keyword in text_trimmed for keyword in ['agendar', 'programar', 'crear', 'reservar', 'listar']):
        # Verificar si es una selección por número
        if text_trimmed.isdigit():
            return {
                'action': 'seleccionar_calendario',
                'params': {
                    'numero': int(text_trimmed)
                }
            }
        # Si no es número, es probablemente un nombre de calendario
        return {
            'action': 'seleccionar_calendario',
            'params': {
                'nombre': text_trimmed
            }
        }
    
    # Verificar cada patrón para detectar la intención
    for intent, pattern_list in patterns.items():
        for pattern in pattern_list:
            if re.search(pattern, text):
                if intent == 'listar_calendarios':
                    return {
                        'action': 'listar_calendarios',
                        'params': {}
                    }
                
                elif intent == 'seleccionar_calendario':
                    # Buscar un número de calendario
                    num_match = re.search(r'([0-9]+)', text)
                    if num_match:
                        return {
                            'action': 'seleccionar_calendario',
                            'params': {
                                'numero': int(num_match.group(1))
                            }
                        }
                    
                    # Buscar un nombre de calendario
                    name_match = re.search(r'(quiero|elijo|selecciono|escojo|usar|prefiero)(\s+el|\s+la|\s+)?\s+(calendario|agenda)\s+([a-záéíóúñ\s]+)', text)
                    if name_match:
                        return {
                            'action': 'seleccionar_calendario',
                            'params': {
                                'nombre': name_match.group(4).strip()
                            }
                        }
                    
                    # Si es solo el nombre
                    simple_match = re.search(r'^([a-záéíóúñ\s]+)$', text)
                    if simple_match:
                        return {
                            'action': 'seleccionar_calendario',
                            'params': {
                                'nombre': simple_match.group(1).strip()
                            }
                        }
                
                elif intent == 'crear_visita':
                    # Extraer título/nombre si existe
                    title = "Visita"  # Título por defecto
                    title_match = re.search(r'(nombre|título|titulo|sobre|para|con)\s+([a-záéíóúñ\s]+)', text)
                    if title_match:
                        title = title_match.group(2).strip()
                    
                    # Intentar extraer fechas
                    dates = parse_natural_date(text)
                    
                    if dates:
                        start_time, end_time = dates
                        return {
                            'action': 'crear_visita',
                            'params': {
                                'titulo': title,
                                'inicio': start_time,
                                'fin': end_time
                            }
                        }
                    else:
                        return {
                            'action': 'solicitar_fecha',
                            'params': {
                                'titulo': title
                            }
                        }
    
    # Si no se detectó una intención específica pero hay palabras clave de agenda
    agenda_keywords = ['agendar', 'cita', 'visita', 'calendario', 'reunión', 'reunion', 'programar', 'reservar']
    if any(keyword in text for keyword in agenda_keywords):
        return {
            'action': 'listar_calendarios',
            'params': {}
        }
    
    # No se detectó ninguna intención relacionada con el calendario
    return None

def get_all_calendars_from_project(project_id):
    """
    Obtiene todos los calendarios disponibles para un proyecto usando SupabaseDatabase.
    
    Args:
        project_id: ID del proyecto
        
    Returns:
        Lista de calendarios o lista vacía si no hay resultados
    """
    from app.resources.postgresql import SupabaseDatabase
    
    logger.info(f"Obteniendo calendarios para el proyecto {project_id}")
    
    try:
        db = SupabaseDatabase()
        
        calendars = db.select(
            'calendars',
            filters={'project_id': project_id}
        )
        
        if not calendars:
            logger.info(f"No se encontraron calendarios para el proyecto {project_id}")
            return []
            
        logger.info(f"Se encontraron {len(calendars)} calendarios")
        return calendars
    
    except Exception as e:
        logger.error(f"Error obteniendo calendarios: {str(e)}", exc_info=True)
        return []

def check_calendar_availability(calendar_id, start_time, end_time):
    """
    Verifica si hay disponibilidad en el calendario para una nueva visita
    
    Args:
        calendar_id: ID del calendario
        start_time: Fecha y hora de inicio en formato ISO
        end_time: Fecha y hora de fin en formato ISO
        
    Returns:
        (bool, str): Tupla con disponibilidad (True si está disponible) y mensaje
    """
    from app.resources.postgresql import SupabaseDatabase
    
    logger.info(f"Verificando disponibilidad en calendario {calendar_id} para {start_time} a {end_time}")
    
    try:
        db = SupabaseDatabase()
        
        # Buscar eventos que se solapen con las fechas proporcionadas
        query = f"""
        SELECT id, title, start_time, end_time 
        FROM calendar_events 
        WHERE calendar_id = '{calendar_id}' 
        AND (
            (start_time <= '{end_time}' AND end_time >= '{start_time}')
        )
        ORDER BY start_time ASC
        """
        
        overlapping_events = db.select_query('execute_query', {'sql_text': query})
        
        if not overlapping_events:
            return True, "Horario disponible"
        
        # Formatear los eventos que se solapan para mostrarlos
        events_info = []
        for event in overlapping_events:
            start = datetime.fromisoformat(event.get("start_time").replace('Z', '+00:00'))
            end = datetime.fromisoformat(event.get("end_time").replace('Z', '+00:00'))
            
            start_formatted = start.strftime("%d/%m/%Y %H:%M")
            end_formatted = end.strftime("%d/%m/%Y %H:%M")
            
            events_info.append(f"'{event.get('title')}' de {start_formatted} a {end_formatted}")
        
        return False, f"Horario no disponible. Eventos existentes: {', '.join(events_info)}"
    
    except Exception as e:
        logger.error(f"Error verificando disponibilidad: {str(e)}", exc_info=True)
        return False, f"Error al verificar disponibilidad: {str(e)}" 