from typing import ClassVar
import logging
from app.controler.chat.core.tools.google_calendar_langchain_tool import GoogleCalendarLangChainTool
import json

class AgendaSmartBookingTool(GoogleCalendarLangChainTool):
    logger: ClassVar = logging.getLogger(__name__)
    """
    Tool avanzada para agendar automáticamente en días y franjas libres según la configuración de la agenda en Supabase.
    Además, envía email de confirmación y notifica a un webhook configurado.
    """
    def __init__(self, project_id: str = None, **kwargs):
        super().__init__(project_id=project_id, **kwargs)

    def _get_project_config(self):
        """
        Obtiene configuración completa del proyecto desde tabla agenda en Supabase (versión sin async).
        """
        try:
            if not self.project_id:
                self.logger.error("⚠️ No se proporcionó project_id - requerido para obtener configuración de agenda")
                return None
            response = self.supabase_client.client.table("agenda").select("*").eq("project_id", self.project_id).execute()
            if response.data and len(response.data) > 0:
                agenda_config = response.data[0]
                self.logger.info(f"✅ Configuración de agenda obtenida para project_id: {self.project_id}")
                self._cached_project_config = agenda_config
                return agenda_config
            else:
                self.logger.error(f"❌ No se encontró configuración de agenda para project_id: {self.project_id}")
                return None
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo configuración de agenda: {str(e)}")
            return None

    def book_appointment(self, summary: str, description: str = "", duration: int = 30, preferred_dates: list = None, attendees: list = None, **kwargs):
        """
        Agenda un evento en el primer slot disponible según la configuración de la agenda en Supabase.
        Envía email y notifica al webhook tras agendar.
        Parámetros esperados:
            - summary/title: Título del evento
            - description: Descripción
            - duration: Duración en minutos
            - preferred_dates: Lista de fechas preferidas (YYYY-MM-DD)
            - attendees: Lista de emails invitados
        """
        from datetime import datetime, timedelta
        import pytz

        # 1. Definir rango de fechas a buscar (por defecto próximos 7 días)
        today = datetime.now().date()
        if preferred_dates and len(preferred_dates) > 0:
            start_date = preferred_dates[0]
            end_date = preferred_dates[-1]
        else:
            start_date = today.strftime("%Y-%m-%d")
            end_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")

        # 2. Buscar slots libres
        free_slots = self._find_free_slots(start_date, end_date, duration_minutes=duration)
        if not free_slots:
            return "❌ No hay slots libres disponibles en la agenda para el rango solicitado."
        slot = free_slots[0]

        # 3. Agendar el evento en Google Calendar
        start_datetime = slot["start"]
        end_datetime = slot["end"]
        timezone = self._get_project_config().get("general_settings", {}).get("timezone", "America/Santiago")
        event_result = self._create_event(
            summary=summary,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            timezone=timezone,
            description=description,
            attendees=attendees or [],
            include_meet=True
        )

        # 4. Enviar email de confirmación (placeholder)
        # Aquí deberías llamar a tu servicio de email, usando la configuración de la agenda
        # Por ejemplo: self._send_confirmation_email(...)
        # TODO: Implementar lógica de email

        # 5. Notificar al webhook (placeholder)
        # Aquí deberías llamar a tu servicio de webhook, usando la configuración de la agenda
        # Por ejemplo: self._send_webhook_notification(...)
        # TODO: Implementar lógica de webhook

        return {
            "status": "success",
            "message": f"Evento agendado para {start_datetime}",
            "event": event_result,
            "slot": slot
        }

    def _parse_granular_schedule(self, workflow_settings: dict) -> dict:
        """
        Extrae y valida la configuración granular de horarios desde workflow_settings.
        """
        agenda_settings = workflow_settings.get("AGENDA_COMPLETA", {})
        schedule = agenda_settings.get("schedule", {})
        if not schedule:
            self.logger.info("📋 No hay configuración granular, usando horarios estándar")
            return {
                "monday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "tuesday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "wednesday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "thursday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "friday": {"enabled": True, "time_slots": [{"start": "09:00", "end": "18:00", "description": "Horario estándar"}]},
                "saturday": {"enabled": False, "time_slots": []},
                "sunday": {"enabled": False, "time_slots": []}
            }
        self.logger.info("✅ Configuración granular de horarios cargada exitosamente")
        return schedule

    def _is_day_enabled(self, schedule: dict, day_name: str) -> bool:
        """
        Verifica si un día específico está habilitado.
        """
        day_config = schedule.get(day_name, {})
        return day_config.get("enabled", False)

    def _get_time_slots_for_day(self, schedule: dict, day_name: str) -> list:
        """
        Obtiene las franjas horarias para un día específico.
        """
        if not self._is_day_enabled(schedule, day_name):
            return []
        day_config = schedule.get(day_name, {})
        return day_config.get("time_slots", [])

    def _find_free_slots(self, start_date: str, end_date: str, duration_minutes: int = 30) -> list:
        """
        Busca slots libres en Google Calendar según la configuración de la agenda y la disponibilidad real.
        Retorna una lista de dicts con info de cada slot libre.
        """
        from datetime import datetime, timedelta
        import pytz

        config = self._get_project_config()
        if not config:
            self.logger.error("No se pudo obtener configuración de agenda para buscar slots libres.")
            return []
        workflow_settings = config.get("workflow_settings", {})
        schedule = self._parse_granular_schedule(workflow_settings)
        timezone = config.get("general_settings", {}).get("timezone", "America/Santiago")
        tz = pytz.timezone(timezone)

        # Convertir fechas a datetime
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        delta = timedelta(days=1)
        free_slots = []

        while start_dt <= end_dt:
            day_name = start_dt.strftime("%A").lower()
            if self._is_day_enabled(schedule, day_name):
                time_slots = self._get_time_slots_for_day(schedule, day_name)
                for slot in time_slots:
                    slot_start = datetime.combine(start_dt.date(), datetime.strptime(slot["start"], "%H:%M").time())
                    slot_end = datetime.combine(start_dt.date(), datetime.strptime(slot["end"], "%H:%M").time())
                    # Buscar eventos ocupados en este rango
                    events_json = self._search_events(
                        start_date=slot_start.strftime("%Y-%m-%dT%H:%M:%S"),
                        end_date=slot_end.strftime("%Y-%m-%dT%H:%M:%S"),
                        max_results=50
                    )
                    try:
                        events = json.loads(events_json) if isinstance(events_json, str) else events_json
                    except Exception:
                        events = []
                    # Construir lista de intervalos ocupados
                    busy_intervals = []
                    for ev in events:
                        try:
                            ev_start = datetime.fromisoformat(ev["start"])
                            ev_end = datetime.fromisoformat(ev["end"])
                            busy_intervals.append((ev_start, ev_end))
                        except Exception:
                            continue
                    # Ordenar por inicio
                    busy_intervals.sort()
                    # Buscar huecos libres
                    current = slot_start
                    while current + timedelta(minutes=duration_minutes) <= slot_end:
                        overlap = False
                        for b_start, b_end in busy_intervals:
                            if b_start < current + timedelta(minutes=duration_minutes) and b_end > current:
                                overlap = True
                                current = b_end
                                break
                        if not overlap:
                            free_slots.append({
                                "start": current.astimezone(tz).isoformat(),
                                "end": (current + timedelta(minutes=duration_minutes)).astimezone(tz).isoformat(),
                                "day": day_name,
                                "slot": slot
                            })
                            current += timedelta(minutes=duration_minutes)
            start_dt += delta
        return free_slots 