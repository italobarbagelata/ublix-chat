# 🚀 Guía Completa: Contact Tool Dinámico

## 📋 Tabla de Contenidos
1. [Introducción](#introducción)
2. [Instalación y Configuración](#instalación-y-configuración)
3. [Campos Base vs Campos Dinámicos](#campos-base-vs-campos-dinámicos)
4. [Configuraciones por Tipo de Bot](#configuraciones-por-tipo-de-bot)
5. [Ejemplos Prácticos](#ejemplos-prácticos)
6. [Integración con Otras Herramientas](#integración-con-otras-herramientas)
7. [Casos de Uso Avanzados](#casos-de-uso-avanzados)

---

## 🎯 Introducción

La herramienta de contactos ahora es completamente **dinámica** y **personalizable**. Puedes:

✅ **Capturar campos base**: nombre, email, teléfono  
✅ **Agregar campos personalizados**: según tu tipo de negocio  
✅ **Extraer información automáticamente**: de conversaciones  
✅ **Configurar por tipo de bot**: inversiones, e-commerce, servicios, etc.

---

## ⚙️ Instalación y Configuración

### 1. Ejecutar Migración de Base de Datos
```sql
-- Ejecutar el archivo: add_additional_fields_to_contacts.sql
ALTER TABLE contacts 
ADD COLUMN IF NOT EXISTS additional_fields JSONB DEFAULT '{}';
```

### 2. Importar Funciones en tu Código
```python
from app.controler.chat.core.tools.contact_tool import (
    get_contact_async,
    save_contact_async, 
    extract_additional_fields_async,
    get_field_config_examples,
    SaveContactTool
)
```

---

## 📊 Campos Base vs Campos Dinámicos

### 🔹 Campos Base (Universales)
Estos campos funcionan para **cualquier tipo de bot**:
- `name`: Nombre completo del usuario
- `email`: Correo electrónico 
- `phone_number`: Número de teléfono

### 🔹 Campos Dinámicos (Personalizables)
Se guardan en `additional_fields` como JSON:

```json
{
  "direccion": "Santiago Centro",
  "edad": 35,
  "ha_invertido": true,
  "presupuesto": 1000000,
  "producto_interes": "Laptop Gaming"
}
```

---

## 🤖 Configuraciones por Tipo de Bot

### 💰 Bot de Inversiones
```python
config_inversiones = {
    "direccion": {
        "keywords": ["vivo en", "mi dirección", "dirección es", "domicilio"],
        "type": "string",
        "description": "Dirección de residencia"
    },
    "ciudad": {
        "keywords": ["ciudad", "vivo en", "de la ciudad"],
        "type": "string",
        "description": "Ciudad donde reside"
    },
    "edad": {
        "keywords": ["tengo", "años", "mi edad"],
        "type": "number",
        "description": "Edad del cliente"
    },
    "ha_invertido": {
        "keywords": ["he invertido", "inversión", "broker", "acciones"],
        "type": "boolean",
        "description": "Experiencia previa en inversiones"
    },
    "experiencia_inversion": {
        "keywords": ["experiencia", "años invirtiendo", "tiempo"],
        "type": "string",
        "description": "Tiempo de experiencia invirtiendo"
    }
}
```

### 🛒 Bot de E-commerce
```python
config_ecommerce = {
    "producto_interes": {
        "keywords": ["me interesa", "quiero", "busco", "necesito"],
        "type": "string",
        "description": "Producto de interés"
    },
    "presupuesto": {
        "keywords": ["presupuesto", "dispongo", "puedo pagar"],
        "type": "number",
        "description": "Presupuesto disponible"
    },
    "fecha_compra": {
        "keywords": ["cuando", "fecha", "para cuándo"],
        "type": "string",
        "description": "Fecha estimada de compra"
    },
    "metodo_pago": {
        "keywords": ["pago", "transferencia", "tarjeta", "efectivo"],
        "type": "string",
        "description": "Método de pago preferido"
    }
}
```

### 🔧 Bot de Servicios
```python
config_servicios = {
    "tipo_servicio": {
        "keywords": ["necesito", "servicio", "requiero", "busco"],
        "type": "string",
        "description": "Tipo de servicio requerido"
    },
    "urgencia": {
        "keywords": ["urgente", "pronto", "rápido", "cuando"],
        "type": "string",
        "description": "Nivel de urgencia"
    },
    "disponibilidad": {
        "keywords": ["disponible", "horario", "puede", "prefiero"],
        "type": "string",
        "description": "Disponibilidad horaria"
    }
}
```

---

## 💡 Ejemplos Prácticos

### 📝 Caso 1: Captura Básica de Información
```python
# Usuario dice: "Hola, soy Juan Pérez, mi email es juan@gmail.com"

# En tu bot:
tool = SaveContactTool(project_id="proj_123", user_id="user_456")
result = tool._run(name="Juan Pérez", email="juan@gmail.com")
```

### 📝 Caso 2: Campos Personalizados para Bot de Inversiones
```python
# Usuario dice: "Tengo 35 años, vivo en Santiago y ya he invertido antes"

# Opción A: Manual
tool._run(additional_fields='{"edad": 35, "ciudad": "Santiago", "ha_invertido": true}')

# Opción B: Extracción Automática  
config = '{"edad": {"keywords": ["tengo", "años"], "type": "number"}, "ciudad": {"keywords": ["vivo en"], "type": "string"}, "ha_invertido": {"keywords": ["he invertido"], "type": "boolean"}}'

tool._run(
    conversation_text="Tengo 35 años, vivo en Santiago y ya he invertido antes",
    field_config=config
)
```

### 📝 Caso 3: Bot de E-commerce
```python
# Usuario dice: "Busco una laptop, mi presupuesto es 500mil, la necesito para marzo"

tool._run(additional_fields='{"producto_interes": "laptop", "presupuesto": 500000, "fecha_compra": "marzo"}')
```

### 📝 Caso 4: Actualización Incremental
```python
# Primero guardar info básica
tool._run(name="María López", email="maria@email.com")

# Después agregar campos específicos
tool._run(additional_fields='{"direccion": "Valparaíso", "urgencia": "alta"}')

# Los datos se combinan automáticamente, no se sobrescriben
```

---

## 🔄 Integración con Otras Herramientas

### 📧 Con Email Tool
```python
# La herramienta de email puede usar automáticamente el email guardado
contact = get_contact_sync("proj_123", "user_456")
if contact and contact.get('email'):
    # Enviar email personalizado con nombre
    send_email(
        to=contact['email'], 
        subject=f"Hola {contact['name']}", 
        content="..."
    )
```

### 📅 Con Calendar Tool
```python
# El calendario usa automáticamente el email del contacto
calendar_tool = GoogleCalendarTool(project_id, user_id)
# Internamente obtiene el email del contacto para invitaciones
```

### 🔌 Con API Tools
```python
# Las APIs pueden usar información del contacto
contact = get_contact_sync("proj_123", "user_456")
additional = contact.get('additional_fields', {})

# Ejemplo: API de CRM con datos del lead
api_data = {
    "name": contact.get('name'),
    "email": contact.get('email'),
    "budget": additional.get('presupuesto'),
    "product_interest": additional.get('producto_interes')
}
```

---

## 🎯 Casos de Uso Avanzados

### 🔍 Caso 1: Lead Scoring Automático
```python
async def calculate_lead_score(project_id: str, user_id: str) -> int:
    contact = await get_contact_async(project_id, user_id)
    if not contact:
        return 0
    
    score = 0
    additional = contact.get('additional_fields', {})
    
    # Puntuación por completitud de datos
    if contact.get('name'): score += 10
    if contact.get('email'): score += 15
    if contact.get('phone_number'): score += 15
    
    # Puntuación por campos específicos (bot de inversiones)
    if additional.get('ha_invertido'): score += 20
    if additional.get('presupuesto', 0) > 1000000: score += 25
    if additional.get('urgencia') == 'alta': score += 15
    
    return score
```

### 🔍 Caso 2: Segmentación Automática
```python
def segment_contact(contact: dict) -> str:
    additional = contact.get('additional_fields', {})
    
    # Bot de inversiones
    if additional.get('ha_invertido') and additional.get('presupuesto', 0) > 5000000:
        return "INVERSOR_VIP"
    elif additional.get('ha_invertido'):
        return "INVERSOR_EXPERIMENTADO"
    elif additional.get('edad', 0) < 30:
        return "JOVEN_PRINCIPIANTE"
    else:
        return "POTENCIAL_CLIENTE"
```

### 🔍 Caso 3: Personalización Dinámica de Respuestas
```python
def personalize_response(contact: dict, base_message: str) -> str:
    name = contact.get('name', 'usuario')
    additional = contact.get('additional_fields', {})
    
    # Personalizar por experiencia
    if additional.get('ha_invertido'):
        return f"Hola {name}, veo que ya tienes experiencia invirtiendo. Te recomiendo..."
    else:
        return f"Hola {name}, como eres nuevo en inversiones, te sugiero empezar con..."
```

---

## 🚨 Consideraciones Importantes

### ✅ Buenas Prácticas
- **Validar datos**: Siempre verificar que los campos adicionales sean JSON válido
- **Campos consistentes**: Usar los mismos nombres de campos en todo el proyecto
- **Tipos apropiados**: string, number, boolean según corresponda
- **Keywords relevantes**: Usar palabras clave que realmente aparezcan en conversaciones

### ⚠️ Limitaciones
- Los campos adicionales se guardan como JSON, no como columnas SQL nativas
- La extracción automática depende de palabras clave, no es 100% precisa
- Se recomienda validar información crítica con el usuario

### 🔧 Troubleshooting
```python
# Verificar configuración de campos
examples = get_field_config_examples()
print(examples['bot_inversiones'])

# Verificar contacto existente
contact = get_contact_sync("proj_123", "user_456")
print(json.dumps(contact, indent=2))

# Probar extracción
service = ContactService()
result = service.extract_additional_fields_with_llm(
    "texto de prueba", 
    {"edad": {"keywords": ["años"], "type": "number"}}
)
print(result)
```

---

## 🎉 ¡Listo para Usar!

Tu herramienta de contactos ahora es súper poderosa y flexible. Puedes:

1. **Configurar campos específicos** para tu tipo de negocio
2. **Extraer información automáticamente** de conversaciones  
3. **Integrar con otras herramientas** del sistema
4. **Personalizar respuestas** según el perfil del usuario
5. **Hacer seguimiento avanzado** de leads y conversiones

¡Empieza a capturar leads de manera inteligente! 🚀 