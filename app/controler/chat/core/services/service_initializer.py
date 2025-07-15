"""
Inicializador de servicios especializados.
Configura y inicializa todos los servicios de forma coordinada.
"""

import asyncio
import logging
from typing import Dict, Any

from .db_pool_manager import db_pool

logger = logging.getLogger(__name__)

class ServiceInitializer:
    """
    Coordinador de inicialización de servicios.
    Maneja el ciclo de vida de todos los servicios especializados.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.initialized = False
        self.services = {}
    
    async def initialize_all_services(self) -> Dict[str, Any]:
        """
        Inicializa todos los servicios especializados.
        
        Returns:
            Diccionario con el estado de inicialización de cada servicio
        """
        initialization_status = {}
        
        try:
            # 1. Inicializar pool de conexiones de base de datos
            self.logger.info("🔄 Inicializando pool de conexiones de base de datos...")
            await db_pool.initialize_pool()
            initialization_status['db_pool'] = 'initialized'
            self.logger.info("✅ Pool de conexiones inicializado exitosamente")
            
            # 2. Verificar conectividad de base de datos
            self.logger.info("🔄 Verificando conectividad de base de datos...")
            health_status = await db_pool.health_check()
            if health_status.get('connectivity_test') == 'passed':
                initialization_status['db_connectivity'] = 'verified'
                self.logger.info("✅ Conectividad de base de datos verificada")
            else:
                initialization_status['db_connectivity'] = f"failed: {health_status.get('connectivity_test', 'unknown')}"
                self.logger.warning(f"⚠️ Problema de conectividad: {health_status.get('connectivity_test', 'unknown')}")
            
            # 3. Los servicios individuales se inicializan bajo demanda
            # ContactManager, CalendarService, NotificationService, WorkflowManager
            # se inicializan cuando se crean instancias de AgendaTool
            
            self.initialized = True
            initialization_status['service_initializer'] = 'ready'
            
            self.logger.info("🎉 Inicialización de servicios completada exitosamente")
            
        except Exception as e:
            self.logger.error(f"❌ Error durante inicialización de servicios: {str(e)}")
            initialization_status['error'] = str(e)
            raise
        
        return initialization_status
    
    async def cleanup_all_services(self):
        """Limpia recursos de todos los servicios."""
        try:
            self.logger.info("🔄 Iniciando cleanup de servicios...")
            
            # Cleanup del pool de base de datos
            await db_pool.cleanup()
            
            self.initialized = False
            self.logger.info("✅ Cleanup de servicios completado")
            
        except Exception as e:
            self.logger.error(f"❌ Error durante cleanup: {str(e)}")
    
    async def get_services_health(self) -> Dict[str, Any]:
        """
        Obtiene el estado de salud de todos los servicios.
        
        Returns:
            Estado detallado de todos los servicios
        """
        health_status = {
            'initialized': self.initialized,
            'timestamp': None
        }
        
        try:
            # Estado del pool de base de datos
            db_health = await db_pool.health_check()
            health_status['database'] = db_health
            
            # Estadísticas del pool
            pool_stats = db_pool.get_stats()
            health_status['pool_stats'] = pool_stats
            
            # Estado general
            health_status['overall_status'] = 'healthy' if self.initialized else 'not_initialized'
            
        except Exception as e:
            health_status['overall_status'] = 'error'
            health_status['error'] = str(e)
        
        return health_status

# Instancia global del inicializador
service_initializer = ServiceInitializer()

async def initialize_services() -> Dict[str, Any]:
    """
    Función de conveniencia para inicializar servicios.
    
    Returns:
        Estado de inicialización
    """
    return await service_initializer.initialize_all_services()

async def cleanup_services():
    """Función de conveniencia para cleanup de servicios."""
    await service_initializer.cleanup_all_services()

async def get_services_health() -> Dict[str, Any]:
    """Función de conveniencia para obtener estado de servicios."""
    return await service_initializer.get_services_health()