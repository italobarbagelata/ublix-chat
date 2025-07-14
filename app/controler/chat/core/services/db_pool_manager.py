"""
Gestor de pool de conexiones para optimizar operaciones de base de datos.
Mejora el rendimiento y previene el agotamiento de conexiones.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, AsyncContextManager
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import threading
from datetime import datetime

from app.controler.chat.store.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)

class DatabasePoolManager:
    """
    Gestor de pool de conexiones para operaciones de base de datos.
    Optimiza el rendimiento mediante reutilización de conexiones y control de concurrencia.
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
        
        # Pool de ejecutores para operaciones síncronas
        self.read_executor = ThreadPoolExecutor(
            max_workers=10, 
            thread_name_prefix="db_read"
        )
        self.write_executor = ThreadPoolExecutor(
            max_workers=5, 
            thread_name_prefix="db_write"
        )
        
        # Semáforos para control de concurrencia
        self.read_semaphore = asyncio.Semaphore(20)  # Máximo 20 lecturas concurrentes
        self.write_semaphore = asyncio.Semaphore(5)  # Máximo 5 escrituras concurrentes
        
        # Pool de clientes Supabase reutilizables
        self._client_pool = []
        self._pool_size = 5
        self._pool_lock = asyncio.Lock()
        
        # Estadísticas
        self.stats = {
            'total_operations': 0,
            'read_operations': 0,
            'write_operations': 0,
            'pool_hits': 0,
            'pool_misses': 0,
            'errors': 0
        }
        
        self._initialized = True
        self.logger.info("DatabasePoolManager inicializado")
    
    async def initialize_pool(self):
        """Inicializa el pool de conexiones."""
        try:
            async with self._pool_lock:
                for _ in range(self._pool_size):
                    client = SupabaseClient()
                    self._client_pool.append(client)
                
                self.logger.info(f"Pool de conexiones inicializado con {self._pool_size} clientes")
        except Exception as e:
            self.logger.error(f"Error inicializando pool: {str(e)}")
            raise
    
    @asynccontextmanager
    async def get_client(self) -> AsyncContextManager[SupabaseClient]:
        """
        Obtiene un cliente del pool de forma thread-safe.
        
        Returns:
            Cliente Supabase reutilizable
        """
        client = None
        try:
            async with self._pool_lock:
                if self._client_pool:
                    client = self._client_pool.pop()
                    self.stats['pool_hits'] += 1
                else:
                    client = SupabaseClient()
                    self.stats['pool_misses'] += 1
            
            yield client
            
        except Exception as e:
            self.logger.error(f"Error usando cliente del pool: {str(e)}")
            self.stats['errors'] += 1
            raise
        finally:
            if client:
                async with self._pool_lock:
                    if len(self._client_pool) < self._pool_size:
                        self._client_pool.append(client)
    
    async def execute_read_operation(self, operation_func, *args, **kwargs) -> Any:
        """
        Ejecuta operación de lectura con pool optimizado.
        
        Args:
            operation_func: Función a ejecutar
            *args: Argumentos posicionales
            **kwargs: Argumentos con nombre
            
        Returns:
            Resultado de la operación
        """
        async with self.read_semaphore:
            try:
                self.stats['total_operations'] += 1
                self.stats['read_operations'] += 1
                
                # CRÍTICO: run_in_executor NO acepta **kwargs
                # Necesitamos crear una función wrapper que los convierta
                def wrapper():
                    return operation_func(*args, **kwargs)
                
                result = await asyncio.get_event_loop().run_in_executor(
                    self.read_executor,
                    wrapper
                )
                
                return result
                
            except Exception as e:
                self.stats['errors'] += 1
                self.logger.error(f"Error en operación de lectura: {str(e)}")
                raise
    
    async def execute_write_operation(self, operation_func, *args, **kwargs) -> Any:
        """
        Ejecuta operación de escritura con pool optimizado.
        
        Args:
            operation_func: Función a ejecutor
            *args: Argumentos posicionales
            **kwargs: Argumentos con nombre
            
        Returns:
            Resultado de la operación
        """
        async with self.write_semaphore:
            try:
                self.stats['total_operations'] += 1
                self.stats['write_operations'] += 1
                
                # CRÍTICO: run_in_executor NO acepta **kwargs
                # Necesitamos crear una función wrapper que los convierta
                def wrapper():
                    return operation_func(*args, **kwargs)
                
                result = await asyncio.get_event_loop().run_in_executor(
                    self.write_executor,
                    wrapper
                )
                
                return result
                
            except Exception as e:
                self.stats['errors'] += 1
                self.logger.error(f"Error en operación de escritura: {str(e)}")
                raise
    
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
                # Determinar si es operación de lectura o escritura
                is_write_op = any(
                    write_keyword in operation_func.__name__.lower() 
                    for write_keyword in ['insert', 'update', 'delete', 'create', 'modify']
                )
                
                if is_write_op:
                    return await self.execute_write_operation(operation_func, *args, **kwargs)
                else:
                    return await self.execute_read_operation(operation_func, *args, **kwargs)
                
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
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica el estado del pool de conexiones.
        
        Returns:
            Estado del pool y estadísticas
        """
        try:
            async with self._pool_lock:
                pool_status = {
                    'available_connections': len(self._client_pool),
                    'max_pool_size': self._pool_size,
                    'read_executor_active': not self.read_executor._shutdown,
                    'write_executor_active': not self.write_executor._shutdown,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Test de conectividad
            try:
                async with self.get_client() as client:
                    # Operación simple para verificar conectividad
                    test_result = await self.execute_read_operation(
                        lambda: client.client.table("projects").select("id").limit(1).execute()
                    )
                    pool_status['connectivity_test'] = 'passed'
            except Exception as e:
                pool_status['connectivity_test'] = f'failed: {str(e)}'
            
            pool_status.update(self.stats)
            return pool_status
            
        except Exception as e:
            self.logger.error(f"Error en health check: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def cleanup(self):
        """Limpia recursos del pool."""
        try:
            # Cerrar ejecutores
            self.read_executor.shutdown(wait=True)
            self.write_executor.shutdown(wait=True)
            
            # Limpiar pool de clientes
            async with self._pool_lock:
                self._client_pool.clear()
            
            self.logger.info("DatabasePoolManager cleanup completado")
            
        except Exception as e:
            self.logger.error(f"Error en cleanup de DatabasePoolManager: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del pool."""
        return {
            **self.stats,
            'pool_size': len(self._client_pool),
            'max_pool_size': self._pool_size,
            'efficiency': (
                self.stats['pool_hits'] / 
                (self.stats['pool_hits'] + self.stats['pool_misses'])
                if (self.stats['pool_hits'] + self.stats['pool_misses']) > 0 
                else 0
            )
        }

# Instancia global del pool manager
db_pool = DatabasePoolManager()