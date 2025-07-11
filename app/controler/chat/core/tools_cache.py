import logging
import asyncio
import hashlib
from functools import lru_cache, wraps
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import threading

class ToolsCache:
    """
    Sistema de cache inteligente para herramientas con:
    - Cache LRU por proyecto
    - Invalidación automática por tiempo
    - Cache thread-safe
    """
    
    _cache: Dict[str, Any] = {}
    _cache_timestamps: Dict[str, datetime] = {}
    _cache_lock = threading.RLock()
    _max_cache_size = 100
    _cache_ttl_hours = 24  # TTL de 24 horas
    
    @classmethod
    def _generate_cache_key(cls, project_id: str, user_id: str, project_version: Optional[str] = None) -> str:
        """
        Genera una clave única para el cache basada en proyecto y usuario.
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario
            project_version: Versión del proyecto (opcional)
            
        Returns:
            Clave única para el cache
        """
        key_data = f"{project_id}:{user_id}"
        if project_version:
            key_data += f":{project_version}"
        
        # Usar hash para claves consistentes y manejables
        return hashlib.md5(key_data.encode()).hexdigest()
    
    @classmethod
    def _is_cache_valid(cls, cache_key: str) -> bool:
        """
        Verifica si el cache sigue siendo válido (no ha expirado).
        
        Args:
            cache_key: Clave del cache a verificar
            
        Returns:
            True si el cache es válido, False si ha expirado
        """
        if cache_key not in cls._cache_timestamps:
            return False
        
        cache_time = cls._cache_timestamps[cache_key]
        now = datetime.now()
        expiry_time = cache_time + timedelta(hours=cls._cache_ttl_hours)
        
        return now < expiry_time
    
    @classmethod
    def _cleanup_expired_cache(cls):
        """
        Limpia entradas de cache expiradas.
        """
        with cls._cache_lock:
            expired_keys = []
            for key in list(cls._cache.keys()):
                if not cls._is_cache_valid(key):
                    expired_keys.append(key)
            
            for key in expired_keys:
                cls._cache.pop(key, None)
                cls._cache_timestamps.pop(key, None)
            
            if expired_keys:
                logging.info(f"🗑️ Cache limpiado: {len(expired_keys)} entradas expiradas eliminadas")
    
    @classmethod
    def get_cached_tools(cls, project_id: str, user_id: str, project_version: Optional[str] = None) -> Optional[List]:
        """
        Obtiene herramientas del cache si están disponibles y válidas.
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario
            project_version: Versión del proyecto
            
        Returns:
            Lista de herramientas si están en cache, None si no
        """
        cache_key = cls._generate_cache_key(project_id, user_id, project_version)
        
        with cls._cache_lock:
            # Limpiar cache expirado
            cls._cleanup_expired_cache()
            
            if cache_key in cls._cache and cls._is_cache_valid(cache_key):
                logging.info(f"🎯 Cache HIT para herramientas del proyecto {project_id}")
                return cls._cache[cache_key]
            else:
                logging.info(f"❌ Cache MISS para herramientas del proyecto {project_id}")
                return None
    
    @classmethod
    def set_cached_tools(cls, project_id: str, user_id: str, tools: List, project_version: Optional[str] = None):
        """
        Almacena herramientas en el cache.
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario
            tools: Lista de herramientas a cachear
            project_version: Versión del proyecto
        """
        cache_key = cls._generate_cache_key(project_id, user_id, project_version)
        
        with cls._cache_lock:
            # Limpiar cache si está lleno
            if len(cls._cache) >= cls._max_cache_size:
                # Eliminar la entrada más antigua
                oldest_key = min(cls._cache_timestamps.keys(), 
                               key=lambda k: cls._cache_timestamps[k])
                cls._cache.pop(oldest_key, None)
                cls._cache_timestamps.pop(oldest_key, None)
                logging.info(f"🗑️ Cache lleno: eliminada entrada {oldest_key}")
            
            # Almacenar nuevas herramientas
            cls._cache[cache_key] = tools.copy() if tools else []
            cls._cache_timestamps[cache_key] = datetime.now()
            
            logging.info(f"💾 Herramientas cacheadas para proyecto {project_id} (total cache: {len(cls._cache)})")
    
    @classmethod
    def invalidate_project_cache(cls, project_id: str):
        """
        Invalida todo el cache relacionado con un proyecto específico.
        
        Args:
            project_id: ID del proyecto a invalidar
        """
        with cls._cache_lock:
            keys_to_remove = []
            for key in cls._cache.keys():
                # Buscar claves que contengan el project_id
                for cached_key in cls._cache_timestamps.keys():
                    if project_id in cached_key:
                        keys_to_remove.append(cached_key)
            
            for key in keys_to_remove:
                cls._cache.pop(key, None)
                cls._cache_timestamps.pop(key, None)
            
            if keys_to_remove:
                logging.info(f"🗑️ Cache invalidado para proyecto {project_id}: {len(keys_to_remove)} entradas eliminadas")
    
    @classmethod
    def clear_all_cache(cls):
        """
        Limpia todo el cache.
        """
        with cls._cache_lock:
            cache_size = len(cls._cache)
            cls._cache.clear()
            cls._cache_timestamps.clear()
            logging.info(f"🗑️ Todo el cache limpiado: {cache_size} entradas eliminadas")
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """
        Obtiene estadísticas del cache.
        
        Returns:
            Diccionario con estadísticas del cache
        """
        with cls._cache_lock:
            cls._cleanup_expired_cache()
            
            return {
                'total_entries': len(cls._cache),
                'max_size': cls._max_cache_size,
                'ttl_hours': cls._cache_ttl_hours,
                'oldest_entry': min(cls._cache_timestamps.values()) if cls._cache_timestamps else None,
                'newest_entry': max(cls._cache_timestamps.values()) if cls._cache_timestamps else None
            }


def cached_tools(ttl_hours: int = 24):
    """
    Decorador para cachear herramientas automáticamente.
    
    Args:
        ttl_hours: Tiempo de vida del cache en horas
        
    Returns:
        Decorador que cachea el resultado de la función
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(project_id, user_id, name, number_phone_agent, unique_id, project):
            # Intentar obtener del cache primero
            project_version = getattr(project, 'version', None) or getattr(project, 'updated_at', None)
            if isinstance(project_version, datetime):
                project_version = project_version.isoformat()
            
            cached_tools = ToolsCache.get_cached_tools(project_id, user_id, str(project_version))
            
            if cached_tools is not None:
                return cached_tools
            
            # Si no está en cache, ejecutar la función original
            try:
                logging.info(f"🔧 Cargando herramientas para proyecto {project_id}...")
                start_time = datetime.now()
                
                tools = await func(project_id, user_id, name, number_phone_agent, unique_id, project)
                
                load_time = (datetime.now() - start_time).total_seconds()
                logging.info(f"⚡ Herramientas cargadas en {load_time:.2f}s")
                
                # Almacenar en cache
                ToolsCache.set_cached_tools(project_id, user_id, tools, str(project_version))
                
                return tools
                
            except Exception as e:
                logging.error(f"❌ Error cargando herramientas para proyecto {project_id}: {str(e)}")
                # En caso de error, intentar devolver cache expirado si existe
                cache_key = ToolsCache._generate_cache_key(project_id, user_id, str(project_version))
                if cache_key in ToolsCache._cache:
                    logging.warning(f"⚠️ Usando cache expirado debido a error")
                    return ToolsCache._cache[cache_key]
                raise
        
        return wrapper
    return decorator