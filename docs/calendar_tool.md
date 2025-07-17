# calendar_tool.py - Documentación

## Descripción General
`calendar_tool.py` es la herramienta principal de LangChain para la integración directa con Google Calendar API. Proporciona acceso de bajo nivel a todas las operaciones de calendario, manejando autenticación, construcción de requests y parsing de respuestas.

## Arquitectura y Relación con el Sistema

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐
│ WorkflowManager │ --> │ CalendarService  │ --> │ calendar_tool   │ --> │ Google       │
│                 │     │ (Alto nivel)     │     │ (Herramienta)   │     │ Calendar API │
└─────────────────┘     └──────────────────┘     └─────────────────┘     └──────────────┘
```

### Diferencias con CalendarService

| Aspecto | calendar_tool | CalendarService |
|---------|--------------|-----------------|
| **Nivel** | Bajo nivel (herramienta LangChain) | Alto nivel (servicio) |
| **Propósito** | Interfaz directa con Google Calendar API | Lógica de negocio y abstracción |
| **Manejo de errores** | Básico, retorna strings | Robusto con categorías y severidades |
| **Retry** | No implementado | Automático con backoff exponencial |
| **Formato entrada** | Query string: "ACCIÓN\|PARÁMETROS" | Métodos Python con parámetros tipados |
| **Caché** | Lee y actualiza caché | Gestión completa del caché |

## Función Principal

### `@tool google_calendar_tool(query: str, state: dict) -> str`

Herramienta decorada con `@tool` de LangChain que procesa todas las operaciones de calendario.

**Formato de Query**: `[ACCIÓN]|[PARÁMETRO1=VALOR1]|[PARÁMETRO2=VALOR2]`

**Acciones Soportadas**:
- `list_events` - Lista eventos en un rango
- `search_events` - Busca eventos por criterios
- `create_event` - Crea nuevo evento
- `update_event` - Actualiza evento existente
- `delete_event` - Elimina evento
- `check_availability` - Verifica disponibilidad
- `find_available_slots` - Encuentra horarios libres

## Funciones de Configuración

### `get_project_calendar_config(project_id: str, agenda_data: dict = None) -> dict`

Obtiene la configuración del calendario desde la tabla "agenda" en Supabase.

**Características**:
- Prioriza datos cacheados para evitar consultas duplicadas
- Extrae configuración granular de horarios por día
- Calcula automáticamente horas extremas de trabajo
- Retorna configuración por defecto si no hay datos

**Configuración extraída**:
```python
{
    "default_duration": 1.0,              # Horas
    "start_hour": 9,                      # Hora inicio jornada
    "end_hour": 18,                       # Hora fin jornada
    "working_days": ["monday", ...],      # Días laborales
    "auto_include_meet": True,            # Google Meet automático
    "timezone": "America/Santiago"        # Zona horaria
}
```

### `get_default_calendar_config() -> dict`

Retorna configuración por defecto cuando no hay configuración específica del proyecto.

## Funciones de Calendario

### 1. `find_next_available_slots(service, params, project_config, state)`

La función más compleja que encuentra horarios disponibles considerando:

**Características principales**:
- Validación de consistencia de fechas
- Verificación de conectividad con Google Calendar
- Soporte para configuración granular por día
- Generación inteligente de slots según duración
- Respeto de horarios laborales y feriados
- Filtrado por disponibilidad real en calendario

**Parámetros soportados**:
- `duration` - Duración en horas (default: 1)
- `specific_date` - Fecha específica YYYY-MM-DD
- `day` - Día de la semana en español
- `start_hour` - Hora inicio búsqueda
- `end_hour` - Hora fin búsqueda
- `exclude_holidays` - Excluir feriados
- `search_weeks_ahead` - Semanas a buscar

**Algoritmo**:
1. Valida conectividad y consistencia de fechas
2. Obtiene configuración granular si existe
3. Genera slots potenciales según configuración
4. Verifica disponibilidad real en calendario
5. Filtra y retorna slots libres

### 2. `create_event(service, params, state, project_config)`

Crea eventos con validaciones y características avanzadas.

**Características**:
- Verificación automática de conflictos
- Inclusión opcional de Google Meet
- Validación de emails de asistentes
- Conversión automática a zona horaria Chile
- Invalidación de caché post-creación

**Parámetros**:
- `title` - Título del evento (requerido)
- `start` - Fecha/hora inicio ISO format
- `end` - Fecha/hora fin (opcional)
- `description` - Descripción
- `attendees` - Emails separados por coma
- `meet` - true/false para Google Meet
- `force_create` - Ignorar conflictos

### 3. `check_availability(service, params, project_config)`

Verifica disponibilidad usando caché inteligente.

**Optimizaciones**:
- Usa `conflict_cache` para consultas repetidas
- Invalida caché selectivamente
- Manejo thread-safe con decorador

### 4. `check_time_conflicts(service, start_time, end_time, project_id)`

Función interna crítica para detección de conflictos.

**Características**:
- Integración con sistema de caché
- Detección precisa de solapamientos
- Logging detallado para debugging
- Manejo robusto de errores de API

## Utilidades y Helpers

### Funciones de calendar_utils

El módulo importa utilidades compartidas:
- `CHILE_TZ` - Timezone de Chile
- `format_date_spanish` - Formateo de fechas en español
- `normalize_to_chile_timezone` - Normalización de zonas horarias
- `get_day_name_spanish` - Conversión de nombres de días

## Sistema de Caché

### Integración con `conflict_cache`

- **Lectura**: Verifica caché antes de consultar API
- **Escritura**: Actualiza caché con nuevos datos
- **Invalidación**: Limpia entradas afectadas por cambios
- **Thread-safety**: Operaciones protegidas con locks

## Manejo de Errores

### Clasificación de errores

```python
# Errores de autenticación
if "authentication" in str(e).lower():
    return "Error de autenticación..."

# Errores de red
elif "network" in str(e).lower():
    return "Error de conexión..."

# Límites de API
elif "quota" in str(e).lower():
    return "Límite de API alcanzado..."

# Errores genéricos
else:
    return "Error inesperado..."
```

## Integración con OAuth2

### `get_google_credentials(project_id)`

Obtiene credenciales OAuth2 desde la tabla `calendar_integrations`:

1. Consulta integración activa para el proyecto
2. Verifica expiración de tokens
3. Construye objeto `Credentials` de Google
4. Retorna None si no hay credenciales válidas

**Campos requeridos**:
- `access_token`
- `refresh_token`
- `token_uri`
- `client_id`
- `client_secret`
- `scopes`

## Optimizaciones de Rendimiento

1. **Caché de configuración**: Evita consultas repetidas a BD
2. **Validación temprana**: Detecta errores antes de llamar API
3. **Generación eficiente de slots**: Algoritmo optimizado
4. **Consultas batch**: Minimiza llamadas a Calendar API

## Logging y Debugging

El módulo implementa logging extensivo:

```python
logger.info("Configuración obtenida...")      # Información general
logger.warning("Formato inválido...")         # Advertencias
logger.error("Error en operación...")         # Errores
logger.debug("Detalles de procesamiento...")  # Debug
```

## Consideraciones de Seguridad

1. **Validación de entrada**: Todas las queries son parseadas y validadas
2. **Sanitización**: Parámetros limpiados antes de usar
3. **Credenciales seguras**: OAuth2 con tokens encriptados
4. **Segregación por proyecto**: Cada proyecto tiene sus propias credenciales

## Ejemplo de Uso Completo

```python
# Query para buscar horarios disponibles
query = "find_available_slots|duration=1.5|specific_date=2025-01-20|exclude_holidays=true"

# Estado con configuración del proyecto
state = {
    "project": project_object,
    "agenda_config": {
        "cached_agenda_data": {...},
        "granular_schedule": {...}
    }
}

# Ejecutar herramienta
result = google_calendar_tool(query, state)

# Resultado parseado por CalendarService
# "Horarios disponibles:
#  1. Lunes 20 de enero a las 09:00
#  2. Lunes 20 de enero a las 14:00
#  3. Martes 21 de enero a las 10:00"
```

## Mejores Prácticas

1. **Usar CalendarService** para operaciones de alto nivel
2. **Pasar agenda_config en state** para evitar consultas duplicadas
3. **Validar disponibilidad** antes de crear eventos
4. **Manejar errores** apropiadamente en cada nivel
5. **Respetar límites de API** de Google Calendar