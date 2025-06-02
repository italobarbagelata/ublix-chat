# Herramientas de Feriados de Chile 🇨🇱

Este módulo proporciona herramientas para verificar feriados nacionales de Chile, específicamente diseñadas para asistentes de chat que necesitan manejar consultas relacionadas con fechas y días laborales.

## Características

- ✅ **Soporte completo en español**: Interpreta fechas en lenguaje natural
- 📅 **Cobertura amplia**: Feriados de Chile desde 2020 hasta 2035
- 🕐 **Zona horaria correcta**: Configurado para America/Santiago
- 🤖 **Integración con LangChain**: Herramientas listas para usar con agentes

## Herramientas Disponibles

### 1. `check_chile_holiday_tool`

Verifica si una fecha específica es feriado en Chile.

**Ejemplos de uso:**
```python
# Consultas típicas de usuarios
"¿Es feriado mañana?"
"¿El 18 de septiembre es feriado?"
"¿Es día hábil el lunes?"
"25 de diciembre"
"¿Mañana trabajo?"
```

**Respuestas de ejemplo:**
- ✅ Sí, el viernes 18 de septiembre de 2024 es feriado en Chile: **Día de la Independencia**.
- ❌ El martes 17 de septiembre de 2024 no es feriado en Chile. Es un día hábil normal.
- ❌ El sábado 19 de septiembre de 2024 no es feriado en Chile, pero es sábado (fin de semana).

### 2. `next_chile_holidays_tool`

Muestra los próximos feriados de Chile.

**Ejemplos de uso:**
```python
# Mostrar próximos 3 feriados (por defecto)
""

# Mostrar próximos 5 feriados
"5"

# Mostrar próximos 10 feriados
"10"
```

**Respuesta de ejemplo:**
```
🇨🇱 **Próximos 3 feriados en Chile:**

• **Día de la Independencia**: viernes 18 de septiembre de 2024 (en 5 días)
• **Día de las Glorias del Ejército**: sábado 19 de septiembre de 2024 (en 6 días)
• **Día de la Raza**: lunes 12 de octubre de 2024 (en 29 días)
```

## Integración en Proyectos

Para habilitar estas herramientas en un proyecto:

1. **Agregar a la configuración del proyecto:**
```python
project.enabled_tools = ["chile_holidays"]  # Agregar a la lista existente
```

2. **Las herramientas se cargarán automáticamente** cuando el agente se inicialice.

## Casos de Uso Comunes

### Para Empresas
- **Planificación de reuniones**: "¿Podemos reunirnos el lunes?"
- **Cálculo de días hábiles**: "¿Cuántos días hábiles quedan en septiembre?"
- **Recordatorios**: "¿Qué feriados vienen?"

### Para Usuarios Generales
- **Planificación personal**: "¿Es feriado mañana para planificar mi viaje?"
- **Consultas rápidas**: "¿El 25 de diciembre es feriado?"
- **Información general**: "¿Qué feriados vienen este mes?"

## Dependencias

```bash
pip install holidays dateparser
```

## Notas Técnicas

- **Biblioteca `holidays`**: Usa la implementación oficial de feriados de Chile
- **Parsing inteligente**: `dateparser` con configuración específica para español
- **Manejo de errores**: Respuestas claras cuando no se puede interpretar la fecha
- **Logging**: Registra actividad para debugging
- **Formato amigable**: Respuestas con emojis y formato markdown

## Feriados Soportados

La herramienta reconoce todos los feriados oficiales de Chile:
- Año Nuevo
- Viernes Santo
- Sábado Santo
- Día del Trabajo
- Día de las Glorias Navales
- Día de la Independencia
- Día de las Glorias del Ejército
- Día de la Raza
- Día de las Iglesias Evangélicas y Protestantes
- Día de Todos los Santos
- Inmaculada Concepción
- Navidad

Y feriados variables según la legislación chilena. 