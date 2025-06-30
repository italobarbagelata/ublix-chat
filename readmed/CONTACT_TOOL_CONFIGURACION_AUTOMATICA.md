# 🤖 Contact Tool - Configuración Automática

## Resumen

La herramienta de contactos ahora soporta **configuración automática de campos por proyecto** usando la tabla `contact_field_configs`. Esto elimina la necesidad de especificar manualmente `field_config` en cada conversación.

## 🆚 Antes vs Después

### ❌ ANTES (Manual)
```python
save_contact_tool(
    conversation_text="Hola, tengo 30 años y vivo en Santiago",
    field_config='{"edad": {"keywords": ["tengo", "años"], "type": "number"}, "ciudad": {"keywords": ["vivo en"], "type": "string"}}'
)
```

### ✅ DESPUÉS (Automático)
```python
save_contact_tool(
    conversation_text="Hola, tengo 30 años y vivo en Santiago",
    auto_extract=true
)
```

## 🏗️ Arquitectura de la Solución

### 1. Tabla `contact_field_configs`

Almacena la configuración de campos por proyecto:

```sql
CREATE TABLE contact_field_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    field_name VARCHAR(255) NOT NULL,
    keywords JSONB NOT NULL DEFAULT '[]',
    field_type VARCHAR(50) NOT NULL CHECK (field_type IN ('string', 'number', 'boolean')),
    description TEXT,
    enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 2. Funciones SQL Utilitarias

- `get_contact_field_config(project_uuid)`: Obtiene configuración como JSON
- `add_contact_field(...)`: Agrega/actualiza un campo
- Triggers automáticos para `updated_at`

### 3. Nuevos Métodos en ContactService

- `get_project_field_config()`: Lee configuración desde BD
- `auto_extract_from_conversation()`: Extrae campos automáticamente

### 4. Función Async Nueva

- `auto_extract_fields_async()`: Función independiente para extracción automática

## 📋 Pasos de Implementación

### Paso 1: Crear la Tabla
```bash
# Ejecutar en tu base de datos PostgreSQL
psql -d tu_base_datos -f create_contact_field_configs_table.sql
```

### Paso 2: Configurar Campos para tu Proyecto

#### Para Bot de Inversiones:
```sql
SELECT add_contact_field(
    'tu-project-id'::UUID,
    'edad',
    '["tengo", "años", "mi edad es"]'::JSONB,
    'number',
    'Edad del cliente'
);

SELECT add_contact_field(
    'tu-project-id'::UUID,
    'presupuesto',
    '["presupuesto", "capital", "dispongo", "millones"]'::JSONB,
    'number',
    'Capital disponible para invertir'
);

SELECT add_contact_field(
    'tu-project-id'::UUID,
    'ha_invertido',
    '["he invertido", "experiencia", "broker", "acciones"]'::JSONB,
    'boolean',
    'Experiencia previa en inversiones'
);
```

#### Para Bot de E-commerce:
```sql
SELECT add_contact_field(
    'tu-project-id'::UUID,
    'producto_interes',
    '["me interesa", "quiero", "busco", "necesito"]'::JSONB,
    'string',
    'Producto de interés'
);

SELECT add_contact_field(
    'tu-project-id'::UUID,
    'presupuesto',
    '["presupuesto", "puedo pagar", "precio máximo"]'::JSONB,
    'number',
    'Presupuesto disponible'
);
```

### Paso 3: Usar la Herramienta

#### 🔥 MODO AUTOMÁTICO (Recomendado):
```python
save_contact_tool(
    conversation_text="Hola, soy María, tengo 35 años. He invertido antes y tengo 5 millones disponibles.",
    auto_extract=true
)
```

#### 🔧 MODO MANUAL (Fallback):
```python
save_contact_tool(
    conversation_text="Hola, soy María, tengo 35 años...",
    field_config='{"edad": {"keywords": ["tengo", "años"], "type": "number"}}'
)
```

## 📊 Configuraciones Predefinidas

### Bot de Inversiones
- **edad**: `["tengo", "años"]` (number)
- **direccion**: `["vivo en", "mi dirección"]` (string)
- **ha_invertido**: `["he invertido", "experiencia"]` (boolean)
- **presupuesto**: `["capital", "millones"]` (number)
- **tolerancia_riesgo**: `["conservador", "agresivo", "moderado"]` (string)

### Bot de E-commerce
- **producto_interes**: `["me interesa", "quiero", "busco"]` (string)
- **presupuesto**: `["presupuesto", "puedo pagar"]` (number)
- **fecha_compra**: `["para cuándo", "necesito"]` (string)
- **metodo_pago**: `["pago", "cuotas", "contado"]` (string)

### Bot de Servicios
- **tipo_servicio**: `["necesito", "servicio", "requiero"]` (string)
- **urgencia**: `["urgente", "pronto", "rápido"]` (string)
- **presupuesto**: `["presupuesto", "cuesta"]` (number)
- **disponibilidad**: `["disponible", "horario"]` (string)

## 🛠️ Gestión de Configuración

### Ver Configuración Actual
```sql
SELECT * FROM contact_field_configs 
WHERE project_id = 'tu-project-id' 
ORDER BY priority;
```

### Obtener como JSON (para usar en código)
```sql
SELECT get_contact_field_config('tu-project-id'::UUID);
```

### Deshabilitar un Campo
```sql
UPDATE contact_field_configs 
SET enabled = false 
WHERE project_id = 'tu-project-id' AND field_name = 'direccion';
```

### Cambiar Prioridad
```sql
UPDATE contact_field_configs 
SET priority = 10 
WHERE project_id = 'tu-project-id' AND field_name = 'presupuesto';
```

### Actualizar Keywords
```sql
UPDATE contact_field_configs 
SET keywords = '["tengo", "años", "mi edad", "soy de"]'::JSONB
WHERE project_id = 'tu-project-id' AND field_name = 'edad';
```

## 🔄 Flujo de Trabajo

1. **Usuario envía mensaje**: "Hola, tengo 30 años y vivo en Santiago"
2. **Herramienta detecta** `auto_extract=true`
3. **Lee configuración** desde `contact_field_configs` para el proyecto
4. **Extrae campos** usando LLM con las keywords configuradas
5. **Guarda automáticamente** los campos extraídos
6. **Combina con información existente** sin sobrescribir

## ✅ Beneficios

- **🚀 Simplicidad**: Solo necesitas `auto_extract=true`
- **🔧 Flexibilidad**: Configuración por proyecto en BD
- **📈 Escalabilidad**: No requiere cambios de código para nuevos campos
- **🔄 Reutilización**: Misma configuración para todas las conversaciones
- **🎯 Precisión**: Keywords específicas por tipo de bot
- **⚡ Performance**: Consulta optimizada con índices

## 🚨 Respuesta a tu Pregunta

> "¿Cómo la herramienta sabe qué datos extras guardar automáticamente?"

**AHORA SÍ LO SABE** 🎉

Con la tabla `contact_field_configs`:
1. Cada proyecto tiene su configuración persistente
2. La herramienta consulta automáticamente qué campos capturar
3. Usa las keywords configuradas para extraer información
4. Todo funciona sin especificar `field_config` manualmente

## 📁 Archivos Creados/Modificados

- ✅ `create_contact_field_configs_table.sql` - Tabla y funciones
- ✅ `contact_service.py` - Métodos de configuración automática
- ✅ `contact_tool.py` - Parámetro `auto_extract` y lógica
- ✅ `ejemplo_uso_contact_tool_automatico.py` - Ejemplos completos
- ✅ `CONTACT_TOOL_CONFIGURACION_AUTOMATICA.md` - Esta documentación

## 🎯 Conclusión

**Sí, con la tabla `contact_field_configs` es suficiente** para hacer la herramienta completamente automática. Ya no necesitas especificar configuraciones manualmente - todo se maneja desde la base de datos por proyecto. 🚀 