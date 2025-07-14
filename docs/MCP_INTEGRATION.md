# Infraestructura MCP (Model Context Protocol)

## Descripción

Este sistema incluye una infraestructura completa para integrar servidores MCP futuros. La implementación inicial de Google Calendar fue removida en favor de la herramienta nativa `calendar_tool.py`, pero la infraestructura MCP permanece lista para futuras integraciones.

## Arquitectura

### Componentes Principales

1. **MCPClient** (`app/controler/chat/core/tools/mcp_client.py`)
   - Cliente base para conectar con servidores MCP
   - Maneja comunicación stdio con servidores externos

2. **MCPToolFactory** (`app/controler/chat/core/tools/mcp_tool_factory.py`)
   - Factory para crear y gestionar herramientas MCP
   - Maneja ciclo de vida de conexiones MCP
   - Incluye templates para futuras herramientas

3. **Configuración MCP** (`app/controler/chat/config/mcp_config.py`)
   - Configuraciones de servidores MCP disponibles
   - Templates para nuevos servidores MCP

## Estado Actual

### Google Calendar
❌ **MCP Google Calendar removido** - Se mantiene la herramienta nativa `calendar_tool.py` que ofrece:
- Integración completa con configuración de proyecto
- Optimización para zona horaria de Chile
- Detección de conflictos y creación de Google Meet
- Sin dependencias externas

### Infraestructura MCP
✅ **Infraestructura MCP mantenida** para futuras integraciones:
- Cliente MCP base funcional
- Factory de herramientas escalable 
- Sistema de configuración preparado
- Templates para nuevos servidores

## Agregar Nuevos Servidores MCP

### 1. Configurar Servidor

Agregar configuración en `app/controler/chat/config/mcp_config.py`:

```python
MCP_SERVERS_CONFIG = {
    "github": {
        "name": "github-mcp-server",
        "command": "npx",
        "args": ["-y", "@github/mcp-server"],
        "env": {"GITHUB_TOKEN": "your_token"},
        "description": "Servidor MCP para GitHub",
        "tools": ["create_issue", "list_repos", "create_pr"]
    }
}
```

### 2. Crear Herramienta

Crear nueva herramienta en `app/controler/chat/core/tools/`:

```python
class GitHubMCPTool(BaseTool):
    name: str = "github_mcp"
    description: str = "Herramienta GitHub vía MCP"
    args_schema: type[BaseModel] = GitHubMCPInput
    
    # Implementar métodos _run y _arun
```

### 3. Actualizar Factory

Agregar soporte en `MCPToolFactory._create_mcp_tool()`:

```python
if tool_type == "github":
    tool = await self._create_github_tool(project_id)
    if tool:
        self.created_tools[tool_type] = tool
    return tool
```

### 4. Habilitar en Proyecto

```python
project.enabled_tools = ["api", "calendar", "mcp_github", ...]
```

## Servidores MCP Recomendados

### Herramientas Populares
- **GitHub MCP Server**: Gestión de repositorios, issues, PRs
- **Slack MCP Server**: Comunicación y notificaciones
- **Database MCP Server**: Consultas SQL y gestión de BD
- **File System MCP Server**: Operaciones de archivos
- **Jira MCP Server**: Gestión de proyectos y tickets

### Ejemplo de Implementación Completa

```python
# 1. Configuración del servidor
MCP_SERVERS_CONFIG = {
    "jira": {
        "name": "jira-mcp-server",
        "command": "python",
        "args": ["-m", "jira_mcp_server"],
        "env": {
            "JIRA_URL": "https://company.atlassian.net",
            "JIRA_TOKEN": "your_api_token"
        },
        "description": "Servidor MCP para Jira",
        "tools": ["create_ticket", "update_ticket", "search_tickets"]
    }
}

# 2. Herramienta específica
class JiraMCPTool(BaseTool):
    name: str = "jira_mcp"
    description: str = "Gestión de tickets Jira vía MCP"
    
    async def _arun(self, action: str, **kwargs) -> str:
        # Lógica específica de Jira
        pass

# 3. Integración en factory
async def _create_jira_tool(self, project_id: str):
    server_config = get_mcp_server_config("jira")
    # ... lógica de creación
    return JiraMCPTool()
```

## Monitoreo y Health Check

### Verificar Estado MCP

```python
from app.controler.chat.core.tools.mcp_tool_factory import get_mcp_tool_factory

factory = get_mcp_tool_factory()
health = await factory.health_check()
print(health)
# Output: {"server_name": {"connected": True, "tools_available": 5}}
```

### Logs del Sistema

```python
# Conexión MCP
"Conectando al servidor MCP: server-name"
"Conectado exitosamente al servidor MCP"

# Carga de herramientas
"Cargadas N herramientas del servidor MCP"
"Herramientas MCP habilitadas: ['tool_name']"

# Ejecución de herramientas
"Ejecutando herramienta MCP: action_name"
```

## Resolución de Problemas

### Error de Dependencias

1. Verificar que el comando del servidor esté disponible
2. Instalar dependencias necesarias (Node.js, Python, etc.)
3. Configurar PATH correctamente

### Error de Conexión MCP

1. Verificar que el servidor MCP esté funcionando
2. Comprobar logs para errores específicos
3. Revisar configuración de variables de entorno

### Timeout de Servidor

1. Verificar conectividad de red
2. Aumentar timeout en la configuración
3. Comprobar que el servidor responda correctamente

## Archivos de Infraestructura

### Archivos Mantenidos
- `app/controler/chat/core/tools/mcp_client.py` - Cliente MCP base
- `app/controler/chat/core/tools/mcp_tool_factory.py` - Factory de herramientas
- `app/controler/chat/config/mcp_config.py` - Configuraciones
- `docs/MCP_INTEGRATION.md` - Esta documentación

### Uso de Memoria
La infraestructura MCP está optimizada para:
- Reutilización de conexiones
- Cache de herramientas creadas
- Cleanup automático de recursos
- Manejo eficiente de múltiples servidores