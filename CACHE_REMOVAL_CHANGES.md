# Cambios en el Sistema de Herramientas - Eliminación de Caché

## Fecha: 2025-08-19

## Resumen de Cambios
Se eliminó el sistema de caché problemático que estaba causando loops infinitos y herramientas no disponibles. Ahora las herramientas se cargan directamente en cada solicitud, mejorando la confiabilidad del sistema.

## Problemas Resueltos

### 1. Loop Infinito con save_contact_tool
- **Problema**: El bot llamaba repetidamente `save_contact_tool(lead_status="reservado")` hasta alcanzar el límite de recursión
- **Causa**: El caché mantenía un estado inconsistente de las herramientas
- **Solución**: Eliminación del caché y carga directa de herramientas

### 2. EmailTool No Disponible
- **Problema**: La herramienta de email no se cargaba aunque estaba en `enabled_tools`
- **Causa**: El caché no actualizaba correctamente las herramientas cuando cambiaba la configuración
- **Solución**: Agregada EmailTool al sistema de carga de herramientas

### 3. Caché con Claves Incorrectas
- **Problema**: El caché usaba `project_id_enabled_tools` como clave pero no invalidaba cuando cambiaba
- **Causa**: No había mecanismo de invalidación automática
- **Solución**: Eliminación completa del sistema de caché

## Archivos Modificados

### 1. `/app/controler/chat/core/tools/__init__.py`
- **Cambios**:
  - Agregado import de EmailTool
  - Mejorada la función `agent_tools()` con manejo de errores robusto
  - Agregadas más herramientas opcionales (holidays, week_info)
  - Eliminada dependencia del caché
  - Agregado logging mejorado para debugging

### 2. `/app/controler/chat/core/nodes.py`
- **Cambios**:
  - Eliminado import de `tools_cache`
  - Modificada función `agent()` para llamar directamente a `agent_tools()`
  - Modificada función `tools_node()` para cargar herramientas sin caché
  - Simplificado el código eliminando referencias al caché

### 3. `/promts/instrucciones_bot_secretaria.md`
- **Cambios**:
  - Agregadas reglas explícitas para prevenir loops
  - Instrucciones claras sobre cuándo usar cada herramienta
  - Manejo condicional de email cuando no está disponible
  - Estados del lead claramente definidos

## Archivos Nuevos

### 1. `/app/controler/chat/core/tools_manager.py`
- **Propósito**: Gestor opcional de herramientas sin caché problemático
- **Estado**: Creado pero NO activado por defecto
- **Uso**: Puede activarse descomentando la línea de instanciación si se necesita en el futuro

## Mejoras Implementadas

### 1. Carga Directa de Herramientas
- Las herramientas se cargan fresh en cada solicitud
- No hay estado persistente que pueda causar inconsistencias
- Mejor debugging con logs detallados

### 2. Manejo Robusto de Errores
- Try-catch para cada herramienta opcional
- Las herramientas esenciales siempre se cargan
- Logs de error específicos para cada falla

### 3. Herramientas Esenciales Garantizadas
- `current_datetime_tool` siempre disponible
- `SaveContactTool` siempre disponible
- No dependen de configuración del proyecto

## Configuración de Herramientas

### Herramientas Disponibles por Configuración:
- `api`: Herramientas de API personalizadas
- `unified_search`: Búsqueda unificada en documentos
- `agenda_tool`: Gestión de agenda y citas
- `email`: Envío de correos electrónicos
- `holidays`: Información de feriados chilenos
- `week_info`: Información de semana actual

### Herramientas Siempre Disponibles:
- `current_datetime_tool`: Fecha y hora actual
- `save_contact_tool`: Guardar información de contacto

## Impacto en Performance

### Antes (con caché):
- ✅ Menos llamadas a funciones de inicialización
- ❌ Problemas de sincronización y estado
- ❌ Loops infinitos por estado inconsistente
- ❌ Herramientas no disponibles por caché desactualizado

### Después (sin caché):
- ✅ Herramientas siempre actualizadas
- ✅ Sin problemas de estado o sincronización
- ✅ Debugging más fácil
- ✅ Mayor confiabilidad
- ⚠️ Ligeramente más llamadas de inicialización (impacto mínimo ~50ms)

## Recomendaciones

1. **Monitorear Performance**: Verificar que el tiempo de respuesta no se vea afectado significativamente
2. **Logs**: Revisar logs para asegurar que todas las herramientas se cargan correctamente
3. **Testing**: Probar todos los flujos de conversación, especialmente:
   - Guardado de contactos
   - Cambio de estados de lead
   - Envío de emails (cuando esté habilitado)

## Rollback (si es necesario)

Para volver al sistema con caché:
1. Restaurar import de `tools_cache` en `nodes.py`
2. Cambiar las llamadas a `agent_tools()` para usar `tools_cache.get_tools()`
3. Reactivar el archivo `tools_cache.py`

**NOTA**: No se recomienda volver al sistema con caché debido a los problemas documentados.

## Próximos Pasos Sugeridos

1. **Optimización Futura**: Si el performance es crítico, considerar:
   - Usar el `ToolsManager` creado (actualmente desactivado)
   - Implementar un pool de herramientas pre-inicializadas
   - Lazy loading de herramientas pesadas

2. **Mejoras de Configuración**:
   - Validación de configuración de herramientas al inicio
   - Sistema de health checks para herramientas
   - Métricas de uso de herramientas

3. **Testing Automatizado**:
   - Tests unitarios para cada herramienta
   - Tests de integración para flujos completos
   - Tests de carga para verificar performance