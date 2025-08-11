"""
Cache para conversation_data para evitar consultas repetidas
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

class ConversationCache:
    """Cache para datos de conversación"""
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
            cls._instance._timestamps = {}
            cls._instance._ttl = timedelta(seconds=30)  # 30 segundos de cache
        return cls._instance
    
    async def get_conversation(self, project_id: str, phone_number: str, fetch_func) -> List[Dict[Any, Any]]:
        """Obtiene conversación del cache o la busca"""
        cache_key = f"{project_id}_{phone_number}"
        
        async with self._lock:
            # Verificar cache
            if cache_key in self._cache:
                if datetime.now() - self._timestamps[cache_key] < self._ttl:
                    logger.info(f"💬 Cache HIT para conversación: {cache_key}")
                    return self._cache[cache_key]
            
            # Buscar en DB
            logger.info(f"💬 Cache MISS - buscando conversación: {cache_key}")
            data = await fetch_func()
            
            # Guardar en cache
            self._cache[cache_key] = data
            self._timestamps[cache_key] = datetime.now()
            
            return data
    
    def invalidate(self, project_id: str, phone_number: str):
        """Invalida el cache cuando hay nuevos mensajes"""
        cache_key = f"{project_id}_{phone_number}"
        if cache_key in self._cache:
            del self._cache[cache_key]
            del self._timestamps[cache_key]

# Instancia global
conversation_cache = ConversationCache()