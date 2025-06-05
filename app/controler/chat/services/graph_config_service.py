import logging
import datetime
import asyncio
from typing import Optional, Dict, Any
from app.controler.chat.store.persistence import Persist
from app.controler.chat.classes.model_costs import ModelCosts

class GraphConfigService:
    """Servicio para manejar configuración del grafo y cache de proyectos"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.database = Persist()
        self.model_costs = ModelCosts()
        self._project_cache: Dict[str, Any] = {}
        self._project_cache_time: Dict[str, datetime.datetime] = {}
        self._cache_ttl = 300  # 5 minutos
    
    async def get_project_cached(self, project_id: str):
        """Obtiene el proyecto con cache para evitar consultas repetidas"""
        now = datetime.datetime.now()
        
        # Verificar si tenemos cache válido
        if (project_id in self._project_cache and 
            project_id in self._project_cache_time and 
            (now - self._project_cache_time[project_id]).total_seconds() < self._cache_ttl):
            return self._project_cache[project_id]
        
        # Buscar proyecto en hilo separado
        project = await asyncio.to_thread(self.database.find_project, project_id)
        
        # Actualizar cache
        self._project_cache[project_id] = project
        self._project_cache_time[project_id] = now
        
        return project
    
    def get_model_name(self, project) -> str:
        """Determina el modelo a usar basado en el proyecto"""
        model_name = "gpt-4.1-mini"  # Default fallback
        
        if (project and hasattr(project, 'model') and 
            project.model and isinstance(project.model, str)):
            if project.model in self.model_costs.get_supported_models():
                model_name = project.model
            else:
                self.logger.warning(
                    f"Modelo '{project.model}' del proyecto no soportado, "
                    f"usando fallback '{model_name}'."
                )
        
        return model_name
    
    def clear_cache(self, project_id: Optional[str] = None):
        """Limpia el cache de proyectos"""
        if project_id:
            self._project_cache.pop(project_id, None)
            self._project_cache_time.pop(project_id, None)
        else:
            self._project_cache.clear()
            self._project_cache_time.clear() 