# 🚀 LÓGICA GRANULAR DE HORARIOS - CÓDIGO PYTHON
# Ejemplo de implementación para agenda_tool.py

from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Any, Tuple

def parse_granular_schedule(workflow_settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae y valida la configuración granular de horarios desde workflow_settings
    
    Returns:
        Dict con configuración validada de horarios por día
    """
    agenda_settings = workflow_settings.get("AGENDA_COMPLETA", {})
    schedule = agenda_settings.get("schedule", {})
    
    # Configuración por defecto si no existe schedule granular
    if not schedule:
        return {
            "monday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
            "tuesday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
            "wednesday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
            "thursday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
            "friday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
            "saturday": {"enabled": False, "time_slots": []},
            "sunday": {"enabled": False, "time_slots": []}
        }
    
    return schedule

def is_day_enabled(schedule: Dict[str, Any], day_name: str) -> bool:
    """
    Verifica si un día específico está habilitado
    
    Args:
        schedule: Configuración granular de horarios
        day_name: Nombre del día (monday, tuesday, etc.)
    
    Returns:
        True si el día está habilitado
    """
    day_config = schedule.get(day_name, {})
    return day_config.get("enabled", False)

def get_time_slots_for_day(schedule: Dict[str, Any], day_name: str) -> List[Dict[str, str]]:
    """
    Obtiene las franjas horarias para un día específico
    
    Args:
        schedule: Configuración granular de horarios
        day_name: Nombre del día (monday, tuesday, etc.)
    
    Returns:
        Lista de franjas horarias [{"start": "09:00", "end": "12:00", "description": "Mañana"}]
    """
    if not is_day_enabled(schedule, day_name):
        return []
    
    day_config = schedule.get(day_name, {})
    return day_config.get("time_slots", [])

def is_time_in_working_hours(schedule: Dict[str, Any], target_datetime: datetime) -> Tuple[bool, str]:
    """
    Verifica si una fecha/hora específica está dentro de horarios laborales
    
    Args:
        schedule: Configuración granular de horarios
        target_datetime: Fecha/hora a verificar
    
    Returns:
        Tupla (es_valido, mensaje)
    """
    # Mapeo de weekday() a nombre de día
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_name = day_names[target_datetime.weekday()]
    
    # Verificar si el día está habilitado
    if not is_day_enabled(schedule, day_name):
        days_available = [day for day in day_names if is_day_enabled(schedule, day)]
        return False, f"❌ No trabajo los {day_name}s. Días disponibles: {', '.join(days_available)}"
    
    # Obtener franjas horarias del día
    time_slots = get_time_slots_for_day(schedule, day_name)
    if not time_slots:
        return False, f"❌ No hay franjas horarias configuradas para {day_name}"
    
    # Convertir hora objetivo a formato HH:MM
    target_time = target_datetime.strftime("%H:%M")
    
    # Verificar si está dentro de alguna franja horaria
    for slot in time_slots:
        start_time = slot.get("start", "00:00")
        end_time = slot.get("end", "23:59")
        
        if start_time <= target_time < end_time:
            description = slot.get("description", "Horario laboral")
            return True, f"✅ Horario válido en franja '{description}' ({start_time}-{end_time})"
    
    # No está en ninguna franja
    slot_descriptions = [f"{slot['start']}-{slot['end']} ({slot.get('description', 'Sin descripción')})" 
                        for slot in time_slots]
    return False, f"❌ Horario fuera de franjas laborales. Disponible: {', '.join(slot_descriptions)}"

def find_available_slots_granular(schedule: Dict[str, Any], duration_minutes: int = 60, 
                                buffer_minutes: int = 15, max_slots: int = 3) -> List[Dict[str, Any]]:
    """
    Encuentra horarios disponibles basado en configuración granular
    
    Args:
        schedule: Configuración granular de horarios
        duration_minutes: Duración de la cita en minutos
        buffer_minutes: Buffer entre citas
        max_slots: Máximo número de slots a retornar
    
    Returns:
        Lista de slots disponibles
    """
    chile_tz = pytz.timezone("America/Santiago")
    now = datetime.now(chile_tz)
    available_slots = []
    
    # Mapeo de nombres de días
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    days_esp = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
    
    # Buscar en los próximos 14 días
    for day_offset in range(14):
        if len(available_slots) >= max_slots:
            break
            
        current_date = now.date() + timedelta(days=day_offset)
        day_name = day_names[current_date.weekday()]
        
        # Verificar si el día está habilitado
        if not is_day_enabled(schedule, day_name):
            continue
        
        # Obtener franjas horarias del día
        time_slots = get_time_slots_for_day(schedule, day_name)
        
        # Buscar horarios disponibles en cada franja
        for slot in time_slots:
            start_time_str = slot.get("start", "09:00")
            end_time_str = slot.get("end", "18:00")
            description = slot.get("description", "Horario laboral")
            
            # Convertir a datetime
            start_hour, start_minute = map(int, start_time_str.split(':'))
            end_hour, end_minute = map(int, end_time_str.split(':'))
            
            # Crear slots cada hora dentro de la franja
            current_slot_time = datetime.combine(current_date, datetime.min.time().replace(hour=start_hour, minute=start_minute))
            current_slot_time = chile_tz.localize(current_slot_time)
            end_slot_time = datetime.combine(current_date, datetime.min.time().replace(hour=end_hour, minute=end_minute))
            end_slot_time = chile_tz.localize(end_slot_time)
            
            while current_slot_time + timedelta(minutes=duration_minutes) <= end_slot_time:
                # Si es hoy, no mostrar horarios que ya pasaron
                if day_offset == 0 and current_slot_time <= now:
                    current_slot_time += timedelta(minutes=duration_minutes + buffer_minutes)
                    continue
                
                # Aquí se haría la verificación contra Google Calendar
                # Por ahora asumimos que está disponible
                
                slot_end = current_slot_time + timedelta(minutes=duration_minutes)
                day_esp = days_esp[current_date.weekday()]
                
                available_slots.append({
                    'start': current_slot_time,
                    'end': slot_end,
                    'date_str': f"{day_esp} {current_date.day} de {current_date.strftime('%B')}",
                    'time_str': f"{current_slot_time.strftime('%H:%M')} - {slot_end.strftime('%H:%M')}",
                    'slot_description': description
                })
                
                if len(available_slots) >= max_slots:
                    break
                
                current_slot_time += timedelta(minutes=duration_minutes + buffer_minutes)
            
            if len(available_slots) >= max_slots:
                break
    
    return available_slots

def validate_specific_day_request(schedule: Dict[str, Any], day_requested: str) -> Tuple[bool, str]:
    """
    Valida si un día específico solicitado está disponible
    
    Args:
        schedule: Configuración granular de horarios
        day_requested: Día solicitado en español (lunes, martes, etc.)
    
    Returns:
        Tupla (es_valido, mensaje)
    """
    # Mapeo de días en español a inglés
    day_mapping = {
        'lunes': 'monday',
        'martes': 'tuesday', 
        'miércoles': 'wednesday',
        'miercoles': 'wednesday',  # Sin acento también
        'jueves': 'thursday',
        'viernes': 'friday',
        'sábado': 'saturday',
        'sabado': 'saturday',  # Sin acento también
        'domingo': 'sunday'
    }
    
    day_english = day_mapping.get(day_requested.lower())
    if not day_english:
        return False, f"❌ Día no reconocido: {day_requested}"
    
    if not is_day_enabled(schedule, day_english):
        # Obtener días disponibles
        available_days = []
        for esp_day, eng_day in day_mapping.items():
            if is_day_enabled(schedule, eng_day):
                available_days.append(esp_day)
        
        return False, f"❌ No trabajo los {day_requested}s. Días disponibles: {', '.join(available_days)}"
    
    # Obtener información de horarios para el día
    time_slots = get_time_slots_for_day(schedule, day_english)
    slot_info = []
    for slot in time_slots:
        slot_desc = f"{slot['start']}-{slot['end']}"
        if slot.get('description'):
            slot_desc += f" ({slot['description']})"
        slot_info.append(slot_desc)
    
    return True, f"✅ {day_requested.capitalize()} disponible. Horarios: {', '.join(slot_info)}"

# EJEMPLO DE USO:
def ejemplo_uso():
    """Ejemplo de cómo usar las funciones granulares"""
    
    # Configuración granular de ejemplo
    workflow_settings = {
        "AGENDA_COMPLETA": {
            "default_duration_minutes": 60,
            "buffer_minutes": 15,
            "schedule": {
                "monday": {
                    "enabled": True,
                    "time_slots": [
                        {"start": "09:00", "end": "12:30", "description": "Mañana"},
                        {"start": "13:30", "end": "18:00", "description": "Tarde"}
                    ]
                },
                "tuesday": {
                    "enabled": True,
                    "time_slots": [
                        {"start": "09:00", "end": "17:00", "description": "Jornada continua"}
                    ]
                },
                "wednesday": {
                    "enabled": False,
                    "time_slots": []
                },
                "thursday": {
                    "enabled": True,
                    "time_slots": [
                        {"start": "08:00", "end": "12:00", "description": "Solo mañana"}
                    ]
                },
                "friday": {
                    "enabled": True,
                    "time_slots": [
                        {"start": "09:00", "end": "16:00", "description": "Viernes corto"}
                    ]
                },
                "saturday": {"enabled": False, "time_slots": []},
                "sunday": {"enabled": False, "time_slots": []}
            }
        }
    }
    
    # Parsear configuración
    schedule = parse_granular_schedule(workflow_settings)
    print("📋 Configuración granular cargada")
    
    # Verificar días específicos
    print("\n🔍 Verificaciones de días:")
    print(validate_specific_day_request(schedule, "lunes"))
    print(validate_specific_day_request(schedule, "miércoles"))
    print(validate_specific_day_request(schedule, "sábado"))
    
    # Verificar horarios específicos
    print("\n⏰ Verificaciones de horarios:")
    chile_tz = pytz.timezone("America/Santiago")
    
    # Lunes 10:00 (debe estar disponible - franja mañana)
    test_time1 = chile_tz.localize(datetime(2024, 1, 15, 10, 0))  # Lunes
    print(is_time_in_working_hours(schedule, test_time1))
    
    # Lunes 13:00 (no debe estar disponible - entre franjas)
    test_time2 = chile_tz.localize(datetime(2024, 1, 15, 13, 0))  # Lunes
    print(is_time_in_working_hours(schedule, test_time2))
    
    # Miércoles 10:00 (no debe estar disponible - día deshabilitado)
    test_time3 = chile_tz.localize(datetime(2024, 1, 17, 10, 0))  # Miércoles
    print(is_time_in_working_hours(schedule, test_time3))
    
    # Buscar slots disponibles
    print("\n📅 Slots disponibles:")
    slots = find_available_slots_granular(schedule, duration_minutes=60, max_slots=5)
    for i, slot in enumerate(slots, 1):
        print(f"{i}. {slot['date_str']} - {slot['time_str']} ({slot['slot_description']})")

if __name__ == "__main__":
    ejemplo_uso()

# 📝 INTEGRACIÓN CON AGENDA_TOOL.PY:
"""
Para integrar este código en tu agenda_tool.py:

1. Agregar estas funciones a la clase AgendaTool
2. Modificar _busqueda_horarios_workflow() para usar find_available_slots_granular()
3. Modificar _generate_calendar_query() para usar is_time_in_working_hours()
4. Agregar validaciones en _agenda_completa_workflow()

Ejemplo de modificación en _busqueda_horarios_workflow():

async def _busqueda_horarios_workflow(self, title: str = None, start_datetime: str = None, end_datetime: str = None) -> str:
    # Obtener configuración granular
    schedule = parse_granular_schedule(self._cached_project_config.get("workflow_settings", {}))
    
    # Si se solicita un día específico
    if title and any(day in title.lower() for day in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']):
        day_requested = next(day for day in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'] if day in title.lower())
        is_valid, message = validate_specific_day_request(schedule, day_requested)
        if not is_valid:
            return message
    
    # Obtener configuración de duración y buffer
    agenda_settings = self._cached_project_config.get("workflow_settings", {}).get("AGENDA_COMPLETA", {})
    duration_minutes = agenda_settings.get("default_duration_minutes", 60)
    buffer_minutes = agenda_settings.get("buffer_minutes", 15)
    
    # Buscar slots usando configuración granular
    slots = find_available_slots_granular(schedule, duration_minutes, buffer_minutes, max_slots=3)
    
    # Formatear respuesta...
""" 