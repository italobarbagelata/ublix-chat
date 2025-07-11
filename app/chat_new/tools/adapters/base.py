"""
Clase Base para Adaptadores de Herramientas

Define la interfaz común para todos los adaptadores de herramientas
en el sistema mejorado de LangGraph Chat.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime

from ...core.state import EnhancedState


class BaseToolAdapter(ABC):
    """
    Clase base abstracta para adaptadores de herramientas.
    
    Todos los adaptadores deben implementar los métodos abstractos
    para garantizar compatibilidad con el registro de herramientas.
    """
    
    def __init__(self, metadata: Optional[Dict] = None):
        self.metadata = metadata or {}
        self.created_at = datetime.now()
    
    @abstractmethod
    async def execute(self, state: EnhancedState, **kwargs) -> Any:
        """
        Ejecuta la herramienta con el estado dado.
        
        Args:
            state: Estado mejorado actual
            **kwargs: Argumentos para la herramienta
            
        Returns:
            Resultado de la ejecución
        """
        pass
    
    @abstractmethod
    def get_tool_info(self) -> Dict[str, Any]:
        """
        Obtiene información detallada de la herramienta.
        
        Returns:
            Diccionario con información de la herramienta
        """
        pass
    
    @abstractmethod
    def is_available(self, state: EnhancedState) -> bool:
        """
        Verifica si la herramienta está disponible.
        
        Args:
            state: Estado mejorado actual
            
        Returns:
            True si la herramienta está disponible
        """
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """Obtiene metadatos del adaptador"""
        return {
            **self.metadata,
            "adapter_created_at": self.created_at.isoformat(),
            "adapter_type": self.__class__.__name__
        }