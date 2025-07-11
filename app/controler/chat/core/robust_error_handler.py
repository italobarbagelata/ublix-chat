import logging
import asyncio
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Type, Union
from dataclasses import dataclass, field
from enum import Enum

class ErrorSeverity(Enum):
    """Niveles de severidad de errores"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class CircuitBreakerState(Enum):
    """Estados del circuit breaker"""
    CLOSED = "closed"      # Funcionamiento normal
    OPEN = "open"          # Bloqueando solicitudes
    HALF_OPEN = "half_open"  # Probando recuperación

@dataclass
class RetryConfig:
    """Configuración para reintentos"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_backoff: bool = True
    jitter: bool = True
    retry_on: tuple = (Exception,)

@dataclass
class CircuitBreakerConfig:
    """Configuración para circuit breaker"""
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: float = 60.0
    half_open_max_calls: int = 3

@dataclass
class ErrorStats:
    """Estadísticas de errores"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    error_counts: Dict[str, int] = field(default_factory=dict)

class RobustErrorHandler:
    """
    Sistema robusto de manejo de errores con:
    - Retry automático con backoff exponencial
    - Circuit breaker pattern
    - Estadísticas de errores
    - Fallback strategies
    """
    
    def __init__(self):
        self._circuit_breakers: Dict[str, Dict] = {}
        self._error_stats: Dict[str, ErrorStats] = {}
    
    def with_retry(
        self,
        config: Optional[RetryConfig] = None,
        circuit_breaker_key: Optional[str] = None,
        fallback: Optional[Callable] = None
    ):
        """
        Decorador para retry automático con circuit breaker opcional.
        
        Args:
            config: Configuración de retry
            circuit_breaker_key: Clave para circuit breaker
            fallback: Función de fallback en caso de fallo
        """
        if config is None:
            config = RetryConfig()
        
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                func_name = f"{func.__module__}.{func.__name__}"
                
                # Verificar circuit breaker
                if circuit_breaker_key:
                    if not self._check_circuit_breaker(circuit_breaker_key):
                        logging.warning(f"🚫 Circuit breaker abierto para {func_name}")
                        if fallback:
                            return await self._execute_fallback(fallback, *args, **kwargs)
                        raise CircuitBreakerOpenError(f"Circuit breaker abierto para {circuit_breaker_key}")
                
                # Obtener o crear estadísticas
                stats = self._get_or_create_stats(func_name)
                stats.total_calls += 1
                
                last_exception = None
                
                for attempt in range(config.max_retries + 1):
                    try:
                        start_time = time.time()
                        
                        # Ejecutar función
                        if asyncio.iscoroutinefunction(func):
                            result = await func(*args, **kwargs)
                        else:
                            result = func(*args, **kwargs)
                        
                        execution_time = time.time() - start_time
                        
                        # Registrar éxito
                        self._record_success(func_name, circuit_breaker_key, execution_time)
                        
                        return result
                        
                    except Exception as e:
                        last_exception = e
                        
                        # Verificar si debemos reintentar
                        if not isinstance(e, config.retry_on):
                            logging.error(f"❌ Error no reintentar para {func_name}: {str(e)}")
                            self._record_failure(func_name, circuit_breaker_key, e, attempt)
                            break
                        
                        if attempt == config.max_retries:
                            logging.error(f"❌ Máximo de reintentos alcanzado para {func_name}")
                            self._record_failure(func_name, circuit_breaker_key, e, attempt)
                            break
                        
                        # Calcular delay para siguiente intento
                        delay = self._calculate_delay(config, attempt)
                        
                        logging.warning(
                            f"⚠️ Intento {attempt + 1}/{config.max_retries + 1} falló para {func_name}: {str(e)}. "
                            f"Reintentando en {delay:.2f}s"
                        )
                        
                        await asyncio.sleep(delay)
                
                # Si llegamos aquí, todos los intentos fallaron
                self._record_failure(func_name, circuit_breaker_key, last_exception, config.max_retries)
                
                # Intentar fallback
                if fallback:
                    try:
                        logging.info(f"🔄 Ejecutando fallback para {func_name}")
                        return await self._execute_fallback(fallback, *args, **kwargs)
                    except Exception as fallback_error:
                        logging.error(f"❌ Fallback también falló para {func_name}: {str(fallback_error)}")
                
                # Re-lanzar la última excepción
                raise last_exception
            
            return wrapper
        return decorator
    
    def _calculate_delay(self, config: RetryConfig, attempt: int) -> float:
        """Calcula el delay para el siguiente intento"""
        if config.exponential_backoff:
            delay = config.base_delay * (2 ** attempt)
        else:
            delay = config.base_delay
        
        # Aplicar límite máximo
        delay = min(delay, config.max_delay)
        
        # Agregar jitter para evitar thundering herd
        if config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
        return delay
    
    def _check_circuit_breaker(self, key: str) -> bool:
        """Verifica si el circuit breaker permite la ejecución"""
        if key not in self._circuit_breakers:
            self._circuit_breakers[key] = {
                'state': CircuitBreakerState.CLOSED,
                'config': CircuitBreakerConfig(),
                'failure_count': 0,
                'success_count': 0,
                'last_failure_time': None,
                'half_open_calls': 0
            }
        
        breaker = self._circuit_breakers[key]
        state = breaker['state']
        config = breaker['config']
        
        if state == CircuitBreakerState.CLOSED:
            return True
        elif state == CircuitBreakerState.OPEN:
            # Verificar si es tiempo de probar recuperación
            if (time.time() - breaker['last_failure_time']) > config.timeout:
                breaker['state'] = CircuitBreakerState.HALF_OPEN
                breaker['half_open_calls'] = 0
                logging.info(f"🔄 Circuit breaker {key} cambiando a HALF_OPEN")
                return True
            return False
        elif state == CircuitBreakerState.HALF_OPEN:
            if breaker['half_open_calls'] < config.half_open_max_calls:
                breaker['half_open_calls'] += 1
                return True
            return False
        
        return False
    
    def _record_success(self, func_name: str, circuit_breaker_key: Optional[str], execution_time: float):
        """Registra una ejecución exitosa"""
        stats = self._get_or_create_stats(func_name)
        stats.successful_calls += 1
        stats.consecutive_successes += 1
        stats.consecutive_failures = 0
        stats.last_success_time = time.time()
        
        # Actualizar circuit breaker
        if circuit_breaker_key and circuit_breaker_key in self._circuit_breakers:
            breaker = self._circuit_breakers[circuit_breaker_key]
            breaker['success_count'] += 1
            
            if breaker['state'] == CircuitBreakerState.HALF_OPEN:
                if breaker['success_count'] >= breaker['config'].success_threshold:
                    breaker['state'] = CircuitBreakerState.CLOSED
                    breaker['failure_count'] = 0
                    logging.info(f"✅ Circuit breaker {circuit_breaker_key} recuperado (CLOSED)")
        
        logging.debug(f"✅ Éxito en {func_name} (tiempo: {execution_time:.2f}s)")
    
    def _record_failure(self, func_name: str, circuit_breaker_key: Optional[str], error: Exception, attempt: int):
        """Registra una falla"""
        stats = self._get_or_create_stats(func_name)
        stats.failed_calls += 1
        stats.consecutive_failures += 1
        stats.consecutive_successes = 0
        stats.last_failure_time = time.time()
        
        # Contar tipo de error
        error_type = type(error).__name__
        stats.error_counts[error_type] = stats.error_counts.get(error_type, 0) + 1
        
        # Actualizar circuit breaker
        if circuit_breaker_key:
            if circuit_breaker_key not in self._circuit_breakers:
                self._circuit_breakers[circuit_breaker_key] = {
                    'state': CircuitBreakerState.CLOSED,
                    'config': CircuitBreakerConfig(),
                    'failure_count': 0,
                    'success_count': 0,
                    'last_failure_time': None,
                    'half_open_calls': 0
                }
            
            breaker = self._circuit_breakers[circuit_breaker_key]
            breaker['failure_count'] += 1
            breaker['last_failure_time'] = time.time()
            breaker['success_count'] = 0
            
            # Abrir circuit breaker si se alcanza el threshold
            if (breaker['failure_count'] >= breaker['config'].failure_threshold and 
                breaker['state'] == CircuitBreakerState.CLOSED):
                breaker['state'] = CircuitBreakerState.OPEN
                logging.error(f"🚫 Circuit breaker {circuit_breaker_key} ABIERTO por muchas fallas")
            elif breaker['state'] == CircuitBreakerState.HALF_OPEN:
                breaker['state'] = CircuitBreakerState.OPEN
                logging.error(f"🚫 Circuit breaker {circuit_breaker_key} vuelve a OPEN")
    
    async def _execute_fallback(self, fallback: Callable, *args, **kwargs) -> Any:
        """Ejecuta función de fallback"""
        if asyncio.iscoroutinefunction(fallback):
            return await fallback(*args, **kwargs)
        else:
            return fallback(*args, **kwargs)
    
    def _get_or_create_stats(self, func_name: str) -> ErrorStats:
        """Obtiene o crea estadísticas para una función"""
        if func_name not in self._error_stats:
            self._error_stats[func_name] = ErrorStats()
        return self._error_stats[func_name]
    
    def get_stats(self, func_name: Optional[str] = None) -> Dict[str, Any]:
        """Obtiene estadísticas de errores"""
        if func_name:
            if func_name in self._error_stats:
                stats = self._error_stats[func_name]
                return {
                    'function': func_name,
                    'total_calls': stats.total_calls,
                    'successful_calls': stats.successful_calls,
                    'failed_calls': stats.failed_calls,
                    'success_rate': stats.successful_calls / max(stats.total_calls, 1),
                    'consecutive_failures': stats.consecutive_failures,
                    'consecutive_successes': stats.consecutive_successes,
                    'error_counts': stats.error_counts
                }
            return {}
        else:
            return {func: self.get_stats(func) for func in self._error_stats.keys()}
    
    def get_circuit_breaker_status(self, key: Optional[str] = None) -> Dict[str, Any]:
        """Obtiene estado de circuit breakers"""
        if key:
            if key in self._circuit_breakers:
                breaker = self._circuit_breakers[key]
                return {
                    'key': key,
                    'state': breaker['state'].value,
                    'failure_count': breaker['failure_count'],
                    'success_count': breaker['success_count'],
                    'last_failure_time': breaker['last_failure_time']
                }
            return {}
        else:
            return {key: self.get_circuit_breaker_status(key) for key in self._circuit_breakers.keys()}
    
    def reset_circuit_breaker(self, key: str):
        """Resetea un circuit breaker específico"""
        if key in self._circuit_breakers:
            self._circuit_breakers[key]['state'] = CircuitBreakerState.CLOSED
            self._circuit_breakers[key]['failure_count'] = 0
            self._circuit_breakers[key]['success_count'] = 0
            logging.info(f"🔄 Circuit breaker {key} reseteado")

class CircuitBreakerOpenError(Exception):
    """Excepción lanzada cuando el circuit breaker está abierto"""
    pass

# Instancia global del error handler
error_handler = RobustErrorHandler()