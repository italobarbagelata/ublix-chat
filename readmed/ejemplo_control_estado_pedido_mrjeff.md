# 🔧 Ejemplo: Control de Estado del Pedido - Mr. Jeff

## 📋 Problema Identificado

El bot de Mr. Jeff estaba repitiendo el mensaje de confirmación del pedido cuando el cliente respondía después de completar un pedido. Esto violaba las reglas establecidas en las instrucciones.

### ❌ Comportamiento Anterior (Problemático):

```
Bot: ¡Tu pedido ha sido registrado exitosamente! 🎉
Cliente: No ninguno
Bot: ¡Tu pedido ha sido registrado exitosamente! 🎉  ← REPETICIÓN INCORRECTA
Cliente: No ninguno  
Bot: ¡Tu pedido ha sido registrado exitosamente! 🎉  ← REPETICIÓN INCORRECTA
```

## ✅ Solución Implementada

### 1. **Control de Estado con save_contact_tool**

Usar la herramienta `save_contact_tool` para mantener el estado del pedido en la conversación.

### 2. **Flujo Correcto Implementado**

#### **Paso 1: Después de Ejecutar la API "agregar prospecto"**
```python
# INMEDIATAMENTE después de ejecutar la API exitosamente
save_contact_tool(additional_fields='{"pedido_completado": true, "fecha_ultimo_pedido": "2025-07-02 13:16:00"}')

# Luego enviar el mensaje de confirmación
mensaje = """¡Tu pedido ha sido registrado exitosamente! 🎉

**Resumen de tu pedido:**
- Cubre cama de 2 plazas: $9.990 CLP
- Plumón de 1 plaza: $9.990 CLP (con retiro y entrega GRATIS)
..."""
```

#### **Paso 2: ANTES de Cualquier Intento de Ejecutar la API**
```python
# SIEMPRE verificar el estado antes de procesar pedidos
estado_cliente = save_contact_tool()  # Sin parámetros para verificar datos existentes

# Si encuentra pedido_completado: true
if "pedido_completado": true en estado_cliente:
    respuesta = "Perfecto, quedamos atentos. Si deseas hacer otro pedido o necesitas ayuda adicional, solo avísame."
    # NO ejecutar la API agregar prospecto
    # NO enviar mensaje de confirmación
```

#### **Paso 3: Manejo de Respuestas Post-Confirmación**
```python
# Cuando el cliente responde "gracias", "ok", "listo", etc.
if mensaje_cliente in ["gracias", "ok", "listo", "no ninguno", etc.]:
    if pedido_ya_completado:
        respuesta = "Perfecto, quedamos atentos. Si deseas hacer otro pedido o necesitas ayuda adicional, solo avísame."
    # NO repetir el mensaje de confirmación
```

## 🎯 Ejemplo de Conversación Corregida

### ✅ Comportamiento Correcto:

```
Bot: [Recolecta todos los datos del pedido]
Bot: [Ejecuta API "agregar prospecto"]
Bot: [Guarda estado: save_contact_tool(additional_fields='{"pedido_completado": true}')]
Bot: ¡Tu pedido ha sido registrado exitosamente! 🎉 [Mensaje completo de confirmación]

Cliente: No ninguno
Bot: [Verifica estado: encuentra pedido_completado: true]
Bot: Perfecto, quedamos atentos. Si deseas hacer otro pedido o necesitas ayuda adicional, solo avísame.

Cliente: Gracias
Bot: [Verifica estado: encuentra pedido_completado: true]  
Bot: Perfecto, quedamos atentos. Si deseas hacer otro pedido o necesitas ayuda adicional, solo avísame.
```

## 🔄 Manejo de Nuevos Pedidos

### **Cuando el Cliente Quiere un Nuevo Pedido:**

```
Cliente: Quiero hacer otro pedido diferente
Bot: [Detecta intención de nuevo pedido]
Bot: [Limpia estado: save_contact_tool(additional_fields='{"pedido_completado": false}')]
Bot: ¡Perfecto! ¿Qué prendas deseas lavar en este nuevo pedido?
[Reinicia el proceso completo]
```

### **Palabras Clave para Nuevo Pedido:**
- "nuevo pedido"
- "otro servicio"  
- "necesito lavar otras prendas"
- "quiero agregar más productos"
- Mención de productos/servicios diferentes

## 🚨 Reglas Críticas de Implementación

### ✅ **HACER:**
1. **Siempre verificar estado antes de ejecutar API**
2. **Guardar estado inmediatamente después de API exitosa**
3. **Responder con mensaje de cierre si ya hay pedido completado**
4. **Solo resetear estado si hay intención clara de nuevo pedido**

### ❌ **NO HACER:**
1. **NO repetir mensaje de confirmación**
2. **NO ejecutar API si pedido_completado: true**
3. **NO ignorar el estado del cliente**
4. **NO asumir que cualquier respuesta es nuevo pedido**

## 🔧 Código de Ejemplo para el Bot

```python
def procesar_mensaje_cliente(mensaje):
    # PASO 1: Verificar estado actual
    estado = save_contact_tool()  # Sin parámetros
    
    # PASO 2: Verificar si hay pedido completado
    if "pedido_completado" in estado and estado["pedido_completado"] == True:
        
        # PASO 3: Detectar si quiere nuevo pedido
        nuevos_pedido_keywords = ["nuevo pedido", "otro servicio", "más prendas", "diferente"]
        if any(keyword in mensaje.lower() for keyword in nuevos_pedido_keywords):
            # Limpiar estado y reiniciar
            save_contact_tool(additional_fields='{"pedido_completado": false}')
            return "¡Perfecto! ¿Qué prendas deseas lavar en este nuevo pedido?"
        else:
            # Mensaje de cierre
            return "Perfecto, quedamos atentos. Si deseas hacer otro pedido o necesitas ayuda adicional, solo avísame."
    
    # PASO 4: Si no hay pedido completado, procesar normalmente
    else:
        # [Lógica normal del pedido]
        if todos_los_datos_recolectados:
            # Ejecutar API
            resultado = api_agregar_prospecto(datos)
            if resultado.exitoso:
                # GUARDAR ESTADO INMEDIATAMENTE
                save_contact_tool(additional_fields='{"pedido_completado": true, "fecha_ultimo_pedido": "2025-07-02 13:16:00"}')
                # Enviar mensaje de confirmación UNA SOLA VEZ
                return mensaje_confirmacion_completo
```

## 🎯 Resultado Esperado

Con esta implementación, el bot:

1. ✅ **No repetirá** mensajes de confirmación
2. ✅ **Recordará** que ya completó un pedido 
3. ✅ **Responderá apropiadamente** a mensajes post-confirmación
4. ✅ **Permitirá nuevos pedidos** solo cuando se soliciten explícitamente
5. ✅ **Mantendrá la conversación fluida** sin loops infinitos

Esta solución resuelve completamente el problema reportado de repetición de mensajes y asegura que el bot siga las reglas de cierre establecidas en las instrucciones.

## 📝 Ejemplo Específico: Conversación de Marcela

### ❌ **Problema Detectado en Conversación Real:**

```
Bot: Necesito algunos datos. Por favor, envíame: Nombre, email, teléfono, medio de pago
Cliente: Marcela Villanueva, mvillanuevatoy@gmail.com, 965874779, Pago transferencia
Bot: Gracias, Marcela. Ahora... [continúa sin guardar los datos] ❌ ERROR
```

### ✅ **Conversación Corregida con Guardado de Datos:**

```
Bot: Necesito algunos datos. Por favor, envíame: Nombre, email, teléfono, medio de pago

Cliente: Marcela Villanueva, mvillanuevatoy@gmail.com, 965874779, Pago transferencia

Bot: [EJECUTA INMEDIATAMENTE]:
save_contact_tool(name="Marcela Villanueva", email="mvillanuevatoy@gmail.com", phone_number="965874779")

Bot: Gracias, Marcela. Ahora, por favor, indícame la dirección completa...

Cliente: Enrique gebhard 02185. Villa los arquitectos, Temuco

Bot: [EJECUTA INMEDIATAMENTE]:
save_contact_tool(additional_fields='{"direccion": "Enrique gebhard 02185. Villa los arquitectos, Temuco"}')

Bot: Perfecto. Ahora necesito la fecha de retiro...

Cliente: 03-07-2025, Tarde

Bot: Solo me falta el mensaje adicional...

Cliente: Ninguno

Bot: [ANTES DE EJECUTAR API, VERIFICA ESTADO]:
estado = save_contact_tool()  # Verificar si hay pedido completado

Bot: [Los datos básicos ya están guardados, los datos del pedido van directo a la API]

Bot: [EJECUTA API "agregar prospecto"]

Bot: [INMEDIATAMENTE DESPUÉS DE API EXITOSA]:
save_contact_tool(additional_fields='{"pedido_completado": true, "fecha_ultimo_pedido": "2025-07-03 13:35:00"}')

Bot: ¡Tu pedido ha sido registrado exitosamente! 🎉 [Mensaje completo]

Cliente: Gracias

Bot: [VERIFICA ESTADO - encuentra pedido_completado: true]
Bot: Perfecto, quedamos atentos. Si deseas hacer otro pedido o necesitas ayuda adicional, solo avísame.
```

## 🔧 Flujo de Guardado de Datos Implementado

### **1. Al Recibir Datos Básicos:**
```python
# Inmediatamente después de recibir nombre, email, teléfono
save_contact_tool(name="Marcela Villanueva", email="mvillanuevatoy@gmail.com", phone_number="965874779")
```

### **2. Al Recibir Dirección:**
```python
# Inmediatamente después de recibir la dirección completa
save_contact_tool(additional_fields='{"direccion": "Enrique gebhard 02185. Villa los arquitectos, Temuco"}')
```

### **3. Antes de Ejecutar API:**
```python
# Verificar estado
estado = save_contact_tool()
if "pedido_completado" in estado and estado["pedido_completado"] == True:
    return "Perfecto, quedamos atentos..."

# Los datos básicos ya están guardados
# Los datos del pedido van directo a la API
```

### **4. Después de API Exitosa:**
```python
# Guardar estado de pedido completado
save_contact_tool(additional_fields='{"pedido_completado": true, "fecha_ultimo_pedido": "2025-07-03 13:35:00"}')
```

## ✅ Beneficios de Esta Implementación

1. **✅ Datos de Contacto Persistentes:** Nombre, email, teléfono y dirección se guardan para reutilización
2. **✅ Control de Estado:** El bot recuerda si ya completó un pedido usando additional_fields  
3. **✅ Datos Esenciales:** Solo se guardan datos de contacto y control de estado
4. **✅ No Repetición:** El bot no repite mensajes de confirmación
5. **✅ Experiencia Fluida:** La conversación se cierra apropiadamente

Esta implementación guarda en additional_fields: **dirección** (contacto), **pedido_completado** y **fecha_ultimo_pedido** (control de estado).

## 🆕 Manejo de Conversaciones Nuevas vs Continuaciones

### ❌ **Problema Reportado:**

```
Usuario: hola
Bot: ¡Hola! Soy Mr. Jeff Temuco, tu asistente virtual. ¿Qué prendas deseas lavar hoy?
Usuario: Quisiera lavar nuevamente mi plumon
Bot: Veo que ya tienes un pedido registrado. ¿Deseas hacer un nuevo pedido diferente al anterior? ❌ INCORRECTO
Usuario: cual pedido ?
Usuario: por que si es una conversa nueva no hay pedidos ❌ USUARIO CONFUNDIDO
```

### ✅ **Comportamiento Corregido:**

#### **Escenario 1: Conversación Nueva (Mismo Día)**
```
Usuario: hola
Bot: ¡Hola! Soy Mr. Jeff Temuco, tu asistente virtual. ¿Qué prendas deseas lavar?

Usuario: Quisiera lavar mi plumón
Bot: [Verifica estado SOLO después de mencionar prendas]
Bot: [Encuentra pedido_completado: true del mismo día]
Bot: Veo que ya hiciste un pedido hoy. ¿Deseas hacer un nuevo pedido diferente?

Usuario: Sí, es otro plumón
Bot: [Resetea estado y continúa con nuevo pedido]
```

#### **Escenario 2: Conversación Nueva (Día Diferente)**
```
Usuario: hola
Bot: ¡Hola! Soy Mr. Jeff Temuco, tu asistente virtual. ¿Qué prendas deseas lavar?

Usuario: Quisiera lavar mi plumón
Bot: [Verifica estado]
Bot: [Encuentra pedido_completado: true pero de días anteriores]
Bot: [Ejecuta automáticamente]: save_contact_tool(additional_fields='{"pedido_completado": false}')
Bot: ¡Perfecto! ¿Qué tipo de plumón deseas lavar? [Continúa normalmente]
```

#### **Escenario 3: Continuación de Conversación (Mismo Día)**
```
Usuario: gracias
Bot: [Verifica estado - encuentra pedido_completado: true del mismo día]
Bot: Perfecto, quedamos atentos. Si deseas hacer otro pedido o necesitas ayuda adicional, solo avísame.
```

## 🔧 Lógica de Verificación Temporal

### **Criterios para Distinguir Conversaciones:**

#### ✅ **CONVERSACIÓN NUEVA:**
- Usuario saluda: "Hola", "Buenos días", etc.
- Usuario solicita servicio: "Quisiera lavar", "Necesito", etc.
- **→ NO verificar estado al inicio**
- **→ Solo verificar después de mencionar prendas**

#### ✅ **CONTINUACIÓN DE CONVERSACIÓN:**
- Usuario responde a preguntas del bot
- Usuario dice: "gracias", "ok", "listo", etc.
- **→ Verificar estado inmediatamente**

#### ✅ **VERIFICACIÓN TEMPORAL:**
- **Mismo día** (`fecha_ultimo_pedido` = hoy): Preguntar si quiere nuevo pedido
- **Días anteriores** (`fecha_ultimo_pedido` < hoy): Resetear estado automáticamente

## 📅 Ejemplo de Verificación de Fechas

```python
def verificar_estado_pedido():
    estado = save_contact_tool()
    
    if "pedido_completado" in estado and estado["pedido_completado"] == True:
        fecha_ultimo = estado.get("fecha_ultimo_pedido", "")
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        
        if fecha_ultimo.startswith(fecha_hoy):
            # Mismo día - preguntar si quiere nuevo pedido
            return "MISMO_DIA"
        else:
            # Días anteriores - resetear automáticamente
            save_contact_tool(additional_fields='{"pedido_completado": false}')
            return "DIAS_ANTERIORES"
    
    return "SIN_PEDIDO"
```

## ✅ Beneficios de la Corrección

1. **✅ Conversaciones Naturales:** No confunde al usuario con pedidos anteriores
2. **✅ Distinción Temporal:** Maneja pedidos del mismo día vs días anteriores
3. **✅ UX Mejorada:** Las conversaciones nuevas se sienten frescas
4. **✅ Control Inteligente:** Solo pregunta por pedidos anteriores cuando es relevante
5. **✅ Reseteo Automático:** Limpia el estado automáticamente para nuevos días

Esta corrección resuelve el problema de confusión del usuario al distinguir apropiadamente entre conversaciones nuevas y continuaciones.

## Ejemplo 4: Reutilización Automática de Datos de Contacto ✅

**Escenario:** Cliente que ya tiene datos guardados quiere hacer un nuevo pedido

```
Cliente: quiero hacer pedido
Bot: ¡Claro! ¿Qué prendas deseas lavar en este nuevo pedido?

Cliente: plumón 2 plazas sintético
Bot: Perfecto, has solicitado el lavado de un plumón sintético de 2 plazas.
¿Te gustaría agregar más prendas y continuar?

Cliente: no
Bot: Entendido. ¿Deseas el retiro a domicilio (gratis para plumones) o prefieres dejarlo en sucursal?

Cliente: domicilio
```

**🔧 Acción interna del bot:**
```
save_contact_tool() // Verifica datos existentes
```

**✅ Respuesta correcta:**
```
Bot: Perfecto. Usaré tus datos guardados (Italo - italo@email.com - 123456789).
¿Deseas usar la misma dirección "Pucon 1223, Santiago" o prefieres otra?

Cliente: la misma
Bot: Excelente. Ahora necesito estos datos para el nuevo pedido:
- Medio de pago (efectivo, transferencia, etc.)
- Fecha de retiro (formato DD-MM-YYYY)
- Horario (Mañana o Tarde)
- Mensaje adicional

Cliente: transferencia, 05-07-2025, tarde, sin mensaje
```

**📊 Lo que hace el bot:**
1. ✅ Reutiliza automáticamente nombre, email, teléfono, dirección
2. ✅ Solicita NUEVOS datos del pedido (medio de pago, fecha, horario)
3. ✅ NO reutiliza datos del pedido anterior

## Ejemplo 5: Error Común - Reutilizar Datos del Pedido ❌

**❌ Comportamiento INCORRECTO:**
```
Cliente: quiero hacer pedido  
Bot: Perfecto. Usando tus datos:
📅 Fecha de retiro: Mar 04-07-2025  ← ¡INCORRECTO!
🕐 Horario: Tarde                    ← ¡INCORRECTO!
```

**✅ Comportamiento CORRECTO:**
```
Cliente: quiero hacer pedido
Bot: ¡Claro! ¿Qué prendas deseas lavar en este nuevo pedido?
// ... proceso normal ...
Bot: Usaré tus datos guardados (Italo...). 
Ahora necesito la NUEVA fecha de retiro y horario para este pedido.
```

## Ejemplo 6: "Repetir Pedido" / "El Mismo Pedido" 🔄

**Escenario:** Cliente quiere repetir exactamente el mismo servicio

### ❌ **COMPORTAMIENTO INCORRECTO:**
```
Cliente: repetir pedido
Bot: Perfecto, procederé a registrar nuevamente el mismo pedido.

📋 Detalles del pedido:
- Prenda: Plumón sintético 2 plazas
- Fecha de retiro: 04-07-2025        ← ¡INCORRECTO!
- Horario de retiro: Tarde           ← ¡INCORRECTO!
- Dirección: Pucon 3333, Santiago
- Medio de pago: Transferencia       ← ¡INCORRECTO!
```

### ✅ **COMPORTAMIENTO CORRECTO:**
```
Cliente: repetir pedido
Bot: Perfecto, procederé con el mismo servicio (plumón sintético 2 plazas).

Usaré tus datos guardados (Italo - email - teléfono).
¿Deseas usar la misma dirección "Pucon 3333, Santiago"?

Cliente: sí
Bot: Excelente. Ahora necesito que me indiques para este nuevo pedido:
- Medio de pago (efectivo, transferencia, etc.)
- Fecha de retiro (formato DD-MM-YYYY) 
- Horario (Mañana o Tarde)
- Mensaje adicional

Cliente: transferencia, 06-07-2025, mañana, sin mensaje
```

### 📊 **Regla Clave:**
- **"El mismo pedido" = Mismos PRODUCTOS**
- **"El mismo pedido" ≠ Mismas FECHAS/HORARIOS**
- **SIEMPRE** solicitar nuevas fechas de retiro y entrega
- **SIEMPRE** solicitar nuevo medio de pago

## Ejemplo 7: Validación Correcta de Fechas Relativas ✅

**Escenario:** El cliente pide una fecha relativa como "el lunes". Hoy es Jueves 03-07-2025.

### ❌ **COMPORTAMIENTO INCORRECTO (El error que reportaste):**
```
Cliente: para el lunes en la tarde
Bot: 📅 Fecha: Lun 14-07-2025   ← ¡INCORRECTO! No validó, asumió una fecha errónea.
     🕐 Horario: Tarde

// ... luego se confunde al ser corregido
```

### ✅ **COMPORTAMIENTO CORRECTO (Con las nuevas instrucciones):**
```
Cliente: para el lunes en la tarde
```

**🔧 Acción interna del bot (ANTES de responder):**
1. `current_datetime_tool()` -> Obtiene fecha actual (Jueves 03-07-2025)
2. Resuelve "el lunes" -> Próximo lunes es 07-07-2025
3. `check_chile_holiday_tool(date="2025-07-07")` -> No es feriado
4. Valida día de la semana -> Es lunes (válido)
5. Valida fecha pasada -> 07-07-2025 no es pasado

**✅ Respuesta correcta:**
```
Bot: Perfecto. ¿Confirmamos el retiro para el próximo lunes 7 de julio en la tarde?
```

### 📊 **Regla Clave:**
- **VALIDAR PRIMERO, CONFIRMAR DESPUÉS.**
- El bot debe usar sus herramientas para calcular y validar la fecha *antes* de presentarla al usuario. Esto evita la confusión y los errores de cálculo. 

## Ejemplo 8: Validación de Agendamiento para Hoy (Límite 12 PM) ⏰

**Escenario:** El cliente quiere agendar para hoy, pero ya es la 1:30 PM.

### ❌ **COMPORTAMIENTO INCORRECTO:**
```
Cliente: ¿pueden retirar hoy mismo en la tarde?
Bot: Sí, claro. ¿Confirmamos para hoy en la tarde? ← ¡INCORRECTO! No validó la hora.
```

### ✅ **COMPORTAMIENTO CORRECTO:**
```
Cliente: ¿pueden retirar hoy mismo en la tarde?
```

**🔧 Acción interna del bot (ANTES de responder):**
1. `current_datetime_tool()` -> Obtiene fecha y hora actual (Jueves 03-07-2025 - 13:30)
2. Resuelve "hoy" -> 03-07-2025
3. **Validación de Agendamiento para Hoy:**
   - Fecha solicitada es "hoy" y hora actual (13:30) es después de las 11:59.
   - **Resultado:** Fecha NO VÁLIDA.

**✅ Respuesta correcta:**
```
Bot: Lo siento, ya hemos cerrado los retiros para hoy. 
Podemos agendar tu pedido para mañana viernes 4 de julio. ¿Te parece bien en la mañana o en la tarde?
```

### 📊 **Regla Clave:**
- La validación de la hora límite (11:59 AM) para agendamientos del mismo día es un paso **obligatorio e ineludible** en el flujo de validación de fechas. 