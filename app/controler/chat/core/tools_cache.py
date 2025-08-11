"""
Cache global para herramientas para evitar recargas múltiples
"""
import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

class ToolsCache:
    """Cache singleton para herramientas por proyecto"""
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
            cls._instance._timestamps = {}
            cls._instance._ttl = timedelta(minutes=10)  # 10 minutos de cache
        return cls._instance
    
    async def get_tools(self, cache_key: str, factory_func, *args, **kwargs) -> List[Any]:
        """Obtiene herramientas del cache o las crea si no existen"""
        async with self._lock:
            # Verificar si existe en cache y no está expirado
            if cache_key in self._cache:
                if datetime.now() - self._timestamps[cache_key] < self._ttl:
                    logger.info(f"🎯 Cache HIT para herramientas: {cache_key}")
                    return self._cache[cache_key]
                else:
                    logger.info(f"⏰ Cache expirado para: {cache_key}")
            
            # Crear nuevas herramientas
            logger.info(f"🔧 Cache MISS - creando herramientas para: {cache_key}")
            tools = await factory_func(*args, **kwargs)
            
            # Guardar en cache
            self._cache[cache_key] = tools
            self._timestamps[cache_key] = datetime.now()
            
            logger.info(f"✅ Herramientas cacheadas: {cache_key} ({len(tools)} tools)")
            return tools
    
    def invalidate(self, cache_key: str):
        """Invalida una entrada específica del cache"""
        if cache_key in self._cache:
            del self._cache[cache_key]
            del self._timestamps[cache_key]
            logger.info(f"🗑️ Cache invalidado para: {cache_key}")
    
    def clear_all(self):
        """Limpia todo el cache"""
        self._cache.clear()
        self._timestamps.clear()
        logger.info("🧹 Cache completamente limpiado")

# Instancia global singleton
tools_cache = ToolsCache()