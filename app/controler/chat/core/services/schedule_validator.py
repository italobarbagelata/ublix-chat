"""
📅 SERVICIO DE VALIDACIÓN DE HORARIOS PARA SISTEMA DE CITAS

Extrae y centraliza toda la lógica de validación de horarios granulares
de agenda_tool.py manteniendo todas las configuraciones existentes.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import pytz

logger = logging.getLogger(__name__)

class ScheduleValidator:
    """Servicio especializado para validación de horarios granulares"""
    
    def __init__(self, cached_project_config: Dict[str, Any] = None):
        self.cached_project_config = cached_project_config
    
    def parse_granular_schedule(self, workflow_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae y valida la configuración granular de horarios desde workflow_settings"""
        agenda_settings = workflow_settings.get("AGENDA_COMPLETA", {})
        schedule = agenda_settings.get("schedule", {})
        
        # Configuración por defecto si no existe schedule granular
        if not schedule:
            logger.info("📋 No hay configuración granular, usando horarios estándar")
            return {
                "monday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "tuesday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "wednesday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "thursday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "friday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "saturday": {"enabled": False, "time_slots": []},
                "sunday": {"enabled": False, "time_slots": []}
            }
        
        logger.info("✅ Configuración granular de horarios cargada exitosamente")
        return schedule
    
    def is_day_enabled(self, schedule: Dict[str, Any], day_name: str) -> bool:
        """Verifica si un día específico está habilitado"""
        day_config = schedule.get(day_name, {})
        return day_config.get("enabled", False)
    
    def get_time_slots_for_day(self, schedule: Dict[str, Any], day_name: str) -> List[Dict[str, str]]:
        """Obtiene las franjas horarias para un día específico"""
        if not self.is_day_enabled(schedule, day_name):
            return []
        
        day_config = schedule.get(day_name, {})
        return day_config.get("time_slots", [])
    
    def is_time_in_working_hours(self, schedule: Dict[str, Any], target_datetime: datetime) -> Tuple[bool, str]:
        """Verifica si una fecha/hora específica está dentro de horarios laborales"""
        # Mapeo de weekday() a nombre de día
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        day_name = day_names[target_datetime.weekday()]
        
        # Verificar si el día está habilitado
        if not self.is_day_enabled(schedule, day_name):
            days_available = [day for day in day_names if self.is_day_enabled(schedule, day)]
            return False, f"❌ No trabajo los {day_name}s. Días disponibles: {', '.join(days_available)}"
        
        # Obtener franjas horarias del día
        time_slots = self.get_time_slots_for_day(schedule, day_name)
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
    
    def validate_specific_day_request(self, schedule: Dict[str, Any], day_requested: str) -> Tuple[bool, str]:
        """Valida si un día específico solicitado está disponible"""
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
        
        if not self.is_day_enabled(schedule, day_english):
            # Obtener días disponibles
            available_days = []
            for esp_day, eng_day in day_mapping.items():
                if self.is_day_enabled(schedule, eng_day):
                    available_days.append(esp_day)
            
            return False, f"❌ No trabajo los {day_requested}s. Días disponibles: {', '.join(set(available_days))}"
        
        # Obtener información de horarios para el día
        time_slots = self.get_time_slots_for_day(schedule, day_english)
        slot_info = []
        for slot in time_slots:
            slot_desc = f"{slot['start']}-{slot['end']}"
            if slot.get('description'):
                slot_desc += f" ({slot['description']})"
            slot_info.append(slot_desc)
        
        return True, f"✅ {day_requested.capitalize()} disponible. Horarios: {', '.join(slot_info)}"
    
    def get_available_schedule_summary(self, schedule: Dict[str, Any]) -> str:
        """Genera un resumen de los horarios disponibles"""
        # Mapeo de días en inglés a español
        day_translation = {
            'monday': 'Lunes',
            'tuesday': 'Martes',
            'wednesday': 'Miércoles', 
            'thursday': 'Jueves',
            'friday': 'Viernes',
            'saturday': 'Sábado',
            'sunday': 'Domingo'
        }
        
        schedule_summary = []
        
        for eng_day, config in schedule.items():
            if config.get("enabled", False):
                day_spanish = day_translation.get(eng_day, eng_day.capitalize())
                time_slots = config.get("time_slots", [])
                
                if time_slots:
                    slot_descriptions = []
                    for slot in time_slots:
                        slot_text = f"{slot['start']}-{slot['end']}"
                        if slot.get('description'):
                            slot_text += f" ({slot['description']})"
                        slot_descriptions.append(slot_text)
                    
                    schedule_summary.append(f"• **{day_spanish}:** {', '.join(slot_descriptions)}")
        
        if not schedule_summary:
            return "No hay horarios configurados"
        
        return '\n'.join(schedule_summary)
    
    def extract_day_from_text(self, text: str) -> Optional[str]:
        """Extrae el nombre del día del texto en español - versión mejorada para fechas complejas"""
        if not text:
            return None
            
        text_lower = text.lower()
        
        # Palabras que indican días específicos
        day_keywords = {
            'lunes': 'lunes',
            'martes': 'martes',
            'miércoles': 'miércoles',
            'miercoles': 'miércoles',  # Sin acento
            'jueves': 'jueves',
            'viernes': 'viernes',
            'sábado': 'sábado',
            'sabado': 'sábado',  # Sin acento
            'domingo': 'domingo'
        }
        
        # 1. "Próximo [día]" - ej: "próximo miércoles"
        for keyword, day_name in day_keywords.items():
            if f"próximo {keyword}" in text_lower or f"proximo {keyword}" in text_lower:
                logger.info(f"🎯 Detectado 'próximo {day_name}' en: '{text}'")
                return day_name
        
        # 2. "El próximo [día]" - ej: "el próximo miércoles"  
        for keyword, day_name in day_keywords.items():
            if f"el próximo {keyword}" in text_lower or f"el proximo {keyword}" in text_lower:
                logger.info(f"🎯 Detectado 'el próximo {day_name}' en: '{text}'")
                return day_name
        
        # 3. "Para el [día]" - ej: "para el miércoles"
        for keyword, day_name in day_keywords.items():
            if f"para el {keyword}" in text_lower:
                logger.info(f"🎯 Detectado 'para el {day_name}' en: '{text}'")
                return day_name
        
        # 4. "El [día]" - ej: "el miércoles"
        for keyword, day_name in day_keywords.items():
            if f"el {keyword}" in text_lower:
                logger.info(f"🎯 Detectado 'el {day_name}' en: '{text}'")
                return day_name
        
        # 5. Días simples - comportamiento original
        for keyword, day_name in day_keywords.items():
            if keyword in text_lower:
                logger.info(f"🎯 Detectado día simple '{day_name}' en: '{text}'")
                return day_name
        
        return None
    
    def validate_date_consistency(self, text: str) -> Tuple[bool, str, Optional[str]]:
        """
        Valida la consistencia entre día de la semana mencionado y fecha específica
        
        Args:
            text: Texto del usuario que puede contener día y fecha
            
        Returns:
            Tupla (es_consistente, mensaje_validacion, fecha_corregida)
        """
        try:
            if not text:
                return True, "", None
                
            text_lower = text.lower()
            logger.info(f"🔍 VALIDANDO CONSISTENCIA DE FECHA: '{text}'")
            
            # Mapeo de días en español
            dias_map = {
                'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2,
                'jueves': 3, 'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6
            }
            
            # Mapeo de meses en español
            meses_map = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
            }
            
            # Detectar si hay un día de la semana mencionado
            dia_mencionado = None
            dia_weekday = None
            for dia, weekday in dias_map.items():
                if dia in text_lower:
                    dia_mencionado = dia
                    dia_weekday = weekday
                    break
            
            # Detectar si hay una fecha específica mencionada
            fecha_pattern = r'(\d{1,2})\s+de\s+([a-záéíóúñ]+)(?:\s+de\s+(\d{4}))?'
            fecha_match = re.search(fecha_pattern, text_lower)
            
            if dia_mencionado and fecha_match:
                # Extraer componentes de la fecha
                dia_numero = int(fecha_match.group(1))
                mes_nombre = fecha_match.group(2)
                año = int(fecha_match.group(3)) if fecha_match.group(3) else datetime.now().year
                
                if mes_nombre not in meses_map:
                    return False, f"❌ Mes no reconocido: {mes_nombre}", None
                
                mes_numero = meses_map[mes_nombre]
                
                try:
                    fecha_especifica = datetime(año, mes_numero, dia_numero)
                    fecha_weekday = fecha_especifica.weekday()
                    
                    if dia_weekday == fecha_weekday:
                        return True, f"✅ Fecha válida", fecha_especifica.strftime('%Y-%m-%d')
                    else:
                        dias_weekday_to_name = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                        dia_real = dias_weekday_to_name[fecha_weekday]
                        
                        meses_esp = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                                   'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
                        
                        fecha_legible = f"{dia_numero} de {meses_esp[mes_numero]} de {año}"
                        
                        mensaje_error = f"""❌ **Error en la fecha**: 

🗣️ **Dijiste:** "{dia_mencionado} {fecha_legible}"
📅 **Pero:** El {fecha_legible} es **{dia_real}**, no {dia_mencionado}

🤔 **¿Qué querías decir?**
1. **{dia_real} {fecha_legible}** (corregir el día)
2. **Próximo {dia_mencionado}** (buscar el siguiente {dia_mencionado})

💡 Por favor aclara cuál era tu intención."""
                        
                        return False, mensaje_error, fecha_especifica.strftime('%Y-%m-%d')
                        
                except ValueError as date_error:
                    return False, f"❌ La fecha {dia_numero} de {mes_nombre} de {año} no es válida", None
            
            return True, "", None
            
        except Exception as e:
            logger.error(f"❌ Error validando consistencia de fecha: {str(e)}")
            return True, "", None 