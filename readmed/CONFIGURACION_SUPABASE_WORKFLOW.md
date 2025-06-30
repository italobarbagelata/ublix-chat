# 🚀 Configuración BASE para Workflow Orchestrator (REQUERIDA)

## ⚠️ **IMPORTANTE**: Sin esta configuración, el workflow orchestrator NO funcionará

Como eliminamos todos los fallbacks, **DEBES** tener esta configuración en la tabla `projects` de Supabase.

## 📊 Estructura de Tabla `projects` (REQUERIDA)

```sql
-- 1. Asegurar que la tabla projects tiene las columnas JSONB
ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS owner_email VARCHAR(255),
ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255),
ADD COLUMN IF NOT EXISTS email_templates JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS workflow_settings JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS general_settings JSONB DEFAULT '{}';
```

## 🔧 Configuración BASE Mínima (OBLIGATORIA)

Para cada proyecto que use workflow orchestrator, ejecutar:

```sql
-- CONFIGURACIÓN MÍNIMA REQUERIDA para que funcione workflow_orchestrator
UPDATE projects SET 
    owner_email = 'tu-email@empresa.com',  -- 🚨 REQUERIDO: Email del dueño del proyecto
    contact_email = 'contacto@empresa.com', -- Opcional: Email de contacto backup
    email_templates = '{
        "confirmacion": {
            "subject": "✅ Confirmación de cita: {title}",
            "content": "<h2>🎉 ¡Tu cita ha sido confirmada!</h2><p><strong>📅 Evento:</strong> {title}</p><p><strong>🕒 Horario:</strong> {start_datetime} - {end_datetime}</p>{description_section}<p>¡Esperamos verte pronto! 🌟</p>"
        },
        "recordatorio": {
            "subject": "🔔 Recordatorio: {title}",
            "content": "<h2>🔔 Recordatorio de tu próxima cita</h2><p><strong>📅 Evento:</strong> {title}</p><p><strong>🕒 Horario:</strong> {start_datetime}</p><p>¡No olvides tu cita! 📝</p>"
        },
        "custom": {
            "subject": "📧 Información: {title}",
            "content": "<h2>📧 Información de tu evento</h2><p><strong>📅 Evento:</strong> {title}</p><p><strong>🕒 Horario:</strong> {start_datetime} - {end_datetime}</p>"
        }
    }',
    workflow_settings = '{
        "AGENDA_COMPLETA": {
            "auto_send_confirmation": true,
            "auto_notify_owner": true,
            "include_calendar_link": true,
            "default_duration_minutes": 60
        }
    }',
    general_settings = '{
        "timezone": "America/Santiago",
        "calendar_enabled": true,
        "company_info": {
            "name": "Tu Empresa",
            "phone": "+56 2 1234 5678"
        }
    }'
WHERE project_id = 'TU-PROJECT-ID-AQUI';  -- 🚨 CAMBIAR por tu project_id real
```

## 📋 Campos OBLIGATORIOS

### **1. owner_email** (CRÍTICO)
```sql
owner_email = 'tu-email@empresa.com'
```
- **¿Por qué?**: Sin esto, no se pueden enviar notificaciones al dueño
- **Error sin esto**: "❌ No se encontró email del dueño en configuración"

### **2. email_templates** (CRÍTICO)
```json
{
  "confirmacion": {
    "subject": "✅ Confirmación de cita: {title}",
    "content": "HTML del email..."
  }
}
```
- **¿Por qué?**: Sin esto, no se pueden generar emails
- **Error sin esto**: "⚠️ No se pudo obtener template de email"

## 🎯 Variables Disponibles en Templates

En el `content` de los templates puedes usar estas variables:

- `{title}` - Título del evento
- `{start_datetime}` - Fecha/hora de inicio  
- `{end_datetime}` - Fecha/hora de fin
- `{description}` - Descripción del evento
- `{description_section}` - HTML formateado con descripción

**Ejemplo de uso:**
```html
<p><strong>📅 Evento:</strong> {title}</p>
<p><strong>🕒 Horario:</strong> {start_datetime} - {end_datetime}</p>
{description_section}
```

## ✅ Verificar Configuración

Ejecuta esta query para verificar que tu proyecto está configurado:

```sql
SELECT 
    project_id,
    name,
    owner_email,
    contact_email,
    email_templates->'confirmacion' as template_confirmacion,
    workflow_settings->'AGENDA_COMPLETA' as workflow_agenda,
    general_settings->'timezone' as timezone
FROM projects 
WHERE project_id = 'TU-PROJECT-ID';
```

**Resultado esperado:**
- ✅ `owner_email` NO debe ser NULL
- ✅ `template_confirmacion` debe tener `subject` y `content`
- ✅ `workflow_agenda` debe tener configuraciones
- ✅ `timezone` debe estar definido

## 🚨 Errores Comunes

### Error: "No se pudo obtener configuración del proyecto"
**Causa**: `project_id` incorrecto o no existe en la tabla
**Solución**: Verificar que el `project_id` existe en la tabla `projects`

### Error: "No se encontró email del dueño"
**Causa**: `owner_email` es NULL o vacío
**Solución**: Ejecutar `UPDATE projects SET owner_email = 'tu-email@empresa.com'`

### Error: "No se pudo obtener template de email"
**Causa**: Campo `email_templates` está vacío o el template no existe
**Solución**: Ejecutar el UPDATE con la configuración de templates

## 📞 Script de Configuración Rápida

```sql
-- COPIA Y PEGA ESTE SCRIPT - Solo cambiar el project_id
UPDATE projects SET 
    owner_email = 'CAMBIAR-POR-TU-EMAIL@empresa.com',
    contact_email = 'contacto@empresa.com',
    email_templates = '{
        "confirmacion": {
            "subject": "✅ Confirmación de cita: {title}",
            "content": "<div style=\"font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;\"><div style=\"background: #4CAF50; color: white; padding: 20px; text-align: center;\"><h2 style=\"margin: 0;\">🎉 ¡Tu cita ha sido confirmada!</h2></div><div style=\"padding: 20px; background: #f8f9fa;\"><p><strong>📅 Evento:</strong> {title}</p><p><strong>🕒 Horario:</strong> {start_datetime} - {end_datetime}</p>{description_section}<p style=\"margin-top: 20px; color: #4CAF50;\">¡Esperamos verte pronto! 🌟</p></div></div>"
        },
        "recordatorio": {
            "subject": "🔔 Recordatorio: {title}",
            "content": "<div style=\"font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;\"><div style=\"background: #FF9800; color: white; padding: 20px; text-align: center;\"><h2 style=\"margin: 0;\">🔔 Recordatorio de cita</h2></div><div style=\"padding: 20px; background: #f8f9fa;\"><p><strong>📅 Evento:</strong> {title}</p><p><strong>🕒 Horario:</strong> {start_datetime}</p><p style=\"margin-top: 20px; color: #FF9800;\">¡No olvides tu cita! 📝</p></div></div>"
        }
    }',
    workflow_settings = '{
        "AGENDA_COMPLETA": {
            "auto_send_confirmation": true,
            "auto_notify_owner": true,
            "default_duration_minutes": 60
        }
    }',
    general_settings = '{
        "timezone": "America/Santiago",
        "calendar_enabled": true
    }'
WHERE project_id = 'CAMBIAR-POR-TU-PROJECT-ID';
```

## 🎯 Resultado Final

Con esta configuración, el workflow orchestrator podrá:

✅ **Crear eventos** en calendario  
✅ **Enviar emails** de confirmación personalizados  
✅ **Notificar al dueño** del proyecto automáticamente  
✅ **Buscar horarios** disponibles  
✅ **Actualizar y cancelar** eventos  

¡Ya no habrá más errores por falta de configuración! 🚀 

# 🚀 Configuración Granular Implementada - agenda_tool.py

## ✅ Implementación Completada

Se ha implementado exitosamente la **configuración granular de horarios** en el `agenda_tool.py`, permitiendo control total sobre días y franjas horarias específicas.

## 🔧 Nuevas Funcionalidades Implementadas

### 1. **Validaciones Granulares en Agendamiento**
- **Método:** `_agenda_completa_workflow()`
- **Funcionalidad:** Valida automáticamente que la fecha/hora solicitada esté dentro de los horarios configurados
- **Comportamiento:** Si el horario no está disponible, muestra horarios alternativos

### 2. **Búsqueda Inteligente de Horarios**
- **Método:** `_busqueda_horarios_workflow()`
- **Funcionalidad:** Respeta configuración granular para mostrar solo horarios habilitados
- **Características:**
  - Detecta días específicos mencionados ("para el viernes")
  - Valida disponibilidad antes de mostrar opciones
  - Muestra resumen completo de horarios si no se especifica día

### 3. **Métodos Granulares Añadidos**

#### `_parse_granular_schedule()`
- Extrae configuración desde `workflow_settings.AGENDA_COMPLETA.schedule`
- Aplica configuración por defecto si no existe granular
- Soporta horarios estándar 9-18 como fallback

#### `_is_day_enabled()` / `_get_time_slots_for_day()`
- Verificación de días habilitados
- Extracción de franjas horarias por día
- Manejo de múltiples slots por día

#### `_is_time_in_working_hours()`
- Validación de fecha/hora específica contra configuración
- Mapeo automático de días (monday → lunes)
- Validación de franjas horarias (8:00-12:00, 13:00-19:00)

#### `_validate_specific_day_request()`
- Validación de días solicitados por texto
- Manejo de acentos (miércoles/miercoles)
- Sugerencias de días alternativos

#### `_get_available_schedule_summary()`
- Genera resumen legible de horarios disponibles
- Formato: "Lunes: 8:00-12:00 (Mañana), 13:00-19:00 (Tarde)"
- Traducción automática inglés → español

## 📋 Configuración en Supabase

### Estructura Granular en `workflow_settings`:
```json
{
  "AGENDA_COMPLETA": {
    "default_duration_minutes": 60,
    "schedule": {
      "monday": {
        "enabled": true,
        "time_slots": [
          {"start": "08:00", "end": "12:00", "description": "Mañana"},
          {"start": "13:00", "end": "19:00", "description": "Tarde"}
        ]
      },
      "tuesday": {
        "enabled": true,
        "time_slots": [
          {"start": "09:00", "end": "17:00", "description": "Jornada continua"}
        ]
      },
      "wednesday": {
        "enabled": false,
        "time_slots": []
      }
    }
  }
}
```

## 🎯 Casos de Uso Cubiertos

### ✅ Agendamiento con Validación
```
Usuario: "Quiero agendar para el miércoles a las 10am"
Sistema: ❌ No trabajo los miércoles. Días disponibles: lunes, martes, jueves, viernes
```

### ✅ Búsqueda por Día Específico
```
Usuario: "¿Qué horarios tienes para el viernes?"
Sistema: ✅ Viernes disponible. Horarios: 8:00-12:00 (Mañana), 13:00-19:00 (Tarde)
```

### ✅ Horario Fuera de Franja
```
Usuario: "Para el lunes a las 7am"
Sistema: ❌ Horario fuera de franjas laborales. Disponible: 8:00-12:00 (Mañana), 13:00-19:00 (Tarde)
```

### ✅ Búsqueda General
```
Usuario: "¿Qué horarios tienes?"
Sistema: Muestra todos los días y franjas configuradas
```

## 🔄 Flujo de Validación

1. **Carga Configuración:** `_parse_granular_schedule()`
2. **Detecta Día Solicitado:** `_extract_day_from_text()`
3. **Valida Disponibilidad:** `_validate_specific_day_request()`
4. **Verifica Horario:** `_is_time_in_working_hours()`
5. **Respuesta Inteligente:** Aprueba o sugiere alternativas

## 📊 Beneficios de la Implementación

### 🎯 **Flexibilidad Total**
- Horarios diferentes cada día
- Múltiples franjas por día (descansos, almuerzo)
- Control granular de disponibilidad

### 🤖 **Automatización Inteligente**
- Validación automática en tiempo real
- Sugerencias contextuales
- Manejo de errores descriptivo

### 🔧 **Fácil Configuración**
- Todo desde tabla `agenda` en Supabase
- Sin necesidad de modificar código
- Configuración por proyecto independiente

### 📈 **Escalabilidad**
- Soporta cualquier tipo de horario de negocio
- Configuración específica por cliente
- Fácil modificación de horarios

## 🚀 Próximos Pasos Opcionales

1. **Días Festivos:** Integrar tabla de días no laborales
2. **Zonas Horarias:** Manejo automático de timezones
3. **Duraciones Variables:** Slots de diferente duración
4. **Reservas Recurrentes:** Eventos que se repiten
5. **Buffer Times:** Tiempo entre citas automático

## 📝 Comandos de Prueba

```sql
-- Habilitar solo lunes, miércoles, viernes
UPDATE agenda 
SET workflow_settings = jsonb_set(
    workflow_settings, 
    '{AGENDA_COMPLETA,schedule}',
    '{
        "monday": {"enabled": true, "time_slots": [{"start": "09:00", "end": "17:00", "description": "Horario completo"}]},
        "tuesday": {"enabled": false, "time_slots": []},
        "wednesday": {"enabled": true, "time_slots": [{"start": "08:00", "end": "12:00", "description": "Solo mañanas"}]},
        "thursday": {"enabled": false, "time_slots": []},
        "friday": {"enabled": true, "time_slots": [{"start": "14:00", "end": "20:00", "description": "Solo tardes"}]},
        "saturday": {"enabled": false, "time_slots": []},
        "sunday": {"enabled": false, "time_slots": []}
    }'::jsonb
)
WHERE project_id = '29ab2dc1-8790-4ef1-a9d4-f6d684b00572';
```

La implementación está **100% funcional** y lista para usar con configuración granular completa. 🎉 