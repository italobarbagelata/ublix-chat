# 🚀 CONFIGURACIÓN GRANULAR DE HORARIOS - EJEMPLOS PRÁCTICOS

## 📋 **NUEVA ESTRUCTURA GRANULAR**

### **🎯 Cada día tiene configuración independiente:**
```json
{
  "monday": {
    "enabled": true,              // ¿Está activo este día?
    "time_slots": [               // Array de franjas horarias
      {
        "start": "08:00",         // Hora inicio (HH:MM)
        "end": "12:00",           // Hora fin (HH:MM)  
        "description": "Mañana"   // Descripción opcional
      },
      {
        "start": "13:00",         // Segunda franja
        "end": "19:00",
        "description": "Tarde"
      }
    ]
  }
}
```

---

## 💼 **EJEMPLOS DE CONFIGURACIÓN POR TIPO DE NEGOCIO**

### **1. 🏢 OFICINA CORPORATIVA (Tu caso - Maricunga)**
```sql
-- Lunes a viernes con descanso de almuerzo
UPDATE agenda SET workflow_settings = '{
    "AGENDA_COMPLETA": {
        "default_duration_minutes": 60,
        "buffer_minutes": 15,
        "schedule": {
            "monday": {
                "enabled": true,
                "time_slots": [
                    {"start": "09:00", "end": "12:30", "description": "Mañana"},
                    {"start": "13:30", "end": "18:00", "description": "Tarde"}
                ]
            },
            "tuesday": {
                "enabled": true,
                "time_slots": [
                    {"start": "09:00", "end": "12:30", "description": "Mañana"},
                    {"start": "13:30", "end": "18:00", "description": "Tarde"}
                ]
            },
            "wednesday": {
                "enabled": true,
                "time_slots": [
                    {"start": "09:00", "end": "12:30", "description": "Mañana"},
                    {"start": "13:30", "end": "18:00", "description": "Tarde"}
                ]
            },
            "thursday": {
                "enabled": true,
                "time_slots": [
                    {"start": "09:00", "end": "12:30", "description": "Mañana"},
                    {"start": "13:30", "end": "18:00", "description": "Tarde"}
                ]
            },
            "friday": {
                "enabled": true,
                "time_slots": [
                    {"start": "09:00", "end": "12:30", "description": "Mañana"},
                    {"start": "13:30", "end": "17:00", "description": "Tarde corta"}
                ]
            },
            "saturday": {"enabled": false, "time_slots": []},
            "sunday": {"enabled": false, "time_slots": []}
        }
    }
}' WHERE project_id = '29ab2dc1-8790-4ef1-a9d4-f6d684b00572';
```

### **2. 🏥 CONSULTA MÉDICA**
```sql
-- Horarios específicos con múltiples turnos
UPDATE agenda SET workflow_settings = '{
    "AGENDA_COMPLETA": {
        "default_duration_minutes": 30,
        "buffer_minutes": 10,
        "schedule": {
            "monday": {
                "enabled": true,
                "time_slots": [
                    {"start": "08:00", "end": "12:00", "description": "Turno mañana"},
                    {"start": "15:00", "end": "19:00", "description": "Turno tarde"}
                ]
            },
            "tuesday": {
                "enabled": true,
                "time_slots": [
                    {"start": "08:00", "end": "12:00", "description": "Turno mañana"},
                    {"start": "15:00", "end": "19:00", "description": "Turno tarde"}
                ]
            },
            "wednesday": {
                "enabled": true,
                "time_slots": [
                    {"start": "14:00", "end": "20:00", "description": "Solo tarde"}
                ]
            },
            "thursday": {
                "enabled": true,
                "time_slots": [
                    {"start": "08:00", "end": "12:00", "description": "Turno mañana"},
                    {"start": "15:00", "end": "19:00", "description": "Turno tarde"}
                ]
            },
            "friday": {
                "enabled": true,
                "time_slots": [
                    {"start": "08:00", "end": "14:00", "description": "Medio día"}
                ]
            },
            "saturday": {
                "enabled": true,
                "time_slots": [
                    {"start": "09:00", "end": "13:00", "description": "Urgencias"}
                ]
            },
            "sunday": {"enabled": false, "time_slots": []}
        }
    }
}' WHERE project_id = 'tu-project-id';
```

### **3. 👔 EJECUTIVO FLEXIBLE**
```sql
-- Horarios ejecutivos con días variables
UPDATE agenda SET workflow_settings = '{
    "AGENDA_COMPLETA": {
        "default_duration_minutes": 90,
        "buffer_minutes": 30,
        "schedule": {
            "monday": {
                "enabled": true,
                "time_slots": [
                    {"start": "07:00", "end": "20:00", "description": "Día completo"}
                ]
            },
            "tuesday": {
                "enabled": true,
                "time_slots": [
                    {"start": "09:00", "end": "13:00", "description": "Reuniones mañana"},
                    {"start": "15:00", "end": "18:00", "description": "Reuniones tarde"}
                ]
            },
            "wednesday": {
                "enabled": true,
                "time_slots": [
                    {"start": "14:00", "end": "19:00", "description": "Solo tarde"}
                ]
            },
            "thursday": {
                "enabled": true,
                "time_slots": [
                    {"start": "08:00", "end": "12:00", "description": "Presentaciones"},
                    {"start": "16:00", "end": "20:00", "description": "Reuniones ejecutivas"}
                ]
            },
            "friday": {
                "enabled": true,
                "time_slots": [
                    {"start": "10:00", "end": "15:00", "description": "Viernes reducido"}
                ]
            },
            "saturday": {
                "enabled": true,
                "time_slots": [
                    {"start": "10:00", "end": "14:00", "description": "Reuniones especiales"}
                ]
            },
            "sunday": {"enabled": false, "time_slots": []}
        }
    }
}' WHERE project_id = 'tu-project-id';
```

### **4. 🛍️ NEGOCIO COMERCIAL**
```sql
-- Horario comercial con sábados
UPDATE agenda SET workflow_settings = '{
    "AGENDA_COMPLETA": {
        "default_duration_minutes": 45,
        "buffer_minutes": 15,
        "schedule": {
            "monday": {
                "enabled": true,
                "time_slots": [
                    {"start": "10:00", "end": "14:00", "description": "Mañana"},
                    {"start": "16:00", "end": "22:00", "description": "Tarde/Noche"}
                ]
            },
            "tuesday": {
                "enabled": true,
                "time_slots": [
                    {"start": "10:00", "end": "22:00", "description": "Jornada completa"}
                ]
            },
            "wednesday": {
                "enabled": true,
                "time_slots": [
                    {"start": "10:00", "end": "22:00", "description": "Jornada completa"}
                ]
            },
            "thursday": {
                "enabled": true,
                "time_slots": [
                    {"start": "10:00", "end": "22:00", "description": "Jornada completa"}
                ]
            },
            "friday": {
                "enabled": true,
                "time_slots": [
                    {"start": "10:00", "end": "23:00", "description": "Viernes extendido"}
                ]
            },
            "saturday": {
                "enabled": true,
                "time_slots": [
                    {"start": "10:00", "end": "20:00", "description": "Sábado comercial"}
                ]
            },
            "sunday": {
                "enabled": true,
                "time_slots": [
                    {"start": "12:00", "end": "18:00", "description": "Domingo reducido"}
                ]
            }
        }
    }
}' WHERE project_id = 'tu-project-id';
```

### **5. 🎓 CENTRO EDUCATIVO**
```sql
-- Horarios de clases con recreos
UPDATE agenda SET workflow_settings = '{
    "AGENDA_COMPLETA": {
        "default_duration_minutes": 45,
        "buffer_minutes": 15,
        "schedule": {
            "monday": {
                "enabled": true,
                "time_slots": [
                    {"start": "08:00", "end": "10:30", "description": "Bloque 1"},
                    {"start": "11:00", "end": "12:30", "description": "Bloque 2"},
                    {"start": "14:00", "end": "17:00", "description": "Bloque 3"}
                ]
            },
            "tuesday": {
                "enabled": true,
                "time_slots": [
                    {"start": "08:00", "end": "10:30", "description": "Bloque 1"},
                    {"start": "11:00", "end": "12:30", "description": "Bloque 2"},
                    {"start": "14:00", "end": "17:00", "description": "Bloque 3"}
                ]
            },
            "wednesday": {
                "enabled": true,
                "time_slots": [
                    {"start": "08:00", "end": "10:30", "description": "Bloque 1"},
                    {"start": "11:00", "end": "12:30", "description": "Bloque 2"},
                    {"start": "14:00", "end": "17:00", "description": "Bloque 3"}
                ]
            },
            "thursday": {
                "enabled": true,
                "time_slots": [
                    {"start": "08:00", "end": "10:30", "description": "Bloque 1"},
                    {"start": "11:00", "end": "12:30", "description": "Bloque 2"},
                    {"start": "14:00", "end": "17:00", "description": "Bloque 3"}
                ]
            },
            "friday": {
                "enabled": true,
                "time_slots": [
                    {"start": "08:00", "end": "12:00", "description": "Medio día"}
                ]
            },
            "saturday": {"enabled": false, "time_slots": []},
            "sunday": {"enabled": false, "time_slots": []}
        }
    }
}' WHERE project_id = 'tu-project-id';
```

---

## 🛠️ **COMANDOS DE CONFIGURACIÓN GRANULAR**

### **Activar/Desactivar un día específico:**
```sql
-- Desactivar miércoles
UPDATE agenda SET workflow_settings = jsonb_set(
    workflow_settings, 
    '{AGENDA_COMPLETA,schedule,wednesday,enabled}', 
    'false'::jsonb
) WHERE project_id = 'tu-project-id';
```

### **Cambiar horarios de un día específico:**
```sql
-- Cambiar horarios del lunes
UPDATE agenda SET workflow_settings = jsonb_set(
    workflow_settings, 
    '{AGENDA_COMPLETA,schedule,monday,time_slots}', 
    '[
        {"start": "08:00", "end": "12:00", "description": "Mañana"},
        {"start": "14:00", "end": "20:00", "description": "Tarde extendida"}
    ]'::jsonb
) WHERE project_id = 'tu-project-id';
```

### **Agregar un día completamente nuevo:**
```sql
-- Activar sábados con horario especial
UPDATE agenda SET workflow_settings = jsonb_set(
    workflow_settings, 
    '{AGENDA_COMPLETA,schedule,saturday}', 
    '{
        "enabled": true,
        "time_slots": [
            {"start": "10:00", "end": "14:00", "description": "Sábado especial"}
        ]
    }'::jsonb
) WHERE project_id = 'tu-project-id';
```

---

## 🔍 **CONSULTAS DE VERIFICACIÓN**

### **Ver configuración completa de horarios:**
```sql
SELECT 
    project_id,
    jsonb_pretty(workflow_settings->'AGENDA_COMPLETA'->'schedule') as horarios_granulares
FROM agenda 
WHERE project_id = '29ab2dc1-8790-4ef1-a9d4-f6d684b00572';
```

### **Ver horarios de un día específico:**
```sql
SELECT 
    workflow_settings->'AGENDA_COMPLETA'->'schedule'->'monday' as horarios_lunes
FROM agenda 
WHERE project_id = '29ab2dc1-8790-4ef1-a9d4-f6d684b00572';
```

### **Ver todos los días activos:**
```sql
SELECT 
    day_name,
    day_config->'enabled' as activo,
    jsonb_array_length(day_config->'time_slots') as cantidad_franjas
FROM agenda a,
LATERAL jsonb_each(a.workflow_settings->'AGENDA_COMPLETA'->'schedule') AS t(day_name, day_config)
WHERE a.project_id = '29ab2dc1-8790-4ef1-a9d4-f6d684b00572'
ORDER BY 
    CASE day_name 
        WHEN 'monday' THEN 1 
        WHEN 'tuesday' THEN 2 
        WHEN 'wednesday' THEN 3 
        WHEN 'thursday' THEN 4 
        WHEN 'friday' THEN 5 
        WHEN 'saturday' THEN 6 
        WHEN 'sunday' THEN 7 
    END;
```

---

## 🎯 **VENTAJAS DE LA CONFIGURACIÓN GRANULAR**

### ✅ **Flexibilidad Total:**
- Horarios diferentes cada día
- Múltiples franjas por día (descansos)
- Control individual de días

### ✅ **Casos de Uso Reales:**
- **Almuerzo:** 8-12 y 13-18
- **Breaks:** 9-11, 11:30-13:30, 14-16
- **Días especiales:** Viernes corto, sábados reducidos
- **Horarios ejecutivos:** Flexibilidad total

### ✅ **Fácil Mantenimiento:**
- Cambiar un día sin afectar otros
- Activar/desactivar días específicos
- Agregar franjas según necesidad

🚀 **¡Con esta configuración granular puedes adaptarte a cualquier tipo de horario de trabajo!** 