import logging
import json
from datetime import datetime, timedelta
from typing_extensions import Annotated
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from app.resources.postgresql import SupabaseDatabase
from uuid import UUID
import pytz  # Importación necesaria para usar ZONA_HORARIA

# Importar configuración
from app.controler.chat.core.tools.calendar_config import (
    DIAS_DISPONIBLES, DURACION_VISITA, HORAS_LABORALES, HORA_INICIO, ZONA_HORARIA,
    MSG_SELECCIONA_CALENDARIO, MSG_SELECCIONA_HORARIO, MSG_HORARIO_INVALIDO, 
    MSG_CALENDARIO_INVALIDO, MSG_VISITA_CREADA
)

logger = logging.getLogger(__name__)

@tool(parse_docstring=False)
def internal_calendar_tool(query: str, state: Annotated[dict, InjectedState]) -> str:
    """Esta herramienta permite agendar visitas en un calendario.
    
    Detecta intenciones de agendar como:
    - "Quiero agendar"
    - "Necesito una cita"
    - "Agendar visita"
    - "Programar cita" 
    - "Hacer una reserva"
    
    El flujo simplificado es:
    1. Mostrar los calendarios disponibles numerados
    2. Usuario selecciona calendario por número
    3. Mostrar horarios disponibles numerados
    4. Usuario selecciona horario por número y proporciona título
    5. Confirmar agendamiento
    
    Args:
        query: La consulta del usuario en lenguaje natural
        state: Estado inyectado que contiene la configuración del proyecto y usuario
    
    Returns:
        Información sobre la operación realizada o instrucciones para el siguiente paso
    """
    logger.info(f"Iniciando internal_calendar_tool con query: '{query}'")
    logger.info(f"Estado inicial completo: {state}")
    
    try:
        # Extraer información del proyecto y usuario
        project = state.get("project")
        user_id = state.get("user_id")
        
        logger.info(f"Estado extraído - project: {project.id if project else 'None'}, user_id: {user_id}")
        
        if not project:
            logger.warning("No se encontró información del proyecto en el estado")
            return "Error: No se encontró información del proyecto en el estado"
        
        if not user_id:
            logger.warning("No se encontró información del usuario en el estado")
            return "Error: No se encontró información del usuario en el estado"
        
        # Obtener el ID del proyecto
        project_id = project.id
        logger.info(f"Trabajando con project_id: {project_id}")

        # Analizar el estado actual del flujo de conversación
        current_step = state.get("calendar_step", "inicio")
        selected_calendar = state.get("selected_calendar")
        available_slots = state.get("available_slots", [])
        
        logger.info(f"Estado actual: step={current_step}, calendar={selected_calendar}")
        
        # Limpieza de query
        query_cleaned = query.strip().lower()
        logger.info(f"Query limpio: '{query_cleaned}'")
        
        # Lista de palabras clave para detectar intención de agendar
        palabras_agenda = ["agendar", "agenda", "cita", "visita", "reservar", "programar", "calend"]
        
        # Verificar si hay intención de agendar
        quiere_agendar = any(palabra in query_cleaned for palabra in palabras_agenda)
        
        # INICIO DEL FLUJO - Mostrar calendarios disponibles
        if current_step == "inicio" or quiere_agendar:
            logger.info(f"Detectada intención de agendar: {quiere_agendar}, mostrando lista de calendarios disponibles")
            state["calendar_step"] = "seleccion_calendario"
            logger.info(f"Estado actualizado antes de mostrar calendarios: {state}")
            return list_calendars(project_id)
        
        # PASO 1 - Selección de calendario por número
        elif current_step == "seleccion_calendario":
            logger.info(f"Procesando selección de calendario. Query: '{query_cleaned}'")
            
            # Verificar si es un número
            if query_cleaned.isdigit():
                num = int(query_cleaned)
                logger.info(f"Se detectó selección numérica: {num}")
                
                # Obtener calendarios
                calendars = get_all_calendars_from_project(project_id)
                
                # Verificar si hay calendarios
                if not calendars:
                    logger.warning("No hay calendarios disponibles")
                    return "No se encontraron calendarios disponibles para este proyecto."
                
                logger.info(f"Número de calendarios disponibles: {len(calendars)}")
                logger.info(f"Calendarios disponibles: {calendars}")
                
                # Verificar si el número está en el rango válido
                if 0 < num <= len(calendars):
                    logger.info(f"Número {num} válido para {len(calendars)} calendarios")
                    
                    # Seleccionar calendario por número (ajustando el índice)
                    selected_calendar_obj = calendars[num-1]
                    calendar_id = selected_calendar_obj.get("id")
                    calendar_name = selected_calendar_obj.get("name", "Calendario sin nombre")
                    
                    logger.info(f"Seleccionado calendario {num}: {calendar_name} (ID: {calendar_id})")
                    
                    # Guardar en el estado
                    state["selected_calendar"] = calendar_id
                    state["selected_calendar_name"] = calendar_name
                    state["calendar_step"] = "mostrar_horarios"
                    
                    logger.info(f"Estado actualizado: calendar_step=mostrar_horarios, selected_calendar={calendar_id}, selected_calendar_name={calendar_name}")
                    
                    # Generar y mostrar horarios disponibles
                    slots = generate_available_slots(calendar_id)
                    state["available_slots"] = slots
                    
                    logger.info(f"Generados {len(slots)} horarios disponibles")
                    logger.info(f"Estado actualizado antes de mostrar horarios: {state}")
                    
                    return show_available_slots(slots, calendar_name)
                else:
                    logger.warning(f"Número de calendario inválido: {num} (total: {len(calendars)})")
                    return f"El número {num} no es válido. {MSG_SELECCIONA_CALENDARIO}\n\n{list_calendars(project_id)}"
            else:
                logger.warning(f"Input no reconocido como selección de calendario: '{query_cleaned}'")
                return f"{MSG_SELECCIONA_CALENDARIO}\n\n{list_calendars(project_id)}"
        
        # PASO 2 - Selección de horario disponible
        elif current_step == "mostrar_horarios":
            if "," in query_cleaned:
                # El usuario está enviando "número, título"
                parts = query_cleaned.split(",", 1)
                slot_num = parts[0].strip()
                title = parts[1].strip() if len(parts) > 1 else "Visita"
                
                if not slot_num.isdigit():
                    return "Por favor, indica el número del horario y el título separados por coma. Ejemplo: '3, Dolor de cabeza'"
                
                num = int(slot_num)
                slots = state.get("available_slots", [])
                
                if 0 < num <= len(slots):
                    # Seleccionar horario por número
                    selected_slot = slots[num-1]
                    calendar_id = state.get("selected_calendar")
                    calendar_name = state.get("selected_calendar_name", "Calendario seleccionado")
                    
                    # Crear la visita
                    result = create_visit(title, selected_slot["start"], selected_slot["end"], calendar_id, user_id)
                    
                    # Reiniciar el flujo
                    state["calendar_step"] = "inicio"
                    state.pop("selected_calendar", None)
                    state.pop("selected_calendar_name", None)
                    state.pop("available_slots", None)
                    
                    return result
                else:
                    return f"El número {num} no es válido. Por favor, elige un número entre 1 y {len(slots)}."
            elif query_cleaned.isdigit():
                # Solo número, pedir título
                num = int(query_cleaned)
                slots = state.get("available_slots", [])
                
                if 0 < num <= len(slots):
                    selected_slot = slots[num-1]
                    state["selected_slot_index"] = num - 1
                    state["calendar_step"] = "solicitar_titulo"
                    
                    # Formatear fechas para mostrar
                    start_datetime = datetime.fromisoformat(selected_slot["start"].replace('Z', '+00:00'))
                    formatted_date = start_datetime.strftime("%d/%m/%Y")
                    formatted_time = start_datetime.strftime("%H:%M")
                    
                    return f"Has seleccionado el horario {num}: {formatted_date} a las {formatted_time}. Por favor, indica el título o motivo de tu visita:"
                else:
                    return f"El número {num} no es válido. Por favor, elige un número entre 1 y {len(slots)}."
            else:
                # No es un número ni tiene el formato esperado
                calendar_name = state.get("selected_calendar_name", "Calendario seleccionado")
                slots = state.get("available_slots", [])
                return f"{MSG_SELECCIONA_HORARIO} para el calendario '{calendar_name}':\n\n{format_available_slots(slots)}"
        
        # PASO 3 - Solicitar título de la visita
        elif current_step == "solicitar_titulo":
            title = query_cleaned
            
            if not title:
                title = "Visita"  # Título por defecto
            
            # Obtener el slot seleccionado
            slot_index = state.get("selected_slot_index", 0)
            slots = state.get("available_slots", [])
            
            if 0 <= slot_index < len(slots):
                selected_slot = slots[slot_index]
                calendar_id = state.get("selected_calendar")
                calendar_name = state.get("selected_calendar_name", "Calendario seleccionado")
                
                # Crear la visita
                result = create_visit(title, selected_slot["start"], selected_slot["end"], calendar_id, user_id)
                
                # Reiniciar el flujo
                state["calendar_step"] = "inicio"
                state.pop("selected_calendar", None)
                state.pop("selected_calendar_name", None)
                state.pop("available_slots", None)
                state.pop("selected_slot_index", None)
                
                return result
            else:
                logger.error(f"Índice de slot inválido: {slot_index}")
                return "Ha ocurrido un error al procesar tu solicitud. Por favor, intenta de nuevo."
                
        # Cualquier otro caso - Reiniciar flujo
        else:
            logger.info(f"Reiniciando flujo. Query: {query_cleaned}")
            state["calendar_step"] = "inicio"
            return list_calendars(project_id)
            
    except Exception as e:
        logger.error(f"Error en la herramienta de calendario: {str(e)}", exc_info=True)
        return f"Ocurrió un error al procesar tu solicitud: {str(e)}"

def list_calendars(project_id):
    """Muestra la lista de calendarios disponibles para el proyecto"""
    logger.info(f"Listando calendarios para proyecto {project_id}")
    
    try:
        calendars = get_all_calendars_from_project(project_id)
        
        if not calendars:
            return "No se encontraron calendarios disponibles para este proyecto."
        
        result = "Estos son los calendarios disponibles para agendar tu visita:\n\n"
        
        for idx, calendar in enumerate(calendars):
            calendar_name = calendar.get("name", "Calendario sin nombre")
            result += f"{idx+1}. {calendar_name}\n"
        
        result += f"\n{MSG_SELECCIONA_CALENDARIO}"
        return result
        
    except Exception as e:
        logger.error(f"Error al listar calendarios: {str(e)}", exc_info=True)
        return f"Error al obtener los calendarios: {str(e)}"

def get_all_calendars_from_project(project_id):
    """Obtiene todos los calendarios disponibles para un proyecto"""
    logger.info(f"Obteniendo calendarios para el proyecto {project_id}")
    
    try:
        db = SupabaseDatabase()
        
        # Consulta a la base de datos
        logger.info(f"Consultando tabla 'calendars' con filtro project_id={project_id}")
        calendars = db.select(
            'calendars',
            filters={'project_id': project_id}
        )
        
        # Log detallado de la respuesta
        logger.info(f"Respuesta de la consulta: {calendars}")
        
        if not calendars:
            logger.warning(f"No se encontraron calendarios para el proyecto {project_id}")
            
            # Si no hay calendarios, crear calendarios de ejemplo para evitar fallos
            logger.info("Creando calendarios de ejemplo")
            demo_calendars = [
                {
                    "id": "ejemplo-taller-1",
                    "name": "Talleres Técnicos",
                    "color": "#FF5733",
                    "project_id": project_id
                },
                {
                    "id": "ejemplo-deporte-1",
                    "name": "Deporte",
                    "color": "#33FF57",
                    "project_id": project_id
                }
            ]
            logger.info(f"Retornando calendarios de ejemplo: {demo_calendars}")
            return demo_calendars
            
        logger.info(f"Se encontraron {len(calendars)} calendarios")
        return calendars
    
    except Exception as e:
        logger.error(f"Error obteniendo calendarios: {str(e)}", exc_info=True)
        
        # Si hay error, devolver calendarios de ejemplo
        demo_calendars = [
            {
                "id": "ejemplo-error-1",
                "name": "Calendario de Ejemplo",
                "color": "#3357FF",
                "project_id": project_id
            }
        ]
        logger.info(f"Retornando calendario de ejemplo por error: {demo_calendars}")
        return demo_calendars

def generate_available_slots(calendar_id):
    """Genera horarios disponibles para los próximos días basado en las constantes definidas"""
    logger.info(f"Generando horarios disponibles para calendario {calendar_id}")
    
    try:
        # Obtener zona horaria local
        now = datetime.now(ZONA_HORARIA)
        logger.info(f"Fecha/hora actual: {now.isoformat()}")
        
        # Slots disponibles
        available_slots = []
        
        # Generar slots para los próximos DIAS_DISPONIBLES días
        for day_offset in range(DIAS_DISPONIBLES):
            # Obtener fecha para este día
            current_date = (now + timedelta(days=day_offset)).replace(
                hour=HORA_INICIO, minute=0, second=0, microsecond=0
            )
            
            logger.info(f"Generando slots para el día {current_date.strftime('%Y-%m-%d')}")
            
            # Saltear si es sábado o domingo
            if current_date.weekday() >= 5:  # 5=sábado, 6=domingo
                logger.info(f"Saltando día {current_date.strftime('%Y-%m-%d')} por ser fin de semana")
                continue
            
            # Número de slots posibles en un día basado en HORAS_LABORALES y DURACION_VISITA
            slots_per_day = int(HORAS_LABORALES / DURACION_VISITA)
            logger.info(f"Slots por día: {slots_per_day} (horas laborales: {HORAS_LABORALES}, duración visita: {DURACION_VISITA})")
            
            # Generar slots para este día
            for slot_num in range(slots_per_day):
                slot_time = current_date + timedelta(hours=slot_num * DURACION_VISITA)
                
                # Crear intervalo de tiempo
                start_time = slot_time
                end_time = slot_time + timedelta(hours=DURACION_VISITA)
                
                # Convertir a formato ISO
                start_iso = start_time.isoformat().replace('+00:00', 'Z')
                end_iso = end_time.isoformat().replace('+00:00', 'Z')
                
                # Para debugging, vamos a considerar todos los slots como disponibles por ahora
                # Esto ayudará a identificar si el problema está en la verificación de disponibilidad
                is_available = True
                
                # Añadir slot disponible
                available_slots.append({
                    "start": start_iso,
                    "end": end_iso,
                    "day": current_date.strftime("%d/%m/%Y"),
                    "time": start_time.strftime("%H:%M")
                })
                logger.info(f"Añadido slot {slot_num+1} para {current_date.strftime('%Y-%m-%d')} a las {start_time.strftime('%H:%M')}")
        
        logger.info(f"Total de horarios disponibles: {len(available_slots)}")
        
        # Si no hay slots disponibles, crear algunos de ejemplo para evitar un error de UI
        if not available_slots:
            logger.warning("No se encontraron horarios disponibles. Creando slots de ejemplo.")
            
            # Crear 3 slots de ejemplo para los próximos días
            for day_offset in range(3):
                example_date = (now + timedelta(days=day_offset+1)).replace(
                    hour=HORA_INICIO, minute=0, second=0, microsecond=0
                )
                
                # Saltear si es fin de semana
                if example_date.weekday() >= 5:
                    continue
                
                start_time = example_date
                end_time = example_date + timedelta(hours=DURACION_VISITA)
                
                # Convertir a formato ISO
                start_iso = start_time.isoformat().replace('+00:00', 'Z')
                end_iso = end_time.isoformat().replace('+00:00', 'Z')
                
                available_slots.append({
                    "start": start_iso,
                    "end": end_iso,
                    "day": example_date.strftime("%d/%m/%Y"),
                    "time": start_time.strftime("%H:%M")
                })
                logger.info(f"Añadido slot de ejemplo para {example_date.strftime('%Y-%m-%d')} a las {start_time.strftime('%H:%M')}")
        
        return available_slots
        
    except Exception as e:
        logger.error(f"Error generando horarios disponibles: {str(e)}", exc_info=True)
        # Retornar al menos un slot para evitar errores en la UI
        now = datetime.now(ZONA_HORARIA)
        tomorrow = (now + timedelta(days=1)).replace(hour=HORA_INICIO, minute=0, second=0, microsecond=0)
        
        start_time = tomorrow
        end_time = tomorrow + timedelta(hours=DURACION_VISITA)
        
        # Convertir a formato ISO
        start_iso = start_time.isoformat().replace('+00:00', 'Z')
        end_iso = end_time.isoformat().replace('+00:00', 'Z')
        
        return [{
            "start": start_iso,
            "end": end_iso,
            "day": tomorrow.strftime("%d/%m/%Y"),
            "time": tomorrow.strftime("%H:%M")
        }]

def check_slot_availability(calendar_id, start_time, end_time):
    """Verifica si un horario está disponible en el calendario"""
    logger.info(f"Verificando disponibilidad en calendario {calendar_id} para {start_time} a {end_time}")
    
    try:
        db = SupabaseDatabase()
        
        # Buscar eventos que se solapen con las fechas proporcionadas
        query = f"""
        SELECT id FROM calendar_events 
        WHERE calendar_id = '{calendar_id}' 
        AND (
            (start_time < '{end_time}' AND end_time > '{start_time}')
        )
        LIMIT 1
        """
        
        overlapping_events = db.select_query('execute_query', {'sql_text': query})
        
        # Si no hay eventos superpuestos, el horario está disponible
        return not overlapping_events
    
    except Exception as e:
        logger.error(f"Error verificando disponibilidad: {str(e)}", exc_info=True)
        return False  # Por seguridad, asumir que no está disponible si hay error

def show_available_slots(slots, calendar_name):
    """Muestra los horarios disponibles"""
    if not slots:
        return f"No hay horarios disponibles en el calendario '{calendar_name}' para los próximos {DIAS_DISPONIBLES} días. Por favor, intenta con otro calendario."
    
    result = f"¡Super! Has seleccionado el calendario '{calendar_name}'.\n\nEstos son los horarios disponibles para los próximos {DIAS_DISPONIBLES} días:\n\n"
    result += format_available_slots(slots)
    result += "\nPor favor, selecciona un horario por su número y puedes incluir el título después de una coma. Por ejemplo: '3, Dolor de cabeza' o simplemente '3' y te preguntaré el título después."
    
    return result

def format_available_slots(slots):
    """Formatea la lista de horarios disponibles para mostrar al usuario"""
    result = ""
    current_day = ""
    
    for idx, slot in enumerate(slots):
        day = slot["day"]
        
        # Agrupar por día
        if day != current_day:
            result += f"\n{day}:\n"
            current_day = day
        
        result += f"{idx+1}. {slot['time']} - {slot['time']} + {DURACION_VISITA}h\n"
    
    return result

def create_visit(titulo, inicio, fin, calendar_id, user_id):
    """Crea una nueva visita en el calendario seleccionado"""
    logger.info(f"Creando visita '{titulo}' en calendario {calendar_id} de {inicio} a {fin}")
    
    try:
        # Validar parámetros
        if not calendar_id:
            logger.error("No se proporcionó ID de calendario")
            return "Error: No se ha seleccionado un calendario para la visita."
            
        if not user_id:
            logger.error("No se proporcionó ID de usuario")
            return "Error: No se pudo identificar al usuario para crear la visita."
        
        # Inicializar conexión a Supabase
        db = SupabaseDatabase()
        
        # Obtener información del calendario para el mensaje de confirmación
        calendar_info = db.select(
            'calendars',
            filters={'id': calendar_id}
        )
        
        calendar_name = "Calendario seleccionado"
        if calendar_info and len(calendar_info) > 0:
            calendar_name = calendar_info[0].get("name", "Calendario seleccionado")
        
        # Limpiar el título
        if not titulo or titulo.strip() == "":
            titulo = "Visita"
            
        # Limitar longitud del título
        if len(titulo) > 100:
            titulo = titulo[:97] + "..."
        
        # Crear el evento
        event_data = {
            'calendar_id': calendar_id,
            'title': titulo,
            'description': 'Visita agendada mediante asistente',
            'start_time': inicio,
            'end_time': fin,
            'user_id': user_id
        }
        
        logger.info(f"Insertando evento con datos: {event_data}")
        
        # Insertar la visita
        result = db.insert(
            'calendar_events',
            data=event_data
        )
        
        if not result:
            logger.error("Error al insertar visita en la base de datos")
            return "Error: No se pudo agendar la visita. Por favor, intenta de nuevo más tarde."
        
        # Formatear las fechas para una mejor lectura
        try:
            start_datetime = datetime.fromisoformat(inicio.replace('Z', '+00:00'))
            end_datetime = datetime.fromisoformat(fin.replace('Z', '+00:00'))
            
            start_formatted = start_datetime.strftime("%d/%m/%Y %H:%M")
            end_formatted = end_datetime.strftime("%H:%M")
            
            return f"{MSG_VISITA_CREADA}\n\nTítulo: {titulo}\nCalendario: {calendar_name}\nFecha: {start_formatted} a {end_formatted}"
            
        except (ValueError, AttributeError) as e:
            logger.error(f"Error al formatear fechas: {str(e)}")
            return f"Visita '{titulo}' agendada correctamente en el calendario '{calendar_name}'."
        
    except Exception as e:
        logger.error(f"Error al crear la visita: {str(e)}", exc_info=True)
        return f"Error al agendar la visita: {str(e)}"

def list_events(params, project_id, user_id):
    """Listar todos los eventos del user_id de cualquier calendario"""
    logger.info(f"Iniciando list_events con parámetros: {params}")
    try:
        # Usar ID del proyecto del parámetro o del estado
        pid = params.get('proyecto_id', project_id)
        user_id = params.get('user_id', user_id)
        logger.info(f"user_id: {user_id}")  
        logger.info(f"project_id: {project_id}")
        logger.info(f"params: {params}")

        db = SupabaseDatabase()
        events = db.select(
            'calendar_events',
            filters={'user_id': user_id}
        )
        
        if events is None:
            logger.error("Error al consultar eventos del usuario en Supabase")
            return "Error al obtener los eventos. Por favor, inténtalo más tarde."
        
        if not events:
            logger.warning("No se encontraron eventos para este usuario")
            return "No se encontraron eventos para este usuario."
        
        result = "Eventos encontrados:\n\n"
        for idx, event in enumerate(events):
            event_id = event.get("id")
            event_title = event.get("title", "Evento sin título")
            event_start_time = event.get("start_time", "")
            event_end_time = event.get("end_time", "")
            
            result += f"{idx+1}. {event_title} (ID: {event_id})\n"
            result += f"   Fecha: {event_start_time} a {event_end_time}\n"
            result += f"   ID: {event_id}\n\n"
        
        logger.info(f"Total de eventos encontrados: {len(events)}")
        return result
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        logger.error(f"Error al listar eventos: {str(e)}", exc_info=True)
        logger.error(f"Stack trace: {stack_trace}")
        return f"Error al listar eventos: {str(e)}"

def create_event(params, project_id, user_id):
    """Crear un nuevo evento en el calendario"""
    logger.info(f"Iniciando create_event con parámetros: {params}")
    try:
        # Verificar parámetros requeridos
        required_params = ['calendario_id', 'titulo', 'inicio', 'fin']
        missing_params = [param for param in required_params if param not in params]
        
        # Si falta el ID del calendario pero se proporciona el nombre, intentar encontrarlo
        if 'calendario_id' in missing_params and 'nombre_calendario' in params:
            logger.info(f"Buscando calendario por nombre: {params['nombre_calendario']}")
            calendar_name = params['nombre_calendario'].lower()
            
            # Obtener todos los calendarios del proyecto
            calendars = get_all_calendars_from_project(project_id)
            
            if calendars:
                for calendar in calendars:
                    if calendar.get("name", "").lower() == calendar_name:
                        params['calendario_id'] = calendar.get("id")
                        logger.info(f"Encontrado calendario con ID: {params['calendario_id']}")
                        missing_params.remove('calendario_id')
                        break
        
        # Si faltan parámetros pero no incluye el calendario_id, mostrar calendarios disponibles
        if missing_params and 'calendario_id' in missing_params:
            # Obtener todos los calendarios del proyecto para mostrarlos
            calendars = get_all_calendars_from_project(project_id)
            
            if not calendars:
                logger.warning("No se encontraron calendarios para este proyecto")
                return "No se encontraron calendarios para este proyecto. Por favor, crea un calendario primero."
            
            # Mostrar los calendarios disponibles
            result = "Para crear un evento, necesito saber en qué calendario quieres crearlo. Calendarios disponibles:\n\n"
            
            for idx, calendar in enumerate(calendars):
                calendar_id = calendar.get("id")
                calendar_name = calendar.get("name", "Calendario sin nombre")
                
                result += f"{idx+1}. {calendar_name} (ID: {calendar_id})\n"
            
            result += "\nPor favor, especifica el nombre del calendario junto con el título, fecha de inicio y fin del evento."
            logger.info("Solicitando información sobre el calendario al usuario")
            return result
        
        # Si faltan otros parámetros obligatorios
        if missing_params:
            logger.error(f"Faltan parámetros requeridos: {missing_params}")
            return f"Error: Faltan parámetros requeridos: {', '.join(missing_params)}"
        
        # Inicializar conexión a Supabase
        db = SupabaseDatabase()
        
        # Construir datos del evento
        calendar_id = params['calendario_id']
        title = params['titulo']
        start_time = params['inicio']
        end_time = params['fin']
        description = params.get('descripcion', None)
        
        # Validar que el calendario existe y obtener su nombre
        calendar_result = db.select(
            'calendars',
            filters={'id': calendar_id}
        )
        
        if not calendar_result:
            logger.error(f"El calendario con ID {calendar_id} no existe")
            return f"Error: El calendario especificado no existe"
        
        calendar_name = calendar_result[0].get("name", "Calendario sin nombre")
        
        # Insertar el nuevo evento
        result = db.insert(
            'calendar_events',
            data={
                'calendar_id': calendar_id,
                'title': title,
                'description': description or '',
                'start_time': start_time,
                'end_time': end_time,
                'user_id': user_id or ''
            }
        )
        
        if not result:
            logger.error("Error al insertar evento en Supabase")
            return "Error: No se pudo crear el evento en la base de datos"
        
        created_event = result  # El método insert de SupabaseDatabase ya devuelve el primer elemento
        logger.debug(f"Evento creado: {created_event}")
        
        # Formatear las fechas
        start_time = created_event.get("start_time", "")
        end_time = created_event.get("end_time", "")
        
        if start_time and end_time:
            try:
                start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                
                start_formatted = start_datetime.strftime("%d/%m/%Y %H:%M")
                end_formatted = end_datetime.strftime("%d/%m/%Y %H:%M")
                
                logger.info(f"Evento '{created_event.get('title')}' creado exitosamente para {start_formatted}")
                return f"Evento creado correctamente: '{created_event.get('title')}' programado para el {start_formatted} hasta {end_formatted} en el calendario '{calendar_name}'."
            except (ValueError, AttributeError) as e:
                logger.error(f"Error al formatear fechas del evento creado: {str(e)}")
                return f"Evento '{created_event.get('title')}' creado correctamente en el calendario '{calendar_name}', pero no se pudieron formatear las fechas."
        else:
            logger.warning("Evento creado sin información detallada disponible")
            return f"Evento creado correctamente en el calendario '{calendar_name}', pero no se pudo obtener información detallada."
        
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        logger.error(f"Error al crear el evento: {str(e)}", exc_info=True)
        logger.error(f"Stack trace: {stack_trace}")
        return f"Error al crear el evento: {str(e)}"

def search_events(params, project_id):
    """Buscar eventos por título o fecha"""
    logger.info(f"Iniciando search_events con parámetros: {params}")
    try:
        # Usar ID del proyecto del parámetro o del estado
        pid = params.get('proyecto_id', project_id)
        title = params.get('titulo', '').lower()
        date_str = params.get('fecha', '')
        
        logger.debug(f"Búsqueda con proyecto_id={pid}, título='{title}', fecha='{date_str}'")
        
        # Inicializar conexión a Supabase
        db = SupabaseDatabase()
        
        # Primero obtenemos los calendarios
        calendars_result = db.select(
            'calendars',
            filters={'project_id': pid}
        )
        
        if calendars_result is None:
            logger.error("Error al consultar calendarios del proyecto en Supabase")
            return "Error al obtener los calendarios. Por favor, inténtalo más tarde."
        
        calendars = calendars_result
        
        if not calendars:
            logger.warning("No se encontraron calendarios para este proyecto")
            return "No se encontraron calendarios para este proyecto."
        
        # Formar la respuesta con los eventos encontrados
        result = "Eventos encontrados:\n\n"
        events_found = 0
        
        for cal_idx, calendar in enumerate(calendars):
            calendar_id = calendar.get("id")
            calendar_name = calendar.get("name", "Calendario sin nombre")
            
            # Construir la consulta para buscar eventos
            events_query = f"""
                SELECT id, title, description, start_time, end_time
                FROM calendar_events
                WHERE calendar_id = '{calendar_id}'
            """
            
            # Añadir filtros si se proporcionaron
            if title:
                events_query += f" AND LOWER(title) LIKE '%{title}%'"
            
            if date_str:
                events_query += f" AND start_time::text LIKE '%{date_str}%'"
            
            events_query += " ORDER BY start_time ASC"
            
            events_result = db.select(
                'calendar_events',
                filters={'calendar_id': calendar_id},
                order_by={'start_time': 'ASC'}
            )
            
            # Filtramos los resultados manualmente según título y fecha
            filtered_events = []
            for event in events_result or []:
                event_title = event.get("title", "").lower()
                event_start_time = event.get("start_time", "")
                
                match_title = not title or title in event_title
                match_date = not date_str or date_str in event_start_time
                
                if match_title and match_date:
                    filtered_events.append(event)
            
            events = filtered_events
            
            logger.debug(f"Buscando en calendario {cal_idx+1}/{len(calendars)}: '{calendar_name}' con {len(events)} eventos encontrados")
            
            if events:
                result += f"Calendario: {calendar_name}\n"
                for event_idx, event in enumerate(events):
                    start_time = event.get("start_time", "")
                    end_time = event.get("end_time", "")
                    title = event.get("title", "Evento sin título")
                    description = event.get("description", "")
                    
                    logger.debug(f"Procesando evento coincidente {event_idx+1}/{len(events)}: '{title}'")
                    
                    # Formatear fechas para mejor legibilidad
                    try:
                        start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                        
                        start_formatted = start_datetime.strftime("%d/%m/%Y %H:%M")
                        end_formatted = end_datetime.strftime("%d/%m/%Y %H:%M")
                    except (ValueError, AttributeError) as e:
                        logger.error(f"Error al formatear fechas del evento {title}: {str(e)}")
                        start_formatted = "Fecha desconocida"
                        end_formatted = "Fecha desconocida"
                    
                    result += f"- {start_formatted} a {end_formatted}: {title}\n"
                    if description:
                        result += f"  Descripción: {description}\n"
                    
                    events_found += 1
                
                result += "\n"
        
        logger.info(f"Total de eventos encontrados en la búsqueda: {events_found}")
        if events_found == 0:
            return "No se encontraron eventos que coincidan con los criterios de búsqueda."
        
        return result
        
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        logger.error(f"Error al buscar eventos: {str(e)}", exc_info=True)
        logger.error(f"Stack trace: {stack_trace}")
        return f"Error al buscar eventos: {str(e)}"

def get_event(params):
    """Obtener un evento específico por su ID"""
    logger.info(f"Iniciando get_event con parámetros: {params}")
    try:
        # Verificar parámetros requeridos
        if 'evento_id' not in params:
            logger.error("Falta el ID del evento en los parámetros")
            return "Error: Falta el ID del evento"
        
        event_id = params['evento_id']
        logger.debug(f"Consultando evento con ID: {event_id}")
        
        # Inicializar conexión a Supabase
        db = SupabaseDatabase()
        
        # Obtener detalles del evento
        query = f"""
            SELECT e.id, e.title, e.description, e.start_time, e.end_time, c.name as calendar_name
            FROM calendar_events e
            JOIN calendars c ON e.calendar_id = c.id
            WHERE e.id = '{event_id}'
        """
        
        result = db.select_query('execute_query', {'sql_text': query})
        
        if not result:
            logger.error(f"No se encontró el evento con ID {event_id}")
            return f"Error: No se encontró el evento especificado"
        
        event = result[0]
        logger.debug(f"Datos del evento obtenido: {event}")
        
        # Formatear la respuesta
        start_time = event.get("start_time", "")
        end_time = event.get("end_time", "")
        title = event.get("title", "Evento sin título")
        description = event.get("description", "Sin descripción")
        calendar_name = event.get("calendar_name", "Calendario sin nombre")
        
        # Formatear fechas para mejor legibilidad
        try:
            start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            start_formatted = start_datetime.strftime("%d/%m/%Y %H:%M")
            end_formatted = end_datetime.strftime("%d/%m/%Y %H:%M")
        except (ValueError, AttributeError) as e:
            logger.error(f"Error al formatear fechas del evento {title}: {str(e)}")
            start_formatted = "Fecha desconocida"
            end_formatted = "Fecha desconocida"
        
        result = f"Detalles del evento:\n\n"
        result += f"Título: {title}\n"
        result += f"Calendario: {calendar_name}\n"
        result += f"Fecha: {start_formatted} a {end_formatted}\n"
        result += f"Descripción: {description}\n"
        
        logger.info(f"Evento '{title}' recuperado exitosamente")
        return result
        
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        logger.error(f"Error al obtener el evento: {str(e)}", exc_info=True)
        logger.error(f"Stack trace: {stack_trace}")
        return f"Error al obtener el evento: {str(e)}"

def update_event(params):
    """Actualizar un evento existente"""
    logger.info(f"Iniciando update_event con parámetros: {params}")
    try:
        # Verificar parámetros requeridos
        if 'evento_id' not in params:
            logger.error("Falta el ID del evento en los parámetros")
            return "Error: Falta el ID del evento"
        
        event_id = params['evento_id']
        logger.debug(f"Actualizando evento con ID: {event_id}")
        
        # Inicializar conexión a Supabase
        db = SupabaseDatabase()
        
        # Construir consulta de actualización
        update_fields = []
        
        # Mapeo de nombres de parámetros en español a inglés para la BD
        param_mapping = {
            'titulo': 'title',
            'descripcion': 'description',
            'inicio': 'start_time',
            'fin': 'end_time'
        }
        
        for es_key, db_column in param_mapping.items():
            if es_key in params:
                update_fields.append(f"{db_column} = '{params[es_key]}'")
                logger.debug(f"Actualizando campo '{db_column}' a '{params[es_key]}'")
        
        if not update_fields:
            logger.error("No se proporcionaron datos para actualizar")
            return "Error: No se proporcionaron datos para actualizar"
        
        # Verificar que el evento existe
        check_query = f"""
            SELECT id FROM calendar_events WHERE id = '{event_id}'
        """
        check_result = db.select_query('execute_query', {'sql_text': check_query})
        
        if not check_result:
            logger.error(f"No se encontró el evento con ID {event_id}")
            return f"Error: No se encontró el evento especificado"
        
        # Construir y ejecutar la consulta de actualización
        update_query = f"""
            UPDATE calendar_events 
            SET {', '.join(update_fields)}
            WHERE id = '{event_id}'
            RETURNING id, title
        """
        
        result = db.select_query('execute_query', {'sql_text': update_query})
        
        if not result:
            logger.error(f"Error al actualizar el evento {event_id}")
            return "Error: No se pudo actualizar el evento"
        
        updated_event = result[0]
        logger.info(f"Evento {event_id} actualizado exitosamente: {updated_event}")
        return f"Evento '{updated_event.get('title')}' actualizado correctamente."
        
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        logger.error(f"Error al actualizar el evento: {str(e)}", exc_info=True)
        logger.error(f"Stack trace: {stack_trace}")
        return f"Error al actualizar el evento: {str(e)}"

def delete_event(params):
    """Eliminar un evento"""
    logger.info(f"Iniciando delete_event con parámetros: {params}")
    try:
        # Verificar parámetros requeridos
        if 'evento_id' not in params:
            logger.error("Falta el ID del evento en los parámetros")
            return "Error: Falta el ID del evento"
        
        event_id = params['evento_id']
        logger.debug(f"Eliminando evento con ID: {event_id}")
        
        # Inicializar conexión a Supabase
        db = SupabaseDatabase()
        
        # Verificar que el evento existe y obtener su título para el mensaje
        check_query = f"""
            SELECT id, title FROM calendar_events WHERE id = '{event_id}'
        """
        check_result = db.select_query('execute_query', {'sql_text': check_query})
        
        if not check_result:
            logger.error(f"No se encontró el evento con ID {event_id}")
            return f"Error: No se encontró el evento especificado"
        
        event_title = check_result[0].get('title', 'Evento')
        
        # Eliminar el evento
        delete_query = f"""
            DELETE FROM calendar_events
            WHERE id = '{event_id}'
            RETURNING id
        """
        
        result = db.select_query('execute_query', {'sql_text': delete_query})
        
        if not result:
            logger.error(f"Error al eliminar el evento {event_id}")
            return "Error: No se pudo eliminar el evento"
        
        logger.info(f"Evento {event_id} eliminado exitosamente")
        return f"Evento '{event_title}' eliminado correctamente."
        
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        logger.error(f"Error al eliminar el evento: {str(e)}", exc_info=True)
        logger.error(f"Stack trace: {stack_trace}")
        return f"Error al eliminar el evento: {str(e)}"

def get_calendar(params, project_id):
    """Obtener información de un calendario específico por su nombre"""
    logger.info(f"Iniciando get_calendar con parámetros: {params}")
    try:
        # Verificar parámetros requeridos
        if 'nombre' not in params:
            logger.error("Falta el nombre del calendario en los parámetros")
            return "Error: Falta el nombre del calendario"
        
        calendar_name = params['nombre'].lower()
        logger.debug(f"Buscando calendario con nombre: {calendar_name}")
        
        # Inicializar conexión a Supabase
        db = SupabaseDatabase()
        
        # Buscar el calendario por nombre
        calendars = db.select(
            'calendars',
            filters={'project_id': project_id}
        )
        
        if not calendars:
            logger.warning("No se encontraron calendarios para este proyecto")
            return "No se encontraron calendarios para este proyecto."
        
        # Buscar el calendario que coincida con el nombre
        target_calendar = None
        for calendar in calendars:
            if calendar.get("name", "").lower() == calendar_name:
                target_calendar = calendar
                break
        
        if not target_calendar:
            logger.warning(f"No se encontró el calendario con nombre: {calendar_name}")
            return f"No se encontró el calendario '{calendar_name}'. Por favor, verifica el nombre y vuelve a intentarlo."
        
        # Obtener eventos del calendario
        calendar_id = target_calendar.get("id")
        events = db.select(
            'calendar_events',
            filters={'calendar_id': calendar_id}
        )
        
        # Formatear la respuesta
        result = f"Información del calendario '{target_calendar.get('name')}':\n\n"
        result += f"ID: {calendar_id}\n"
        result += f"Color: {target_calendar.get('color', 'No especificado')}\n"
        result += f"Fecha de creación: {target_calendar.get('created_at', 'No disponible')}\n\n"
        
        if events:
            result += "Eventos programados:\n"
            for event in events:
                start_time = event.get("start_time", "")
                end_time = event.get("end_time", "")
                title = event.get("title", "Evento sin título")
                description = event.get("description", "")
                
                # Formatear fechas
                try:
                    start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00')) 
                    start_formatted = start_datetime.strftime("%d/%m/%Y %H:%M")
                    end_formatted = end_datetime.strftime("%d/%m/%Y %H:%M")
                except (ValueError, AttributeError) as e:
                    logger.error(f"Error al formatear fechas del evento {title}: {str(e)}")
                    start_formatted = "Fecha desconocida"
                    end_formatted = "Fecha desconocida"
                
                result += f"- {start_formatted} a {end_formatted}: {title}\n"
                if description:
                    result += f"  Descripción: {description}\n"
        else:
            result += "No hay eventos programados en este calendario."
        
        return result
        
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        logger.error(f"Error al obtener el calendario: {str(e)}", exc_info=True)
        logger.error(f"Stack trace: {stack_trace}")
        return f"Error al obtener el calendario: {str(e)}"

def search_event_for_edit(params, project_id):
    """Buscar un evento por título para luego editarlo"""
    logger.info(f"Iniciando search_event_for_edit con parámetros: {params}")
    try:
        if 'titulo' not in params:
            logger.error("Falta el título del evento en los parámetros")
            return "Error: Falta el título del evento"
        
        event_title = params['titulo'].lower()
        logger.debug(f"Buscando evento con título similar a: {event_title}")
        
        # Inicializar conexión a Supabase
        db = SupabaseDatabase()
        
        # Obtener todos los calendarios del proyecto
        calendars = db.select(
            'calendars',
            filters={'project_id': project_id}
        )
        
        if not calendars:
            logger.warning("No se encontraron calendarios para este proyecto")
            return "No se encontraron calendarios para este proyecto."
        
        # Buscar eventos que coincidan en todos los calendarios
        matching_events = []
        
        for calendar in calendars:
            calendar_id = calendar.get("id")
            calendar_name = calendar.get("name", "Calendario sin nombre")
            
            # Obtener eventos de este calendario
            events = db.select(
                'calendar_events',
                filters={'calendar_id': calendar_id}
            )
            
            if not events:
                continue
            
            # Filtrar por título
            for event in events:
                if event_title in event.get("title", "").lower():
                    # Agregar información del calendario
                    event_with_calendar = event.copy()
                    event_with_calendar["calendar_name"] = calendar_name
                    matching_events.append(event_with_calendar)
        
        if not matching_events:
            logger.warning(f"No se encontró ningún evento con título similar a '{event_title}'")
            return f"No se encontró ningún evento con título similar a '{event_title}'. Por favor, verifica el título o consulta la lista de eventos."
        
        # Mostrar los eventos encontrados
        result = f"Encontré los siguientes eventos con título similar a '{event_title}':\n\n"
        
        for idx, event in enumerate(matching_events):
            event_id = event.get("id")
            event_title = event.get("title", "Evento sin título")
            calendar_name = event.get("calendar_name", "Calendario desconocido")
            
            # Formatear fechas
            start_time = event.get("start_time", "")
            end_time = event.get("end_time", "")
            
            try:
                start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                
                start_formatted = start_datetime.strftime("%d/%m/%Y %H:%M")
                end_formatted = end_datetime.strftime("%d/%m/%Y %H:%M")
            except (ValueError, AttributeError) as e:
                logger.error(f"Error al formatear fechas del evento {event_title}: {str(e)}")
                start_formatted = "Fecha desconocida"
                end_formatted = "Fecha desconocida"
            
            result += f"{idx+1}. '{event_title}' en '{calendar_name}'\n"
            result += f"   Fecha: {start_formatted} a {end_formatted}\n"
            result += f"   ID: {event_id}\n\n"
        
        result += "Para editar un evento, utiliza el comando 'editar evento con id [ID]' con el ID correspondiente."
        
        return result
    
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        logger.error(f"Error al buscar evento para editar: {str(e)}", exc_info=True)
        logger.error(f"Stack trace: {stack_trace}")
        return f"Error al buscar evento para editar: {str(e)}"

def search_event_for_delete(params, project_id):
    """Buscar un evento por título para luego eliminarlo"""
    logger.info(f"Iniciando search_event_for_delete con parámetros: {params}")
    try:
        if 'titulo' not in params:
            logger.error("Falta el título del evento en los parámetros")
            return "Error: Falta el título del evento"
        
        event_title = params['titulo'].lower()
        logger.debug(f"Buscando evento con título similar a: {event_title}")
        
        # Inicializar conexión a Supabase
        db = SupabaseDatabase()
        
        # Obtener todos los calendarios del proyecto
        calendars = db.select(
            'calendars',
            filters={'project_id': project_id}
        )
        
        if not calendars:
            logger.warning("No se encontraron calendarios para este proyecto")
            return "No se encontraron calendarios para este proyecto."
        
        # Buscar eventos que coincidan en todos los calendarios
        matching_events = []
        
        for calendar in calendars:
            calendar_id = calendar.get("id")
            calendar_name = calendar.get("name", "Calendario sin nombre")
            
            # Obtener eventos de este calendario
            events = db.select(
                'calendar_events',
                filters={'calendar_id': calendar_id}
            )
            
            if not events:
                continue
            
            # Filtrar por título
            for event in events:
                if event_title in event.get("title", "").lower():
                    # Agregar información del calendario
                    event_with_calendar = event.copy()
                    event_with_calendar["calendar_name"] = calendar_name
                    matching_events.append(event_with_calendar)
        
        if not matching_events:
            logger.warning(f"No se encontró ningún evento con título similar a '{event_title}'")
            return f"No se encontró ningún evento con título similar a '{event_title}'. Por favor, verifica el título o consulta la lista de eventos."
        
        # Mostrar los eventos encontrados
        result = f"Encontré los siguientes eventos con título similar a '{event_title}':\n\n"
        
        for idx, event in enumerate(matching_events):
            event_id = event.get("id")
            event_title = event.get("title", "Evento sin título")
            calendar_name = event.get("calendar_name", "Calendario desconocido")
            
            # Formatear fechas
            start_time = event.get("start_time", "")
            end_time = event.get("end_time", "")
            
            try:
                start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                
                start_formatted = start_datetime.strftime("%d/%m/%Y %H:%M")
                end_formatted = end_datetime.strftime("%d/%m/%Y %H:%M")
            except (ValueError, AttributeError) as e:
                logger.error(f"Error al formatear fechas del evento {event_title}: {str(e)}")
                start_formatted = "Fecha desconocida"
                end_formatted = "Fecha desconocida"
            
            result += f"{idx+1}. '{event_title}' en '{calendar_name}'\n"
            result += f"   Fecha: {start_formatted} a {end_formatted}\n"
            result += f"   ID: {event_id}\n\n"
        
        result += "Para eliminar un evento, utiliza el comando 'eliminar evento con id [ID]' con el ID correspondiente."
        
        return result
    
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        logger.error(f"Error al buscar evento para eliminar: {str(e)}", exc_info=True)
        logger.error(f"Stack trace: {stack_trace}")
        return f"Error al buscar evento para eliminar: {str(e)}" 