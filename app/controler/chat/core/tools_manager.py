"""
Gestor de herramientas simplificado sin caché
Mantiene las herramientas cargadas en memoria para mejorar el rendimiento
"""
import logging
from typing import Dict, List, Any, Optional
from app.controler.chat.store.persistence import Project

logger = logging.getLogger(__name__)

class ToolsManager:
    """
    Gestor simplificado de herramientas.
    Carga las herramientas una vez por proyecto y las mantiene en memoria.
    """
    
    def __init__(self):
        self._tools_by_project: Dict[str, List[Any]] = {}
        self._project_configs: Dict[str, List[str]] = {}
    
    async def get_tools(
        self, 
        project_id: str, 
        user_id: str,
        name: str,
        number_phone_agent: str,
        unique_id: str,
        project: Project,
        force_reload: bool = False
    ) -> List[Any]:
        """
        Obtiene las herramientas para un proyecto.
        Si force_reload es True o la configuración cambió, recarga las herramientas.
        """
        from app.controler.chat.core.tools import agent_tools
        
        current_config = project.enabled_tools if project else []
        
        # Verificar si necesitamos recargar las herramientas
        needs_reload = (
            force_reload or 
            project_id not in self._tools_by_project or
            self._project_configs.get(project_id) != current_config
        )
        
        if needs_reload:
            logger.info(f"🔄 Cargando herramientas para proyecto {project_id}")
            tools = await agent_tools(
                project_id, user_id, name, number_phone_agent, unique_id, project
            )
            self._tools_by_project[project_id] = tools
            self._project_configs[project_id] = current_config
            logger.info(f"✅ {len(tools)} herramientas cargadas para proyecto {project_id}")
        else:
            logger.info(f"♻️ Usando herramientas existentes para proyecto {project_id}")
            tools = self._tools_by_project[project_id]
        
        return tools
    
    def clear_project(self, project_id: str):
        """Limpia las herramientas de un proyecto específico"""
        if project_id in self._tools_by_project:
            del self._tools_by_project[project_id]
            del self._project_configs[project_id]
            logger.info(f"🗑️ Herramientas limpiadas para proyecto {project_id}")
    
    def clear_all(self):
        """Limpia todas las herramientas en memoria"""
        self._tools_by_project.clear()
        self._project_configs.clear()
        logger.info("🧹 Todas las herramientas limpiadas")

# Instancia global opcional
# Si quieres usar el manager, puedes habilitarlo descomentando la siguiente línea:
# tools_manager = ToolsManager()