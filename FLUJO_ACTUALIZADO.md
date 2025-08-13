🔄 RESUMEN DEL FLUJO ACTUALIZADO PARA MARICUNGA

El bot debe seguir este orden OBLIGATORIO:

## FLUJO CORRECTO:

1. **Usuario dice "Hola"** 
   → Bot: [saludo inicial] + "¿Estarías interesado en saber más?"

2. **Usuario dice "Sí"**
   → Bot: [información detallada del proyecto] + "¿te parece tener una reunión?"

3. **Usuario dice "Sí" (a la reunión)**
   → Bot: "¡Perfecto! Te muestro los horarios disponibles..."
   → Ejecuta: agenda_tool(workflow_type="BUSQUEDA_HORARIOS")
   → Muestra horarios numerados

4. **Usuario elige horario (ej: "el 2")**
   → Bot: "Excelente elección! Para confirmar tu reunión para [FECHA], necesito algunos datos..."
   → Pide: Nombre, Ciudad, Teléfono, Mail, Profesión, Experiencia de inversión

5. **Usuario da sus datos**
   → Bot: [confirma datos] + agenda la cita

## ❌ ERROR ACTUAL:
El bot está saltándose el paso 3 y pidiendo datos antes de mostrar horarios.

## ✅ SOLUCIÓN:
Seguir EXACTAMENTE el orden: Saludo → Información → HORARIOS → Datos → Confirmar

⚠️ NUNCA pedir datos antes de mostrar los horarios disponibles.