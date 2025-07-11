"""
🚀 Enhanced Graph Bridge - Drop-in Replacement para Graph

Este módulo proporciona un reemplazo directo para Graph.create() que usa
la nueva arquitectura mejorada manteniendo 100% compatibilidad.

Uso simple:
# Cambiar esta línea:
# from app.controler.chat.core.graph import Graph

# Por esta:
# from app.controler.chat.enhanced_graph_bridge import Graph

¡Y listo! Tu código seguirá funcionando igual pero con todas las mejoras.
"""

import logging
from typing import Any, Dict, Optional
import asyncio

# Import del nuevo sistema
from app.chat_new.utils.integration import create_legacy_compatible_graph


class Graph:
    """
    🔄 Bridge class que reemplaza exactamente a Graph pero usa EnhancedGraph internamente.
    
    Esta clase mantiene la misma interfaz que el Graph original pero
    usa toda la nueva arquitectura mejorada por debajo.
    """
    
    def __init__(self, enhanced_wrapper):
        """No se usa directamente - usa Graph.create()"""
        self._enhanced_wrapper = enhanced_wrapper
        self.logger = logging.getLogger(__name__)
        
        # Propiedades de compatibilidad
        self.state = enhanced_wrapper.state
        self.project_id = enhanced_wrapper.project_id
        self.user_id = enhanced_wrapper.user_id
        self.name = enhanced_wrapper.name
        self.source = enhanced_wrapper.source
        self.source_id = enhanced_wrapper.source_id
        self.unique_id = enhanced_wrapper.unique_id
        self.project = enhanced_wrapper.project
    
    @classmethod
    async def create(
        cls,
        project_id: str,
        user_id: str, 
        name: str,
        number_phone_agent: str,
        source: str,
        source_id: str,
        unique_id: str,
        project: Any
    ) -> 'Graph':
        """
        🚀 Método create que usa el nuevo EnhancedGraph internamente.
        
        Mantiene exactamente la misma signatura que el Graph original.
        """
        
        logger = logging.getLogger(__name__)
        logger.info(f"🚀 Creating Enhanced Graph (Bridge) for {project_id}/{user_id}")
        
        try:
            # Crear el wrapper de compatibilidad con el nuevo sistema
            enhanced_wrapper = await create_legacy_compatible_graph(
                project_id=project_id,
                user_id=user_id,
                name=name,
                number_phone_agent=number_phone_agent,
                source=source,
                source_id=source_id,
                unique_id=unique_id,
                project=project
            )
            
            # Retornar instancia del bridge
            instance = cls(enhanced_wrapper)
            logger.info(f"✅ Enhanced Graph Bridge created successfully for {project_id}/{user_id}")
            
            return instance
            
        except Exception as e:
            logger.error(f"❌ Failed to create Enhanced Graph Bridge: {str(e)}")
            # Fallback al sistema original en caso de error
            logger.warning("🔄 Falling back to original Graph system")
            
            from app.controler.chat.core.graph import Graph as OriginalGraph
            return await OriginalGraph.create(
                project_id, user_id, name, number_phone_agent,
                source, source_id, unique_id, project
            )
    
    async def execute(self, message: str, debug: bool = False) -> Dict[str, Any]:
        """
        Ejecuta usando el nuevo sistema mejorado.
        
        Args:
            message: Mensaje del usuario
            debug: Parámetro de compatibilidad (no usado en nuevo sistema)
            
        Returns:
            Respuesta en formato compatible con el sistema original
        """
        try:
            return await self._enhanced_wrapper.execute(message, debug)
        except Exception as e:
            self.logger.error(f"Enhanced execution failed: {str(e)}")
            raise
    
    async def execute_with_immediate_response(
        self, 
        message: str, 
        background_tasks: Any
    ) -> Dict[str, Any]:
        """
        Ejecuta con respuesta inmediata usando el nuevo sistema.
        
        Args:
            message: Mensaje del usuario
            background_tasks: Tareas en segundo plano
            
        Returns:
            Respuesta con metadata de respuesta inmediata
        """
        try:
            return await self._enhanced_wrapper.execute_with_immediate_response(
                message, background_tasks
            )
        except Exception as e:
            self.logger.error(f"Enhanced immediate response failed: {str(e)}")
            raise
    
    async def execute_stream(self, message: str, background_tasks: Any):
        """
        Ejecuta en modo streaming usando el nuevo sistema.
        
        Args:
            message: Mensaje del usuario
            background_tasks: Tareas en segundo plano
            
        Yields:
            Chunks de respuesta en streaming
        """
        try:
            async for chunk in self._enhanced_wrapper.execute_stream(message, background_tasks):
                yield chunk
        except Exception as e:
            self.logger.error(f"Enhanced streaming failed: {str(e)}")
            # Enviar error en formato streaming
            yield {
                "type": "error",
                "error": str(e),
                "is_complete": True
            }


# Función auxiliar para migración gradual
async def create_enhanced_graph_if_enabled(
    project_id: str,
    user_id: str,
    name: str,
    number_phone_agent: str,
    source: str,
    source_id: str,
    unique_id: str,
    project: Any,
    use_enhanced: bool = True
) -> Any:
    """
    🔧 Función helper para migración gradual.
    
    Permite activar/desactivar el nuevo sistema con un flag.
    
    Args:
        use_enhanced: Si True, usa EnhancedGraph. Si False, usa Graph original.
        
    Returns:
        Instancia de Graph (enhanced o original)
    """
    
    if use_enhanced:
        # Usar nuevo sistema
        return await Graph.create(
            project_id, user_id, name, number_phone_agent,
            source, source_id, unique_id, project
        )
    else:
        # Usar sistema original
        from app.controler.chat.core.graph import Graph as OriginalGraph
        return await OriginalGraph.create(
            project_id, user_id, name, number_phone_agent,
            source, source_id, unique_id, project
        )


# Performance monitoring
class GraphPerformanceMonitor:
    """
    📊 Monitor de performance para comparar sistemas
    """
    
    def __init__(self):
        self.enhanced_metrics = []
        self.original_metrics = []
        self.logger = logging.getLogger(__name__)
    
    async def compare_execution(
        self,
        project_id: str,
        user_id: str,
        name: str,
        number_phone_agent: str,
        source: str,
        source_id: str,
        unique_id: str,
        project: Any,
        message: str
    ) -> Dict[str, Any]:
        """
        Compara performance entre sistemas original y mejorado.
        """
        
        import time
        
        comparison_result = {
            "message": message,
            "enhanced_result": None,
            "original_result": None,
            "performance_comparison": {}
        }
        
        try:
            # Test Enhanced System
            start_time = time.time()
            enhanced_graph = await Graph.create(
                project_id, user_id, name, number_phone_agent,
                source, source_id, unique_id, project
            )
            enhanced_result = await enhanced_graph.execute(message)
            enhanced_time = time.time() - start_time
            
            comparison_result["enhanced_result"] = {
                **enhanced_result,
                "execution_time": enhanced_time,
                "system": "enhanced"
            }
            
        except Exception as e:
            self.logger.error(f"Enhanced system test failed: {str(e)}")
            comparison_result["enhanced_result"] = {"error": str(e)}
        
        try:
            # Test Original System
            from app.controler.chat.core.graph import Graph as OriginalGraph
            
            start_time = time.time()
            original_graph = await OriginalGraph.create(
                project_id, user_id, name, number_phone_agent,
                source, source_id, unique_id, project
            )
            original_result = await original_graph.execute(message)
            original_time = time.time() - start_time
            
            comparison_result["original_result"] = {
                **original_result,
                "execution_time": original_time,
                "system": "original"
            }
            
        except Exception as e:
            self.logger.error(f"Original system test failed: {str(e)}")
            comparison_result["original_result"] = {"error": str(e)}
        
        # Calculate performance comparison
        if (comparison_result["enhanced_result"] and 
            comparison_result["original_result"] and
            "error" not in comparison_result["enhanced_result"] and
            "error" not in comparison_result["original_result"]):
            
            enhanced_time = comparison_result["enhanced_result"]["execution_time"]
            original_time = comparison_result["original_result"]["execution_time"]
            
            speed_improvement = ((original_time - enhanced_time) / original_time) * 100
            
            comparison_result["performance_comparison"] = {
                "enhanced_time": enhanced_time,
                "original_time": original_time,
                "speed_improvement_percent": speed_improvement,
                "faster_system": "enhanced" if enhanced_time < original_time else "original",
                "performance_ratio": original_time / enhanced_time if enhanced_time > 0 else 0
            }
        
        return comparison_result


# Global monitor instance
performance_monitor = GraphPerformanceMonitor()