import logging
import asyncio
import time
import json
import traceback
from functools import wraps
from typing import Any, Callable, Dict, Optional, Type, Union, List
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from datetime import datetime, timedelta

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
    """Estadísticas de errores mejoradas"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    error_counts: Dict[str, int] = field(default_factory=dict)
    avg_execution_time: float = 0.0
    total_execution_time: float = 0.0
    error_patterns: Dict[str, int] = field(default_factory=dict)
    recovery_attempts: int = 0
    successful_recoveries: int = 0
    recent_errors: deque = field(default_factory=lambda: deque(maxlen=10))

@dataclass
class ErrorContext:
    """Contexto detallado de un error"""
    timestamp: float
    function_name: str
    error_type: str
    error_message: str
    stack_trace: str
    attempt_number: int
    execution_time: float
    input_hash: Optional[str] = None
    recovery_strategy: Optional[str] = None
    user_context: Dict[str, Any] = field(default_factory=dict)

class RecoveryStrategy(Enum):
    """Estrategias de recuperación disponibles"""
    RETRY_WITH_DELAY = "retry_with_delay"
    FALLBACK_FUNCTION = "fallback_function"
    CIRCUIT_BREAKER = "circuit_breaker"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    USER_NOTIFICATION = "user_notification"
    SKIP_OPERATION = "skip_operation"

class AdvancedErrorHandler:
    """
    Sistema AVANZADO de manejo de errores con:
    - Retry automático con backoff exponencial inteligente
    - Circuit breaker pattern con auto-recuperación
    - Estadísticas detalladas y análisis de patrones
    - Múltiples estrategias de recuperación
    - Predicción de errores basada en patrones
    - Notificaciones contextuales al usuario
    - Sistema de salud y métricas en tiempo real
    - Auto-ajuste de configuración basado en historial
    """
    
    def __init__(self):
        self._circuit_breakers: Dict[str, Dict] = {}
        self._error_stats: Dict[str, ErrorStats] = {}
        self._recovery_strategies: Dict[str, Callable] = {}
        self._error_patterns: Dict[str, List[str]] = defaultdict(list)
        self._health_check_functions: Dict[str, Callable] = {}
        self._global_error_context: Dict[str, Any] = {}
        self._adaptive_configs: Dict[str, Dict] = {}
        self._prediction_cache: Dict[str, Dict] = {}
        
        # Configurar estrategias de recuperación por defecto
        self._setup_default_recovery_strategies()
    
    def _setup_default_recovery_strategies(self):
        """Configura estrategias de recuperación por defecto"""
        self._recovery_strategies.update({
            'api_timeout': self._handle_api_timeout_recovery,
            'connection_error': self._handle_connection_error_recovery,
            'memory_error': self._handle_memory_error_recovery,
            'rate_limit': self._handle_rate_limit_recovery,
            'authentication_error': self._handle_auth_error_recovery,
            'data_validation_error': self._handle_validation_error_recovery
        })
    
    def register_recovery_strategy(self, error_pattern: str, strategy: Callable):
        """Registra una estrategia de recuperación personalizada"""
        self._recovery_strategies[error_pattern] = strategy
        logging.info(f"Recovery strategy registered for: {error_pattern}")
    
    def register_health_check(self, service_name: str, health_check_func: Callable):
        """Registra función de verificación de salud para un servicio"""
        self._health_check_functions[service_name] = health_check_func
        logging.info(f"Health check registered for: {service_name}")
    
    async def _handle_api_timeout_recovery(self, error: Exception, context: Dict) -> Any:
        """Estrategia de recuperación para timeouts de API"""
        logging.info(" Aplicando estrategia de recuperación para timeout de API")
        # Incrementar timeout para siguiente intento
        if 'timeout' in context:
            context['timeout'] = min(context['timeout'] * 1.5, 60.0)
        # Usar cache si está disponible
        if 'use_cache' in context:
            context['use_cache'] = True
        return context
    
    async def _handle_connection_error_recovery(self, error: Exception, context: Dict) -> Any:
        """Estrategia de recuperación para errores de conexión"""
        logging.info(" Aplicando estrategia de recuperación para error de conexión")
        # Cambiar a endpoint alternativo si está disponible
        if 'alternative_endpoint' in context:
            context['use_alternative'] = True
        # Reducir batch size
        if 'batch_size' in context:
            context['batch_size'] = max(1, context['batch_size'] // 2)
        return context
    
    async def _handle_memory_error_recovery(self, error: Exception, context: Dict) -> Any:
        """Estrategia de recuperación para errores de memoria"""
        logging.info(" Aplicando estrategia de recuperación para error de memoria")
        # Forzar limpieza de memoria
        import gc
        gc.collect()
        # Reducir tamaño de datos procesados
        if 'chunk_size' in context:
            context['chunk_size'] = max(1, context['chunk_size'] // 2)
        return context
    
    async def _handle_rate_limit_recovery(self, error: Exception, context: Dict) -> Any:
        """Estrategia de recuperación para rate limiting"""
        logging.info(" Aplicando estrategia de recuperación para rate limit")
        # Extraer tiempo de espera del error si está disponible
        retry_after = self._extract_retry_after(error)
        if retry_after:
            await asyncio.sleep(retry_after)
        # Reducir velocidad de requests
        if 'request_rate' in context:
            context['request_rate'] = context['request_rate'] * 0.5
        return context
    
    async def _handle_auth_error_recovery(self, error: Exception, context: Dict) -> Any:
        """Estrategia de recuperación para errores de autenticación"""
        logging.info(" Aplicando estrategia de recuperación para error de autenticación")
        # Intentar renovar token
        if 'refresh_token_func' in context:
            try:
                await context['refresh_token_func']()
                return context
            except Exception as refresh_error:
                logging.error(f" Error renovando token: {refresh_error}")
        return None  # No se puede recuperar
    
    async def _handle_validation_error_recovery(self, error: Exception, context: Dict) -> Any:
        """Estrategia de recuperación para errores de validación"""
        logging.info(" Aplicando estrategia de recuperación para error de validación")
        # Intentar sanitizar datos
        if 'data' in context and 'sanitize_func' in context:
            try:
                context['data'] = context['sanitize_func'](context['data'])
                return context
            except Exception as sanitize_error:
                logging.error(f" Error sanitizando datos: {sanitize_error}")
        return None
    
    def _extract_retry_after(self, error: Exception) -> Optional[float]:
        """Extrae tiempo de retry-after de un error"""
        error_str = str(error).lower()
        # Buscar patrones comunes de retry-after
        import re
        patterns = [
            r'retry.*?(\d+).*?second',
            r'wait.*?(\d+).*?second',
            r'retry-after:\s*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_str)
            if match:
                return float(match.group(1))
        
        return None
    
    async def predict_error_likelihood(self, func_name: str, context: Dict) -> Dict[str, float]:
        """
        Predice la probabilidad de diferentes tipos de errores basado en patrones históricos
        
        Args:
            func_name: Nombre de la función
            context: Contexto de ejecución
            
        Returns:
            Diccionario con probabilidades de error por tipo
        """
        if func_name not in self._error_stats:
            return {"overall_risk": 0.0}
        
        stats = self._error_stats[func_name]
        predictions = {}
        
        # Calcular riesgo general basado en tasa de fallo reciente
        if stats.total_calls > 0:
            recent_failure_rate = stats.failed_calls / stats.total_calls
            consecutive_failure_factor = min(stats.consecutive_failures / 5.0, 1.0)
            overall_risk = (recent_failure_rate * 0.7) + (consecutive_failure_factor * 0.3)
            predictions["overall_risk"] = min(overall_risk, 1.0)
        
        # Analizar patrones específicos de error
        for error_type, count in stats.error_counts.items():
            error_rate = count / max(stats.total_calls, 1)
            predictions[f"{error_type.lower()}_risk"] = min(error_rate * 1.2, 1.0)
        
        # Factores contextuales
        current_hour = datetime.now().hour
        if 'peak_hours' in context and current_hour in context['peak_hours']:
            predictions["load_related_risk"] = predictions.get("overall_risk", 0.0) * 1.3
        
        return predictions
    
    async def get_adaptive_config(self, func_name: str) -> RetryConfig:
        """
        Obtiene configuración adaptativa basada en el historial de la función
        
        Args:
            func_name: Nombre de la función
            
        Returns:
            Configuración de retry optimizada
        """
        if func_name not in self._error_stats:
            return RetryConfig()  # Configuración por defecto
        
        stats = self._error_stats[func_name]
        
        # Ajustar max_retries basado en tasa de éxito
        if stats.total_calls > 10:
            success_rate = stats.successful_calls / stats.total_calls
            if success_rate > 0.9:
                max_retries = 2  # Pocas fallas, menos reintentos
            elif success_rate > 0.7:
                max_retries = 3  # Tasa normal
            else:
                max_retries = 5  # Muchas fallas, más reintentos
        else:
            max_retries = 3  # Por defecto para funciones nuevas
        
        # Ajustar delays basado en tiempo de ejecución promedio
        if stats.avg_execution_time > 10.0:
            base_delay = 2.0  # Operaciones lentas necesitan más tiempo
            max_delay = 120.0
        elif stats.avg_execution_time > 5.0:
            base_delay = 1.5
            max_delay = 60.0
        else:
            base_delay = 1.0  # Operaciones rápidas
            max_delay = 30.0
        
        # Crear configuración adaptativa
        adaptive_config = RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_backoff=True,
            jitter=True
        )
        
        # Cachear configuración
        self._adaptive_configs[func_name] = {
            'config': adaptive_config,
            'last_updated': time.time(),
            'based_on_calls': stats.total_calls
        }
        
        logging.info(
            f"🧠 Configuración adaptativa para {func_name}: "
            f"max_retries={max_retries}, base_delay={base_delay}s"
        )
        
        return adaptive_config
    
    def with_retry(
        self,
        config: Optional[RetryConfig] = None,
        circuit_breaker_key: Optional[str] = None,
        fallback: Optional[Callable] = None,
        use_adaptive_config: bool = True,
        enable_prediction: bool = True,
        user_context: Optional[Dict] = None
    ):
        """
        Decorador AVANZADO para retry automático con múltiples mejoras.
        
        Args:
            config: Configuración de retry (se usa adaptativa si es None)
            circuit_breaker_key: Clave para circuit breaker
            fallback: Función de fallback en caso de fallo
            use_adaptive_config: Usar configuración adaptativa basada en historial
            enable_prediction: Habilitar predicción de errores
            user_context: Contexto del usuario para personalizar manejo de errores
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                func_name = f"{func.__module__}.{func.__name__}"
                execution_context = user_context or {}
                
                # Usar configuración adaptativa si está habilitada
                if use_adaptive_config and config is None:
                    retry_config = await self.get_adaptive_config(func_name)
                else:
                    retry_config = config or RetryConfig()
                
                # Predicción de errores si está habilitada
                if enable_prediction:
                    predictions = await self.predict_error_likelihood(func_name, execution_context)
                    if predictions.get("overall_risk", 0) > 0.8:
                        logging.warning(f" Alto riesgo de error detectado para {func_name}: {predictions}")
                        # Ajustar configuración preventivamente
                        retry_config.max_retries = min(retry_config.max_retries + 1, 7)
                        retry_config.base_delay *= 1.2
                
                # Verificar circuit breaker
                if circuit_breaker_key:
                    if not self._check_circuit_breaker(circuit_breaker_key):
                        logging.warning(f" Circuit breaker abierto para {func_name}")
                        
                        # Intentar estrategia de recuperación específica
                        recovery_result = await self._attempt_recovery(
                            circuit_breaker_key, "circuit_breaker_open", execution_context
                        )
                        if recovery_result:
                            logging.info(f" Recuperación exitosa para circuit breaker {circuit_breaker_key}")
                        else:
                            if fallback:
                                return await self._execute_fallback(fallback, *args, **kwargs)
                            raise CircuitBreakerOpenError(f"Circuit breaker abierto para {circuit_breaker_key}")
                
                # Obtener o crear estadísticas
                stats = self._get_or_create_stats(func_name)
                stats.total_calls += 1
                
                last_exception = None
                recovery_attempted = False
                
                for attempt in range(retry_config.max_retries + 1):
                    try:
                        start_time = time.time()
                        
                        # Ejecutar función con contexto mejorado
                        if asyncio.iscoroutinefunction(func):
                            result = await func(*args, **kwargs)
                        else:
                            result = func(*args, **kwargs)
                        
                        execution_time = time.time() - start_time
                        
                        # Registrar éxito con contexto
                        await self._record_success_advanced(
                            func_name, circuit_breaker_key, execution_time, execution_context, attempt
                        )
                        
                        return result
                        
                    except Exception as e:
                        last_exception = e
                        execution_time = time.time() - start_time
                        
                        # Crear contexto detallado del error
                        error_context = ErrorContext(
                            timestamp=time.time(),
                            function_name=func_name,
                            error_type=type(e).__name__,
                            error_message=str(e),
                            stack_trace=traceback.format_exc(),
                            attempt_number=attempt,
                            execution_time=execution_time,
                            user_context=execution_context
                        )
                        
                        # Intentar estrategia de recuperación automática
                        if not recovery_attempted and attempt < retry_config.max_retries:
                            recovery_result = await self._attempt_automatic_recovery(e, execution_context)
                            if recovery_result:
                                recovery_attempted = True
                                stats.recovery_attempts += 1
                                logging.info(f" Recuperación automática aplicada para {func_name}")
                                # Actualizar contexto con la recuperación
                                execution_context.update(recovery_result)
                                continue
                        
                        # Verificar si debemos reintentar
                        if not isinstance(e, retry_config.retry_on):
                            logging.error(f" Error no reintentable para {func_name}: {str(e)}")
                            await self._record_failure_advanced(
                                func_name, circuit_breaker_key, error_context
                            )
                            break
                        
                        if attempt == retry_config.max_retries:
                            logging.error(f" Máximo de reintentos alcanzado para {func_name}")
                            await self._record_failure_advanced(
                                func_name, circuit_breaker_key, error_context
                            )
                            break
                        
                        # Calcular delay inteligente para siguiente intento
                        delay = self._calculate_intelligent_delay(retry_config, attempt, e, stats)
                        
                        logging.warning(
                            f" Intento {attempt + 1}/{retry_config.max_retries + 1} falló para {func_name}: {str(e)}. "
                            f"Reintentando en {delay:.2f}s (estrategia: {retry_config.exponential_backoff})"
                        )
                        
                        await asyncio.sleep(delay)
                
                # Si llegamos aquí, todos los intentos fallaron
                await self._record_failure_advanced(
                    func_name, circuit_breaker_key, 
                    ErrorContext(
                        timestamp=time.time(),
                        function_name=func_name,
                        error_type=type(last_exception).__name__,
                        error_message=str(last_exception),
                        stack_trace=traceback.format_exc(),
                        attempt_number=retry_config.max_retries,
                        execution_time=0.0,
                        user_context=execution_context
                    )
                )
                
                # Intentar fallback con contexto
                if fallback:
                    try:
                        logging.info(f" Ejecutando fallback para {func_name}")
                        result = await self._execute_fallback(fallback, *args, **kwargs)
                        stats.successful_recoveries += 1
                        return result
                    except Exception as fallback_error:
                        logging.error(f" Fallback también falló para {func_name}: {str(fallback_error)}")
                
                # Re-lanzar la última excepción con contexto mejorado
                raise last_exception
            
            return wrapper
        return decorator
    
    async def _attempt_automatic_recovery(self, error: Exception, context: Dict) -> Optional[Dict]:
        """Intenta recuperación automática basada en el tipo de error"""
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()
        
        # Detectar patrón de error y aplicar estrategia correspondiente
        for pattern, strategy in self._recovery_strategies.items():
            if pattern in error_type or pattern in error_message:
                try:
                    return await strategy(error, context)
                except Exception as recovery_error:
                    logging.error(f" Error en estrategia de recuperación {pattern}: {recovery_error}")
        
        return None
    
    async def _attempt_recovery(self, key: str, error_type: str, context: Dict) -> bool:
        """Intenta recuperación para circuit breaker"""
        if error_type == "circuit_breaker_open":
            # Verificar health checks antes de intentar recuperación
            for service, health_check in self._health_check_functions.items():
                try:
                    if await health_check():
                        logging.info(f" Health check exitoso para {service}")
                        # Resetear circuit breaker si el servicio está saludable
                        self.reset_circuit_breaker(key)
                        return True
                except Exception as e:
                    logging.error(f" Health check falló para {service}: {e}")
        
        return False
    
    def _calculate_intelligent_delay(self, config: RetryConfig, attempt: int, error: Exception, stats: ErrorStats) -> float:
        """Calcula delay inteligente basado en contexto"""
        base_delay = self._calculate_delay(config, attempt)
        
        # Ajustar delay basado en tipo de error
        error_type = type(error).__name__
        if "timeout" in error_type.lower() or "timeout" in str(error).lower():
            base_delay *= 1.5  # Timeouts necesitan más tiempo
        elif "rate" in str(error).lower() or "limit" in str(error).lower():
            base_delay *= 2.0  # Rate limits necesitan espera mayor
        
        # Ajustar basado en historial de la función
        if stats.consecutive_failures > 3:
            base_delay *= 1.3  # Función problemática necesita más tiempo
        
        return min(base_delay, config.max_delay)
    
    async def _record_success_advanced(
        self, func_name: str, circuit_breaker_key: Optional[str], 
        execution_time: float, context: Dict, attempt: int
    ):
        """Registra éxito con contexto avanzado"""
        stats = self._get_or_create_stats(func_name)
        stats.successful_calls += 1
        stats.consecutive_successes += 1
        stats.consecutive_failures = 0
        stats.last_success_time = time.time()
        
        # Actualizar tiempo de ejecución promedio
        stats.total_execution_time += execution_time
        stats.avg_execution_time = stats.total_execution_time / stats.successful_calls
        
        # Actualizar circuit breaker
        if circuit_breaker_key and circuit_breaker_key in self._circuit_breakers:
            breaker = self._circuit_breakers[circuit_breaker_key]
            breaker['success_count'] += 1
            
            if breaker['state'] == CircuitBreakerState.HALF_OPEN:
                if breaker['success_count'] >= breaker['config'].success_threshold:
                    breaker['state'] = CircuitBreakerState.CLOSED
                    breaker['failure_count'] = 0
                    logging.info(f" Circuit breaker {circuit_breaker_key} recuperado (CLOSED)")
        
        # Log detallado para análisis
        if attempt > 0:
            logging.info(
                f" Éxito en {func_name} después de {attempt} intentos "
                f"(tiempo: {execution_time:.2f}s, promedio: {stats.avg_execution_time:.2f}s)"
            )
        else:
            logging.debug(f" Éxito en {func_name} (tiempo: {execution_time:.2f}s)")
    
    async def _record_failure_advanced(
        self, func_name: str, circuit_breaker_key: Optional[str], error_context: ErrorContext
    ):
        """Registra falla con contexto avanzado"""
        stats = self._get_or_create_stats(func_name)
        stats.failed_calls += 1
        stats.consecutive_failures += 1
        stats.consecutive_successes = 0
        stats.last_failure_time = time.time()
        
        # Agregar error al historial reciente
        stats.recent_errors.append({
            'timestamp': error_context.timestamp,
            'error_type': error_context.error_type,
            'error_message': error_context.error_message[:200],  # Truncar mensaje largo
            'attempt': error_context.attempt_number
        })
        
        # Contar tipo de error
        stats.error_counts[error_context.error_type] = stats.error_counts.get(error_context.error_type, 0) + 1
        
        # Analizar patrones de error
        error_pattern = f"{error_context.error_type}:{error_context.error_message[:50]}"
        stats.error_patterns[error_pattern] = stats.error_patterns.get(error_pattern, 0) + 1
        
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
                logging.error(f" Circuit breaker {circuit_breaker_key} ABIERTO por muchas fallas")
            elif breaker['state'] == CircuitBreakerState.HALF_OPEN:
                breaker['state'] = CircuitBreakerState.OPEN
                logging.error(f" Circuit breaker {circuit_breaker_key} vuelve a OPEN")
        
        # Log con contexto rico
        logging.error(
            f" Error en {func_name} (intento {error_context.attempt_number}): "
            f"{error_context.error_type} - {error_context.error_message} "
            f"(fallas consecutivas: {stats.consecutive_failures})"
        )
    
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
                logging.info(f" Circuit breaker {key} cambiando a HALF_OPEN")
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
                    logging.info(f" Circuit breaker {circuit_breaker_key} recuperado (CLOSED)")
        
        logging.debug(f" Éxito en {func_name} (tiempo: {execution_time:.2f}s)")
    
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
                logging.error(f" Circuit breaker {circuit_breaker_key} ABIERTO por muchas fallas")
            elif breaker['state'] == CircuitBreakerState.HALF_OPEN:
                breaker['state'] = CircuitBreakerState.OPEN
                logging.error(f" Circuit breaker {circuit_breaker_key} vuelve a OPEN")
    
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
            logging.info(f" Circuit breaker {key} reseteado")

class CircuitBreakerOpenError(Exception):
    """Excepción lanzada cuando el circuit breaker está abierto"""
    pass

# Instancia global del error handler avanzado
error_handler = AdvancedErrorHandler()

# Alias para compatibilidad hacia atrás
RobustErrorHandler = AdvancedErrorHandler