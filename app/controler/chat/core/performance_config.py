"""
Configuraciones de optimización de rendimiento para el chat
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from functools import wraps
import time

class PerformanceConfig:
    """Configuraciones globales de rendimiento"""
    
    # Timeouts
    DATABASE_TIMEOUT = 10.0  # segundos
    LLM_TIMEOUT = 30.0      # segundos
    MEMORY_LOAD_TIMEOUT = 5.0  # segundos
    
    # Cache TTL
    PROJECT_CACHE_TTL = 300  # 5 minutos
    STATE_CACHE_TTL = 60     # 1 minuto
    
    # Limits
    MAX_CONCURRENT_TASKS = 10
    MAX_MEMORY_KEYS = 5
    MAX_BATCH_SIZE = 100
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    
    @classmethod
    def get_async_timeout(cls, operation: str) -> float:
        """Obtiene el timeout para una operación específica"""
        timeouts = {
            'database': cls.DATABASE_TIMEOUT,
            'llm': cls.LLM_TIMEOUT,
            'memory': cls.MEMORY_LOAD_TIMEOUT
        }
        return timeouts.get(operation, 10.0)


class PerformanceMonitor:
    """Monitor de rendimiento para medir tiempos de operación"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.metrics = {}
    
    def time_operation(self, operation_name: str):
        """Decorator para medir tiempo de operaciones"""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    self._record_metric(operation_name, duration, True)
                    
                    if duration > 5.0:  # Log operaciones lentas
                        self.logger.warning(f"Operación lenta detectada: {operation_name} tomó {duration:.2f}s")
                    
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self._record_metric(operation_name, duration, False)
                    raise
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    self._record_metric(operation_name, duration, True)
                    
                    if duration > 5.0:  # Log operaciones lentas
                        self.logger.warning(f"Operación lenta detectada: {operation_name} tomó {duration:.2f}s")
                    
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self._record_metric(operation_name, duration, False)
                    raise
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator
    
    def _record_metric(self, operation: str, duration: float, success: bool):
        """Registra una métrica de rendimiento"""
        if operation not in self.metrics:
            self.metrics[operation] = {
                'total_calls': 0,
                'successful_calls': 0,
                'total_time': 0.0,
                'avg_time': 0.0,
                'max_time': 0.0,
                'min_time': float('inf')
            }
        
        metric = self.metrics[operation]
        metric['total_calls'] += 1
        if success:
            metric['successful_calls'] += 1
        
        metric['total_time'] += duration
        metric['avg_time'] = metric['total_time'] / metric['total_calls']
        metric['max_time'] = max(metric['max_time'], duration)
        metric['min_time'] = min(metric['min_time'], duration)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Obtiene todas las métricas registradas"""
        return self.metrics.copy()
    
    def log_performance_summary(self):
        """Log un resumen de rendimiento"""
        for operation, metrics in self.metrics.items():
            success_rate = (metrics['successful_calls'] / metrics['total_calls']) * 100
            self.logger.info(
                f"Rendimiento {operation}: "
                f"Promedio: {metrics['avg_time']:.3f}s, "
                f"Máximo: {metrics['max_time']:.3f}s, "
                f"Mínimo: {metrics['min_time']:.3f}s, "
                f"Éxito: {success_rate:.1f}% ({metrics['successful_calls']}/{metrics['total_calls']})"
            )


async def with_timeout(coro, timeout: float, operation_name: str = "unknown"):
    """Ejecuta una corrutina con timeout"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logging.warning(f"Timeout en operación: {operation_name} ({timeout}s)")
        raise


async def batch_execute(tasks, max_concurrent: int = PerformanceConfig.MAX_CONCURRENT_TASKS):
    """Ejecuta tareas en lotes para controlar concurrencia"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute_with_semaphore(task):
        async with semaphore:
            return await task
    
    limited_tasks = [execute_with_semaphore(task) for task in tasks]
    return await asyncio.gather(*limited_tasks, return_exceptions=True)


def retry_on_failure(max_retries: int = PerformanceConfig.MAX_RETRIES, 
                    delay: float = PerformanceConfig.RETRY_DELAY):
    """Decorator para reintentar operaciones fallidas"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logging.warning(f"Intento {attempt + 1} fallido para {func.__name__}: {e}")
                        await asyncio.sleep(delay * (2 ** attempt))  # Backoff exponencial
                    else:
                        logging.error(f"Todos los intentos fallaron para {func.__name__}")
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logging.warning(f"Intento {attempt + 1} fallido para {func.__name__}: {e}")
                        time.sleep(delay * (2 ** attempt))  # Backoff exponencial
                    else:
                        logging.error(f"Todos los intentos fallaron para {func.__name__}")
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# Instancia global del monitor de rendimiento
performance_monitor = PerformanceMonitor() 