"""
Gestor simplificado para ejecutar operaciones de base de datos con retry automático.
"""

import asyncio
import logging
from typing import Any
from concurrent.futures import ThreadPoolExecutor
import threading


logger = logging.getLogger(__name__)

class DatabasePoolManager:
    """
    Gestor simplificado para operaciones de base de datos con retry automático.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.logger = logging.getLogger(__name__)
        
        # Ejecutor para operaciones síncronas
        self.executor = ThreadPoolExecutor(
            max_workers=10, 
            thread_name_prefix="db_operations"
        )
        
        # Semáforo para control de concurrencia
        self.semaphore = asyncio.Semaphore(20)
        
        self._initialized = True
        self.logger.info("DatabasePoolManager inicializado")
    
    async def execute_with_retry(self, operation_func, max_retries: int = 3, 
                               base_delay: float = 1.0, *args, **kwargs) -> Any:
        """
        Ejecuta operación con retry automático y backoff exponencial.
        
        Args:
            operation_func: Función a ejecutar
            max_retries: Número máximo de reintentos
            base_delay: Delay base en segundos
            *args: Argumentos posicionales
            **kwargs: Argumentos con nombre
            
        Returns:
            Resultado de la operación
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                async with self.semaphore:
                    # Wrapper para ejecutar la función con argumentos
                    def wrapper():
                        return operation_func(*args, **kwargs)
                    
                    result = await asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        wrapper
                    )
                    
                    return result
                
            except Exception as e:
                last_exception = e
                
                if attempt < max_retries:
                    wait_time = base_delay * (2 ** attempt)
                    self.logger.warning(
                        f"Operación falló (intento {attempt + 1}/{max_retries + 1}), "
                        f"reintentando en {wait_time}s: {str(e)}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"Operación falló después de {max_retries + 1} intentos")
                    raise last_exception
        
        raise last_exception

# Instancia global del pool manager
db_pool = DatabasePoolManager()