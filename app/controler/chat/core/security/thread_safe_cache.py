"""
Sistema de cache thread-safe para prevenir race conditions en verificación de conflictos.
Implementa locks distributivos y cache con TTL para operaciones críticas de calendario.
"""

import threading
import time
import hashlib
import json
import logging
from typing import Any, Dict, Optional, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Entrada de cache con metadatos de control."""
    value: Any
    timestamp: float
    ttl_seconds: int
    access_count: int = 0
    last_access: float = 0.0
    
    def is_expired(self) -> bool:
        """Verifica si la entrada ha expirado."""
        return time.time() - self.timestamp > self.ttl_seconds
    
    def is_stale(self, max_age_seconds: int = 60) -> bool:
        """Verifica si la entrada está obsoleta (para cache más agresivo)."""
        return time.time() - self.timestamp > max_age_seconds

class ThreadSafeCache:
    """
    Cache thread-safe con TTL y manejo de concurrencia.
    Previene race conditions en operaciones críticas de calendario.
    """
    
    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        """
        Inicializa el cache thread-safe.
        
        Args:
            default_ttl: TTL por defecto en segundos
            max_size: Tamaño máximo del cache
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'lock_contentions': 0
        }
        
        # Thread para cleanup periódico
        self._cleanup_thread = threading.Thread(target=self._periodic_cleanup, daemon=True)
        self._cleanup_running = True
        self._cleanup_thread.start()
    
    def _get_lock(self, key: str) -> threading.RLock:
        """Obtiene o crea un lock para una clave específica."""
        with self._global_lock:
            if key not in self._locks:
                self._locks[key] = threading.RLock()
            return self._locks[key]
    
    def _generate_key(self, func_name: str, *args, **kwargs) -> str:
        """Genera una clave única para función y argumentos."""
        # Crear string estable de argumentos
        args_str = json.dumps([str(arg) for arg in args], sort_keys=True)
        kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
        
        # Crear hash para evitar claves muy largas
        content = f"{func_name}:{args_str}:{kwargs_str}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def get(self, key: str) -> Optional[Any]:
        """
        Obtiene valor del cache de forma thread-safe.
        
        Args:
            key: Clave del cache
            
        Returns:
            Valor del cache o None si no existe/expiró
        """
        lock = self._get_lock(key)
        
        with lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            entry = self._cache[key]
            
            if entry.is_expired():
                del self._cache[key]
                self._stats['misses'] += 1
                return None
            
            # Actualizar estadísticas de acceso
            entry.access_count += 1
            entry.last_access = time.time()
            self._stats['hits'] += 1
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Establece valor en el cache de forma thread-safe.
        
        Args:
            key: Clave del cache
            value: Valor a almacenar
            ttl: TTL específico (usar default si None)
            
        Returns:
            True si se almacenó correctamente
        """
        lock = self._get_lock(key)
        ttl = ttl or self.default_ttl
        
        with lock:
            # Verificar límite de tamaño
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            
            self._cache[key] = CacheEntry(
                value=value,
                timestamp=time.time(),
                ttl_seconds=ttl,
                access_count=1,
                last_access=time.time()
            )
            
            return True
    
    def delete(self, key: str) -> bool:
        """
        Elimina entrada del cache de forma thread-safe.
        
        Args:
            key: Clave a eliminar
            
        Returns:
            True si se eliminó correctamente
        """
        lock = self._get_lock(key)
        
        with lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def _evict_lru(self) -> None:
        """Elimina la entrada menos recientemente usada."""
        if not self._cache:
            return
        
        # Encontrar entrada LRU (menos recientemente accedida)
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_access
        )
        
        del self._cache[lru_key]
        self._stats['evictions'] += 1
        logger.debug(f"Evicted LRU cache entry: {lru_key}")
    
    def _periodic_cleanup(self) -> None:
        """Limpia entradas expiradas periódicamente."""
        while self._cleanup_running:
            try:
                time.sleep(60)  # Cleanup cada minuto
                self.cleanup_expired()
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
    
    def cleanup_expired(self) -> int:
        """
        Limpia todas las entradas expiradas.
        
        Returns:
            Número de entradas eliminadas
        """
        expired_keys = []
        current_time = time.time()
        
        with self._global_lock:
            for key, entry in self._cache.items():
                if current_time - entry.timestamp > entry.ttl_seconds:
                    expired_keys.append(key)
        
        # Eliminar entradas expiradas
        for key in expired_keys:
            self.delete(key)
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache."""
        with self._global_lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': hit_rate,
                'evictions': self._stats['evictions'],
                'lock_contentions': self._stats['lock_contentions']
            }
    
    def clear(self) -> None:
        """Limpia todo el cache."""
        with self._global_lock:
            self._cache.clear()
            self._locks.clear()
    
    def shutdown(self) -> None:
        """Detiene el cache y limpia recursos."""
        self._cleanup_running = False
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        self.clear()

class ConflictCheckCache:
    """
    Cache especializado para verificación de conflictos de calendario.
    Previene race conditions en operaciones críticas.
    """
    
    def __init__(self):
        self.cache = ThreadSafeCache(default_ttl=120, max_size=500)  # 2 minutos TTL
        self._operation_locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()
    
    def _get_operation_lock(self, operation_id: str) -> threading.RLock:
        """Obtiene lock específico para operación (ej: time slot específico)."""
        with self._global_lock:
            if operation_id not in self._operation_locks:
                self._operation_locks[operation_id] = threading.RLock()
            return self._operation_locks[operation_id]
    
    def check_availability_safe(self, 
                               check_function: Callable,
                               project_id: str,
                               start_time: str,
                               end_time: str,
                               *args,
                               **kwargs) -> Tuple[bool, Any]:
        """
        Verifica disponibilidad de forma thread-safe con cache.
        
        Args:
            check_function: Función de verificación de disponibilidad
            project_id: ID del proyecto
            start_time: Hora de inicio
            end_time: Hora de fin
            *args, **kwargs: Argumentos adicionales para la función
            
        Returns:
            Tuple (hit_cache, resultado)
        """
        # Crear ID único para la operación
        operation_id = f"{project_id}:{start_time}:{end_time}"
        cache_key = self.cache._generate_key(
            f"availability_check_{check_function.__name__}", 
            project_id, start_time, end_time, *args, **kwargs
        )
        
        # Verificar cache primero
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for availability check: {operation_id}")
            return True, cached_result
        
        # Lock específico para este slot temporal
        operation_lock = self._get_operation_lock(operation_id)
        
        with operation_lock:
            # Double-check pattern: verificar cache otra vez después del lock
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit after lock for availability check: {operation_id}")
                return True, cached_result
            
            # Ejecutar verificación real
            logger.debug(f"Cache miss, executing availability check: {operation_id}")
            try:
                result = check_function(*args, **kwargs)
                
                # Cachear resultado por tiempo limitado
                self.cache.set(cache_key, result, ttl=30)  # 30 segundos para operaciones críticas
                
                return False, result
                
            except Exception as e:
                logger.error(f"Error in availability check for {operation_id}: {e}")
                # No cachear errores
                raise
    
    def invalidate_time_range(self, project_id: str, start_time: str, end_time: str) -> None:
        """
        Invalida cache para un rango de tiempo específico.
        Útil después de crear/actualizar/eliminar eventos.
        
        Args:
            project_id: ID del proyecto
            start_time: Hora de inicio del rango
            end_time: Hora de fin del rango
        """
        operation_id = f"{project_id}:{start_time}:{end_time}"
        
        # Invalidar entradas relacionadas
        with self.cache._global_lock:
            keys_to_delete = []
            for key in self.cache._cache.keys():
                # Si la clave contiene el operation_id, invalidarla
                if operation_id in key or project_id in key:
                    keys_to_delete.append(key)
        
        for key in keys_to_delete:
            self.cache.delete(key)
        
        logger.debug(f"Invalidated {len(keys_to_delete)} cache entries for time range: {operation_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache de conflictos."""
        base_stats = self.cache.get_stats()
        base_stats['operation_locks'] = len(self._operation_locks)
        return base_stats

# Instancias globales
global_cache = ThreadSafeCache()
conflict_cache = ConflictCheckCache()

def thread_safe_cache(ttl: int = 300, key_func: Optional[Callable] = None):
    """
    Decorador para hacer funciones thread-safe con cache.
    
    Args:
        ttl: TTL del cache en segundos
        key_func: Función personalizada para generar claves de cache
        
    Returns:
        Decorador
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generar clave de cache
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = global_cache._generate_key(func.__name__, *args, **kwargs)
            
            # Verificar cache
            cached_result = global_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Ejecutar función y cachear resultado
            result = func(*args, **kwargs)
            global_cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

def conflict_safe_check(func: Callable) -> Callable:
    """
    Decorador para hacer verificaciones de conflicto thread-safe.
    Usar en funciones críticas de verificación de disponibilidad.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Extraer parámetros comunes
        project_id = kwargs.get('project_id') or (args[0] if args else 'unknown')
        start_time = kwargs.get('start_time') or kwargs.get('start_datetime')
        end_time = kwargs.get('end_time') or kwargs.get('end_datetime')
        
        if not all([project_id, start_time, end_time]):
            # Si no tenemos parámetros suficientes, ejecutar sin cache
            return func(*args, **kwargs)
        
        hit_cache, result = conflict_cache.check_availability_safe(
            func, str(project_id), str(start_time), str(end_time), *args, **kwargs
        )
        
        return result
    
    return wrapper