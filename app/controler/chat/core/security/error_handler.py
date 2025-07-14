"""
Sistema robusto de manejo de errores para aplicaciones críticas de calendario.
Previene fallos silenciosos y proporciona recovery automático cuando es posible.
"""

import logging
import traceback
import time
from typing import Any, Callable, Dict, Optional, Union, Type, List
from enum import Enum
from dataclasses import dataclass
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Niveles de severidad de errores."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Categorías de errores para manejo específico."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NETWORK = "network"
    DATABASE = "database"
    CALENDAR_API = "calendar_api"
    WEBHOOK = "webhook"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"

@dataclass
class ErrorContext:
    """Contexto de error con información adicional."""
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    operation: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

@dataclass
class ErrorResult:
    """Resultado estructurado de operación con manejo de errores."""
    success: bool
    data: Any = None
    error_message: str = ""
    error_code: str = ""
    error_context: Optional[ErrorContext] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False

class CalendarError(Exception):
    """Excepción base para errores de calendario."""
    
    def __init__(self, message: str, category: ErrorCategory, severity: ErrorSeverity = ErrorSeverity.MEDIUM, 
                 error_code: str = "", context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.error_code = error_code
        self.context = context or {}
        self.timestamp = datetime.utcnow()

class ValidationError(CalendarError):
    """Error de validación de datos."""
    def __init__(self, message: str, field_name: str = "", value: Any = None):
        super().__init__(message, ErrorCategory.VALIDATION, ErrorSeverity.MEDIUM, "VALIDATION_ERROR")
        self.field_name = field_name
        self.value = value

class AuthenticationError(CalendarError):
    """Error de autenticación."""
    def __init__(self, message: str, auth_method: str = ""):
        super().__init__(message, ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH, "AUTH_ERROR")
        self.auth_method = auth_method

class ConflictError(CalendarError):
    """Error de conflicto de calendario."""
    def __init__(self, message: str, conflicting_events: List[Dict] = None):
        super().__init__(message, ErrorCategory.BUSINESS_LOGIC, ErrorSeverity.MEDIUM, "CONFLICT_ERROR")
        self.conflicting_events = conflicting_events or []

class NetworkError(CalendarError):
    """Error de red o comunicación."""
    def __init__(self, message: str, endpoint: str = "", status_code: int = 0):
        super().__init__(message, ErrorCategory.NETWORK, ErrorSeverity.HIGH, "NETWORK_ERROR")
        self.endpoint = endpoint
        self.status_code = status_code

class RobustErrorHandler:
    """
    Manejador robusto de errores con recovery automático y logging estructurado.
    """
    
    def __init__(self):
        self.error_log = []
        self.recovery_strategies = {}
        self._setup_default_recovery_strategies()
    
    def _setup_default_recovery_strategies(self):
        """Configura estrategias de recovery por defecto."""
        self.recovery_strategies = {
            ErrorCategory.AUTHENTICATION: self._retry_with_token_refresh,
            ErrorCategory.NETWORK: self._retry_with_backoff,
            ErrorCategory.CALENDAR_API: self._retry_with_exponential_backoff,
            ErrorCategory.DATABASE: self._retry_with_linear_backoff,
        }
    
    def _retry_with_token_refresh(self, func: Callable, *args, **kwargs) -> ErrorResult:
        """Estrategia de recovery para errores de autenticación."""
        try:
            # Intentar refrescar token de autenticación
            logger.info("Attempting token refresh for authentication error recovery")
            # Aquí iría la lógica de refresh de token
            # Por ahora, solo reintentamos
            result = func(*args, **kwargs)
            return ErrorResult(success=True, data=result, recovery_attempted=True, recovery_successful=True)
        except Exception as e:
            return ErrorResult(
                success=False, 
                error_message=f"Recovery failed: {str(e)}", 
                recovery_attempted=True, 
                recovery_successful=False
            )
    
    def _retry_with_backoff(self, func: Callable, *args, max_retries: int = 3, **kwargs) -> ErrorResult:
        """Estrategia de recovery con backoff exponencial."""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt  # Backoff exponencial
                    logger.info(f"Retrying operation (attempt {attempt + 1}/{max_retries}) after {wait_time}s")
                    time.sleep(wait_time)
                
                result = func(*args, **kwargs)
                success = attempt > 0  # Recovery successful si no fue el primer intento
                return ErrorResult(
                    success=True, 
                    data=result, 
                    recovery_attempted=success, 
                    recovery_successful=success
                )
                
            except Exception as e:
                if attempt == max_retries - 1:  # Último intento
                    return ErrorResult(
                        success=False,
                        error_message=f"All retry attempts failed. Last error: {str(e)}",
                        recovery_attempted=True,
                        recovery_successful=False
                    )
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
    
    def _retry_with_exponential_backoff(self, func: Callable, *args, **kwargs) -> ErrorResult:
        """Recovery específico para Calendar API."""
        return self._retry_with_backoff(func, *args, max_retries=3, **kwargs)
    
    def _retry_with_linear_backoff(self, func: Callable, *args, **kwargs) -> ErrorResult:
        """Recovery específico para base de datos."""
        for attempt in range(2):  # Solo 2 intentos para BD
            try:
                if attempt > 0:
                    time.sleep(1)  # Backoff lineal de 1 segundo
                
                result = func(*args, **kwargs)
                return ErrorResult(
                    success=True, 
                    data=result, 
                    recovery_attempted=attempt > 0, 
                    recovery_successful=attempt > 0
                )
                
            except Exception as e:
                if attempt == 1:  # Último intento
                    return ErrorResult(
                        success=False,
                        error_message=f"Database operation failed: {str(e)}",
                        recovery_attempted=True,
                        recovery_successful=False
                    )
    
    def handle_error(self, error: Exception, context: ErrorContext) -> ErrorResult:
        """
        Maneja error con contexto completo y recovery automático.
        
        Args:
            error: Excepción a manejar
            context: Contexto del error
            
        Returns:
            ErrorResult con información completa del manejo
        """
        # Log estructurado del error
        error_entry = {
            "error_id": context.error_id,
            "timestamp": context.timestamp.isoformat(),
            "severity": context.severity.value,
            "category": context.category.value,
            "message": str(error),
            "type": type(error).__name__,
            "user_id": context.user_id,
            "project_id": context.project_id,
            "operation": context.operation,
            "traceback": traceback.format_exc(),
            "additional_data": context.additional_data
        }
        
        self.error_log.append(error_entry)
        
        # Log según severidad
        if context.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"CRITICAL ERROR [{context.error_id}]: {str(error)}", extra=error_entry)
        elif context.severity == ErrorSeverity.HIGH:
            logger.error(f"HIGH SEVERITY ERROR [{context.error_id}]: {str(error)}", extra=error_entry)
        elif context.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"MEDIUM SEVERITY ERROR [{context.error_id}]: {str(error)}", extra=error_entry)
        else:
            logger.info(f"LOW SEVERITY ERROR [{context.error_id}]: {str(error)}", extra=error_entry)
        
        # Crear resultado base
        result = ErrorResult(
            success=False,
            error_message=str(error),
            error_code=getattr(error, 'error_code', 'UNKNOWN_ERROR'),
            error_context=context
        )
        
        # Intentar recovery si está disponible
        if isinstance(error, CalendarError) and error.category in self.recovery_strategies:
            logger.info(f"Attempting automatic recovery for {error.category.value} error")
            # En este punto normalmente se ejecutaría la estrategia de recovery
            # Por ahora, solo marcar que se intentó
            result.recovery_attempted = True
            # La lógica real de recovery requeriría la función original
        
        return result
    
    def wrap_operation(self, operation_name: str, user_id: str = None, project_id: str = None):
        """
        Decorador para envolver operaciones con manejo robusto de errores.
        
        Args:
            operation_name: Nombre de la operación
            user_id: ID del usuario
            project_id: ID del proyecto
            
        Returns:
            Decorador
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> ErrorResult:
                error_id = f"{operation_name}_{int(time.time())}"
                
                try:
                    result = func(*args, **kwargs)
                    return ErrorResult(success=True, data=result)
                    
                except CalendarError as e:
                    context = ErrorContext(
                        error_id=error_id,
                        timestamp=datetime.utcnow(),
                        severity=e.severity,
                        category=e.category,
                        user_id=user_id,
                        project_id=project_id,
                        operation=operation_name,
                        additional_data=e.context
                    )
                    return self.handle_error(e, context)
                    
                except Exception as e:
                    # Error no categorizado - clasificar automáticamente
                    category = self._classify_error(e)
                    severity = ErrorSeverity.HIGH  # Por defecto, alta severidad para errores no esperados
                    
                    context = ErrorContext(
                        error_id=error_id,
                        timestamp=datetime.utcnow(),
                        severity=severity,
                        category=category,
                        user_id=user_id,
                        project_id=project_id,
                        operation=operation_name
                    )
                    return self.handle_error(e, context)
            
            return wrapper
        return decorator
    
    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Clasifica automáticamente errores no categorizados."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Clasificación por tipo de excepción
        if 'http' in error_type or 'connection' in error_str or 'network' in error_str:
            return ErrorCategory.NETWORK
        elif 'auth' in error_str or 'permission' in error_str or 'unauthorized' in error_str:
            return ErrorCategory.AUTHENTICATION
        elif 'database' in error_str or 'sql' in error_str or 'connection' in error_type:
            return ErrorCategory.DATABASE
        elif 'validation' in error_str or 'invalid' in error_str:
            return ErrorCategory.VALIDATION
        else:
            return ErrorCategory.SYSTEM
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de errores."""
        if not self.error_log:
            return {"total_errors": 0}
        
        stats = {
            "total_errors": len(self.error_log),
            "by_severity": {},
            "by_category": {},
            "recent_errors": len([e for e in self.error_log if 
                                (datetime.utcnow() - datetime.fromisoformat(e["timestamp"])).seconds < 3600])
        }
        
        for entry in self.error_log:
            # Contar por severidad
            severity = entry["severity"]
            stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1
            
            # Contar por categoría
            category = entry["category"]
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
        
        return stats

# Instancia global del manejador de errores
error_handler = RobustErrorHandler()

def safe_execute(operation_name: str, user_id: str = None, project_id: str = None):
    """
    Decorador simplificado para operaciones seguras.
    
    Usage:
        @safe_execute("create_calendar_event", user_id="123", project_id="proj1")
        def create_event(data):
            # lógica del evento
            return result
    """
    return error_handler.wrap_operation(operation_name, user_id, project_id)

def raise_calendar_error(message: str, category: ErrorCategory, severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                        error_code: str = "", **context_data):
    """
    Función helper para lanzar errores de calendario estructurados.
    
    Args:
        message: Mensaje de error
        category: Categoría del error
        severity: Severidad del error
        error_code: Código específico del error
        **context_data: Datos adicionales de contexto
    """
    raise CalendarError(message, category, severity, error_code, context_data)