# 🗓️ Configuración Google Calendar LangChain Tool

## Descripción
Herramienta profesional de calendario basada en **CalendarToolkit de LangChain** que proporciona acceso completo a Google Calendar API con autenticación automática.

## ✨ Características Principales

- ✅ **Crear eventos** con invitados y Google Meet automático
- ✅ **Buscar eventos** por título, fecha o rango temporal
- ✅ **Actualizar eventos** existentes con nuevos datos
- ✅ **Eliminar eventos** de forma segura
- ✅ **Obtener información** de calendarios disponibles
- ✅ **Verificar disponibilidad** en tiempo real
- ✅ **Integración automática** con configuración del proyecto
- ✅ **Zona horaria** configurable por proyecto

## 🚀 Instalación

### 1. Instalar Dependencias

```bash
pip install langchain-google-community[calendar]
```

### 2. Configurar Google Calendar API

#### Paso 1: Crear Proyecto en Google Cloud Console

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita **Google Calendar API**:
   - Navega a "APIs & Services" > "Library"
   - Busca "Google Calendar API"
   - Haz clic en "Enable"

#### Paso 2: Crear Credenciales

1. Ve a "APIs & Services" > "Credentials"
2. Clic en "Create Credentials" > "OAuth 2.0 Client IDs"
3. Selecciona "Desktop application"
4. Descarga el archivo JSON como `credentials.json`
5. Coloca `credentials.json` en la raíz del proyecto

#### Paso 3: Configurar OAuth

```python
# El archivo credentials.json debe tener esta estructura:
{
  "installed": {
    "client_id": "tu-client-id.googleusercontent.com",
    "project_id": "tu-proyecto",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "tu-client-secret",
    "redirect_uris": ["http://localhost"]
  }
}
```

#### Paso 4: Primera Autenticación

En la primera ejecución, la herramienta abrirá automáticamente el navegador para autorizar el acceso. Esto creará un archivo `token.json` que se usará para futuras autenticaciones.

## 🔧 Configuración en el Proyecto

### 1. Habilitar la Herramienta

En la tabla `projects` de Supabase, agregar `"google_calendar_langchain"` al campo `enabled_tools`:

```json
{
  "enabled_tools": [
    "google_calendar_langchain",
    "other_tools"
  ]
}
```

### 2. Configurar Zona Horaria (Opcional)

En la tabla `agenda`, configurar la zona horaria en `general_settings`:

```json
{
  "general_settings": {
    "timezone": "America/Santiago"
  }
}
```

## 📋 Uso de la Herramienta

### Crear Evento

```python
google_calendar_langchain(
    action="create_event",
    summary="Reunión Cliente",
    start_datetime="2024-01-15T15:00:00",
    end_datetime="2024-01-15T16:00:00",
    timezone="America/Santiago",
    location="Oficina Principal",
    description="Reunión estratégica",
    attendees=["cliente@email.com", "otro@email.com"],
    reminders=[{"method": "popup", "minutes": 30}],
    include_meet=True,
    color_id="2"
)
```

### Buscar Eventos

```python
google_calendar_langchain(
    action="search_events",
    query="reunión",
    start_date="2024-01-15",
    end_date="2024-01-20",
    max_results=10
)
```

### Actualizar Evento

```python
google_calendar_langchain(
    action="update_event",
    event_id="abc123def456",
    summary="Nuevo título",
    description="Nueva descripción"
)
```

### Eliminar Evento

```python
google_calendar_langchain(
    action="delete_event",
    event_id="abc123def456"
)
```

### Obtener Información de Calendarios

```python
google_calendar_langchain(
    action="get_calendars_info"
)
```

### Obtener Fecha/Hora Actual

```python
google_calendar_langchain(
    action="get_current_datetime"
)
```

## 🎨 Colores de Eventos

Los eventos pueden tener diferentes colores usando `color_id`:

- `"1"` - Azul claro
- `"2"` - Verde 
- `"3"` - Púrpura
- `"4"` - Rosa
- `"5"` - Amarillo
- `"6"` - Naranja
- `"7"` - Turquesa
- `"8"` - Gris
- `"9"` - Azul oscuro
- `"10"` - Verde oscuro
- `"11"` - Rojo

## 🔒 Seguridad y Permisos

### Scopes Utilizados
- `https://www.googleapis.com/auth/calendar` - Acceso completo al calendario

### Archivos Sensibles
Asegúrate de que estos archivos NO estén en el control de versiones:

```gitignore
credentials.json
token.json
```

## 🐛 Solución de Problemas

### Error: "langchain-google-community no está disponible"
```bash
pip install langchain-google-community[calendar]
```

### Error: "Archivo de credenciales no encontrado"
- Verificar que `credentials.json` esté en la raíz del proyecto
- Verificar que el archivo tenga el formato correcto

### Error: "Error de autenticación"
- Eliminar `token.json` y volver a autenticar
- Verificar que las credenciales en `credentials.json` sean válidas
- Verificar que Google Calendar API esté habilitada

### Error: "CalendarToolkit no disponible"
- Verificar la instalación de dependencias
- Verificar conectividad a internet

## 📚 Integración con Otras Herramientas

Esta herramienta se integra automáticamente con:

- **AgendaTool**: Para workflows complejos de agendamiento
- **ContactTool**: Para obtener emails de contactos
- **EmailTool**: Para notificaciones
- **DatetimeTool**: Para validación de fechas

## 🎯 Casos de Uso Recomendados

1. **Agendamiento Rápido**: Crear eventos directamente desde el chat
2. **Consulta de Disponibilidad**: Verificar horarios libres
3. **Gestión de Reuniones**: Actualizar o cancelar eventos
4. **Sincronización**: Mantener calendarios actualizados
5. **Automatización**: Crear eventos desde otros workflows

## 📞 Soporte

Para problemas específicos con esta herramienta:

1. Verificar logs del sistema
2. Revisar configuración de Google Calendar API
3. Validar archivos de credenciales
4. Consultar documentación oficial de LangChain Google Community

---

**Nota**: Esta herramienta complementa las funcionalidades existentes de calendario en el proyecto, proporcionando una interfaz estandarizada basada en LangChain. 