# 📅 CONFIGURACIÓN DE HORARIOS Y DÍAS HABILITADOS - AGENDA_TOOL

## 🔍 **SITUACIÓN ACTUAL**

### ❌ **Tu `agenda_tool.py` NO tiene configuración de horarios**
- Solo usa `default_duration_minutes` 
- **NO valida días laborales**
- **NO valida horarios laborales**
- **NO excluye feriados**

### ✅ **PERO tu `calendar_tool.py` SÍ tiene configuración completa**
- Configuración avanzada de horarios laborales
- Validación de días de trabajo
- Exclusión de feriados chilenos
- Buffer entre citas

---

## 🎯 **SOLUCIÓN: Configuración Completa de Horarios**

### **1. INSERT SQL con configuración de horarios** 
```sql
-- CONFIGURACIÓN COMPLETA DE HORARIOS LABORALES
"workflow_settings": {
    "AGENDA_COMPLETA": {
        "default_duration_minutes": 60,
        "start_hour": 9,              // 🕘 Inicio: 9:00 AM
        "end_hour": 18,               // 🕕 Fin: 6:00 PM  
        "working_days": [             // 📅 Solo días laborales
            "monday", "tuesday", "wednesday", "thursday", "friday"
        ],
        "buffer_minutes": 15,         // ⏱️ Tiempo entre citas
        "auto_include_holidays_validation": true  // 🚫 Excluir feriados
    },
    "BUSQUEDA_HORARIOS": {
        "max_slots_to_show": 3,       // 🔢 Máximo 3 opciones
        "search_weeks_ahead": 4,      // 📆 Buscar 4 semanas adelante
        "exclude_weekends": true,     // 🚫 No fines de semana
        "exclude_holidays": true      // 🚫 No feriados
    }
}
```

---

## 📋 **TIPOS DE CONFIGURACIÓN DISPONIBLES**

### **🕒 HORARIOS LABORALES**
```json
{
    "start_hour": 9,        // Hora de inicio (24h format)
    "end_hour": 18,         // Hora de fin (24h format)  
    "buffer_minutes": 15    // Minutos entre citas
}
```

**Ejemplos:**
- **Ejecutivos**: `start_hour: 7, end_hour: 19` (7am-7pm)
- **Comercial**: `start_hour: 8, end_hour: 20` (8am-8pm)
- **Técnico**: `start_hour: 9, end_hour: 17` (9am-5pm)

### **📅 DÍAS LABORALES**
```json
{
    "working_days": [
        "monday", "tuesday", "wednesday", "thursday", "friday"
    ]
}
```

**Opciones disponibles:**
- `monday` - Lunes
- `tuesday` - Martes  
- `wednesday` - Miércoles
- `thursday` - Jueves
- `friday` - Viernes
- `saturday` - Sábado
- `sunday` - Domingo

### **⏰ DURACIÓN DE CITAS**
```json
{
    "default_duration_minutes": 60  // Minutos por cita
}
```

**Ejemplos comunes:**
- **Consulta rápida**: `30 minutos`
- **Reunión estándar**: `60 minutos`
- **Presentación ejecutiva**: `90 minutos`
- **Workshop**: `120 minutos`

---

## 🛠️ **COMANDOS DE CONFIGURACIÓN**

### **1. Cambiar horarios laborales:**
```sql
-- Horarios ejecutivos (7am - 7pm)
UPDATE agenda SET workflow_settings = jsonb_set(workflow_settings, '{AGENDA_COMPLETA,start_hour}', '7') WHERE project_id = 'tu-project-id';
UPDATE agenda SET workflow_settings = jsonb_set(workflow_settings, '{AGENDA_COMPLETA,end_hour}', '19') WHERE project_id = 'tu-project-id';
```

### **2. Incluir sábados:**
```sql
UPDATE agenda SET workflow_settings = jsonb_set(
    workflow_settings, 
    '{AGENDA_COMPLETA,working_days}', 
    '["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]'::jsonb
) WHERE project_id = 'tu-project-id';
```

### **3. Cambiar duración de citas:**
```sql
-- Citas de 30 minutos
UPDATE agenda SET workflow_settings = jsonb_set(
    workflow_settings, 
    '{AGENDA_COMPLETA,default_duration_minutes}', 
    '30'::jsonb
) WHERE project_id = 'tu-project-id';
```

### **4. Configurar buffer entre citas:**
```sql
-- 30 minutos entre citas
UPDATE agenda SET workflow_settings = jsonb_set(
    workflow_settings, 
    '{AGENDA_COMPLETA,buffer_minutes}', 
    '30'::jsonb
) WHERE project_id = 'tu-project-id';
```

---

## 📊 **CONFIGURACIONES PRE-DEFINIDAS**

### **🏢 CONFIGURACIÓN EMPRESARIAL**
```sql
-- Lunes a viernes, 8am-6pm, citas de 60 min
UPDATE agenda SET workflow_settings = '{
    "AGENDA_COMPLETA": {
        "default_duration_minutes": 60,
        "start_hour": 8,
        "end_hour": 18,
        "working_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "buffer_minutes": 15
    }
}' WHERE project_id = 'tu-project-id';
```

### **👔 CONFIGURACIÓN EJECUTIVA**
```sql
-- Lunes a sábado, 7am-8pm, citas de 90 min
UPDATE agenda SET workflow_settings = '{
    "AGENDA_COMPLETA": {
        "default_duration_minutes": 90,
        "start_hour": 7,
        "end_hour": 20,
        "working_days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
        "buffer_minutes": 30
    }
}' WHERE project_id = 'tu-project-id';
```

### **🏥 CONFIGURACIÓN MÉDICA**
```sql
-- Lunes a viernes, 9am-5pm, citas de 30 min
UPDATE agenda SET workflow_settings = '{
    "AGENDA_COMPLETA": {
        "default_duration_minutes": 30,
        "start_hour": 9,
        "end_hour": 17,
        "working_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "buffer_minutes": 10
    }
}' WHERE project_id = 'tu-project-id';
```

### **💰 CONFIGURACIÓN FINANCIERA (Tu caso)**
```sql
-- Lunes a viernes, 9am-6pm, citas de 60 min
UPDATE agenda SET workflow_settings = '{
    "AGENDA_COMPLETA": {
        "default_duration_minutes": 60,
        "start_hour": 9,
        "end_hour": 18,
        "working_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "buffer_minutes": 15,
        "auto_include_holidays_validation": true
    },
    "BUSQUEDA_HORARIOS": {
        "max_slots_to_show": 3,
        "search_weeks_ahead": 4,
        "exclude_weekends": true,
        "exclude_holidays": true
    }
}' WHERE project_id = '29ab2dc1-8790-4ef1-a9d4-f6d684b00572';
```

---

## 🔍 **VERIFICAR CONFIGURACIÓN ACTUAL**

### **Consultar configuración completa:**
```sql
SELECT 
    project_id,
    workflow_settings->'AGENDA_COMPLETA'->>'start_hour' as hora_inicio,
    workflow_settings->'AGENDA_COMPLETA'->>'end_hour' as hora_fin,
    workflow_settings->'AGENDA_COMPLETA'->>'default_duration_minutes' as duracion,
    workflow_settings->'AGENDA_COMPLETA'->'working_days' as dias_laborales,
    workflow_settings->'AGENDA_COMPLETA'->>'buffer_minutes' as buffer_minutos
FROM agenda 
WHERE project_id = '29ab2dc1-8790-4ef1-a9d4-f6d684b00572';
```

### **Resultado esperado:**
```
project_id | hora_inicio | hora_fin | duracion | dias_laborales | buffer_minutos
29ab2dc1-... | 9 | 18 | 60 | ["monday","tuesday","wednesday","thursday","friday"] | 15
```

---

## 🚀 **IMPLEMENTACIÓN EN CÓDIGO**

### **Para que tu `agenda_tool.py` use estas configuraciones, necesitas:**

1. **Modificar `_busqueda_horarios_workflow()` para leer configuración:**
```python
# Obtener configuración de horarios desde workflow_settings
workflow_settings = self._cached_project_config.get("workflow_settings", {})
agenda_settings = workflow_settings.get("AGENDA_COMPLETA", {})

start_hour = agenda_settings.get("start_hour", 9)
end_hour = agenda_settings.get("end_hour", 18)  
working_days = agenda_settings.get("working_days", ["monday", "tuesday", "wednesday", "thursday", "friday"])
buffer_minutes = agenda_settings.get("buffer_minutes", 15)
```

2. **Usar configuración en validaciones:**
```python
# Validar que el día solicitado esté en días laborales
if day_requested not in working_days:
    return f"❌ No trabajo los {day_requested}s. Días disponibles: {working_days}"

# Validar horarios laborales
if hour_requested < start_hour or hour_requested >= end_hour:
    return f"❌ Horario fuera de horario laboral ({start_hour}:00 - {end_hour}:00)"
```

---

## 📝 **PRÓXIMOS PASOS**

1. **Aplicar configuración:** Usar `INSERT_AGENDA_CON_HORARIOS.sql`
2. **Modificar código:** Implementar validaciones de horarios en `agenda_tool.py`
3. **Probar:** Verificar que respete días/horarios configurados
4. **Personalizar:** Ajustar según tus necesidades específicas

¿Te gustaría que implemente estas validaciones en tu `agenda_tool.py`? 🚀 