import pytz

# Configuración del sistema de agendamiento
DIAS_DISPONIBLES = 7  # Días hacia adelante para mostrar disponibilidad
DURACION_VISITA = 1  # Duración de cada visita en horas (puede ser 1, 2, etc.)
HORAS_LABORALES = 8  # Cantidad de horas laborales por día
HORA_INICIO = 9  # Hora de inicio de la jornada laboral (9 AM)
ZONA_HORARIA = pytz.timezone('America/Santiago')

# Mensajes del sistema
MSG_SELECCIONA_CALENDARIO = "Por favor, selecciona un calendario por su número."
MSG_SELECCIONA_HORARIO = "Por favor, selecciona un horario por su número."
MSG_HORARIO_INVALIDO = "El horario seleccionado no es válido. Por favor, elige otro."
MSG_CALENDARIO_INVALIDO = "El calendario seleccionado no es válido. Por favor, elige otro."
MSG_VISITA_CREADA = "¡Visita agendada correctamente!" 