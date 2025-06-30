# Ejemplo de uso: AgendaSmartBookingTool

## ¿Qué hace?
Agenda automáticamente en el primer horario libre según la configuración de la agenda en Supabase, Google Calendar y envía email/webhook.

---

## Ejemplo de código Python

```python
from app.controler.chat.core.tools.agenda_smart_booking_tool import AgendaSmartBookingTool

# Instanciar la tool con el project_id correspondiente
tool = AgendaSmartBookingTool(project_id="TU_PROJECT_ID")

# Parámetros de ejemplo
summary = "Reunión de prueba"
description = "Agendamiento automático usando AgendaSmartBookingTool"
duration = 30  # minutos
preferred_dates = ["2024-06-10", "2024-06-11"]  # Opcional
attendees = ["cliente@email.com"]

# Agendar
resultado = tool.book_appointment(
    summary=summary,
    description=description,
    duration=duration,
    preferred_dates=preferred_dates,
    attendees=attendees
)
print(resultado)
```

---

## Prompt sugerido para chatbot

```
Quiero agendar una reunión de 30 minutos con el cliente juan.perez@email.com la próxima semana. Busca el primer horario disponible y envía confirmación por email.
```

O bien:

```
Reserva una cita de 1 hora para revisión de proyecto, preferentemente el martes o miércoles, y avísame por correo.
```

---

## Notas
- El bot buscará automáticamente el primer slot libre según la agenda y Google Calendar.
- Se enviará email y webhook si está configurado.
- Puedes personalizar los parámetros según tu flujo. 