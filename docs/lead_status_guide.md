# Guía de Estados de Lead para Sistema de Agendamiento

## Estados Disponibles

El sistema de chat ahora trackea automáticamente el progreso del usuario a través del flujo de agendamiento con los siguientes estados:

### 1. `nuevo_chat`
**Descripción:** Usuario inició contacto con el sistema
**Cuándo se activa:** 
- Al inicio de cualquier conversación
- Cuando no se detecta ningún patrón específico

### 2. `eligiendo_servicio`
**Descripción:** Usuario está eligiendo qué servicio necesita
**Palabras clave detectadas:**
- "servicio", "necesito", "quiero", "quisiera"
- "consulta", "cita", "turno", "reserva", "agendar"
- "qué ofrecen", "opciones", "tipos de"

### 3. `eligiendo_horario`
**Descripción:** Usuario está seleccionando fecha y hora
**Palabras clave detectadas:**
- **Fechas:** Días de la semana, "mañana", "próxima semana", meses del año
- **Horarios:** ":00", ":30", ":15", ":45", "a las"
- **Períodos:** "mañana", "tarde", "noche"
- **Referencias:** "cuando", "cuándo", "disponible", "horario"

### 4. `recopilando_datos`
**Descripción:** Usuario está proporcionando sus datos personales
**Detección automática:**
- Emails (formato email@dominio.com)
- Números de teléfono (8-12 dígitos)
- "mi nombre es", "me llamo"
- "mi correo", "mi teléfono"

### 5. `esperando_confirmacion`
**Descripción:** Cita armada, esperando confirmación del usuario
**Uso manual:** Se debe establecer cuando se presenta el resumen de la cita

### 6. `reservado`
**Descripción:** Cita confirmada y agendada exitosamente
**Palabras clave detectadas:**
- "confirmo", "sí acepto", "perfecto"
- "de acuerdo", "está bien", "confirmado"
- "adelante", "procedamos"

## Flujo de Transiciones Válidas

```
nuevo_chat 
    → eligiendo_servicio
        → eligiendo_horario (fecha y hora)
            → recopilando_datos
                → esperando_confirmacion
                    → reservado
```

**Nota:** El estado `recopilando_datos` puede ocurrir en cualquier momento del flujo.

## Ejemplos de Uso en el Chat

### Actualización Manual de Estado
```python
# Cuando el usuario elige un servicio
save_contact_tool(lead_status="eligiendo_servicio")

# Cuando el usuario selecciona fecha y/u hora
save_contact_tool(lead_status="eligiendo_horario")

# Cuando presentas el resumen de la cita
save_contact_tool(lead_status="esperando_confirmacion")

# Cuando el usuario confirma
save_contact_tool(lead_status="reservado")
```

### Detección Automática
```python
# El sistema detectará automáticamente el estado basado en el mensaje
Usuario: "Quisiera agendar una cita"
→ Estado detectado: eligiendo_servicio

Usuario: "Prefiero el martes por la mañana"
→ Estado detectado: eligiendo_horario

Usuario: "A las 10:00 está perfecto"
→ Estado detectado: eligiendo_horario

Usuario: "Mi email es juan@gmail.com"
→ Estado detectado: recopilando_datos

Usuario: "Sí, confirmo la cita"
→ Estado detectado: reservado
```

### Combinación con Otros Datos
```python
save_contact_tool(
    name="Juan Pérez",
    email="juan@email.com",
    phone_number="912345678",
    lead_status="recopilando_datos"
)
```

## Validación de Transiciones

El sistema valida que las transiciones de estado sean lógicas. Por ejemplo:
- No se puede pasar de `nuevo_chat` directamente a `reservado`
- No se puede retroceder de `reservado` a estados anteriores

Si se intenta una transición inválida, el sistema mostrará un mensaje de error indicando el próximo estado esperado.

## Mejores Prácticas

1. **Usa detección automática cuando sea posible:** El sistema puede detectar muchos estados automáticamente basándose en el contenido del mensaje.

2. **Actualiza manualmente en puntos clave:** Especialmente para `esperando_confirmacion` que no se detecta automáticamente.

3. **Monitorea el progreso:** El estado del lead te ayuda a entender dónde está cada usuario en el proceso de agendamiento.

4. **Personaliza respuestas según el estado:** Puedes adaptar las respuestas del bot según el estado actual del lead.

## Integración con el Sistema

El estado del lead se guarda en la tabla `contacts` en el campo `lead_status`. Esto permite:
- Hacer seguimiento del progreso de cada usuario
- Generar reportes de conversión
- Identificar puntos de abandono en el flujo
- Personalizar la experiencia según el estado