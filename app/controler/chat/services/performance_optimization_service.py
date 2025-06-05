import logging
import asyncio
import time
from typing import Dict, Any, Optional
from functools import lru_cache
import redis
import json

class PerformanceOptimizationService:
    """Servicio para optimizar performance y velocidad de respuesta"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.logger = logging.getLogger(__name__)
        self.redis_client = redis_client
        self._response_cache = {}
        self._cache_ttl = 300  # 5 minutos
    
    @lru_cache(maxsize=100)
    def get_cached_model_config(self, model_name: str) -> Dict[str, Any]:
        """Cache de configuraciones de modelo para evitar lookups repetidos"""
        # Configuraciones optimizadas por modelo
        configs = {
            "gpt-4.1-mini": {
                "temperature": 0.1,
                "max_tokens": 1000,
                "top_p": 0.9,
                "streaming": True
            },
            "gpt-3.5-turbo": {
                "temperature": 0.1, 
                "max_tokens": 800,
                "top_p": 0.9,
                "streaming": True
            },
            "claude-3-sonnet": {
                "temperature": 0.1,
                "max_tokens": 1000,
                "top_p": 0.9,
                "streaming": True
            }
        }
        return configs.get(model_name, configs["gpt-4.1-mini"])
    
    async def get_cached_response(self, cache_key: str) -> Optional[str]:
        """
        Obtiene respuesta desde cache Redis/Memory para consultas similares
        """
        try:
            # Intentar Redis primero si está disponible
            if self.redis_client:
                cached = await asyncio.to_thread(self.redis_client.get, cache_key)
                if cached:
                    return json.loads(cached)
            
            # Fallback a cache en memoria
            if cache_key in self._response_cache:
                entry = self._response_cache[cache_key]
                if time.time() - entry["timestamp"] < self._cache_ttl:
                    return entry["response"]
                else:
                    del self._response_cache[cache_key]
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Error accessing cache: {e}")
            return None
    
    async def cache_response(self, cache_key: str, response: str):
        """Cachea respuesta para consultas futuras similares"""
        try:
            # Guardar en Redis si está disponible
            if self.redis_client:
                await asyncio.to_thread(
                    self.redis_client.setex, 
                    cache_key, 
                    self._cache_ttl, 
                    json.dumps(response)
                )
            
            # Guardar en memoria como backup
            self._response_cache[cache_key] = {
                "response": response,
                "timestamp": time.time()
            }
            
            # Limpiar cache en memoria si es muy grande
            if len(self._response_cache) > 50:
                oldest_key = min(self._response_cache.keys(), 
                               key=lambda k: self._response_cache[k]["timestamp"])
                del self._response_cache[oldest_key]
                
        except Exception as e:
            self.logger.warning(f"Error caching response: {e}")
    
    def generate_cache_key(self, message: str, user_id: str, project_id: str) -> str:
        """Genera clave de cache basada en mensaje y contexto"""
        # Normalizar mensaje para cache
        normalized_message = message.lower().strip()
        
        # Crear hash para cache key
        import hashlib
        cache_input = f"{normalized_message}:{user_id}:{project_id}"
        cache_key = hashlib.md5(cache_input.encode()).hexdigest()
        
        return f"chat_response:{cache_key}"
    
    async def warm_up_model(self, model_name: str):
        """
        Pre-calentamiento del modelo para reducir cold start
        """
        try:
            # Esto podría ser una llamada simple al modelo para "calentarlo"
            self.logger.info(f"Warming up model: {model_name}")
            # Implementar lógica específica de warm-up según tu provider
            
        except Exception as e:
            self.logger.warning(f"Model warm-up failed: {e}")
    
    def get_optimized_batch_size(self, operation_type: str) -> int:
        """Tamaños de batch optimizados para diferentes operaciones"""
        batch_sizes = {
            "token_calculation": 10,
            "memory_optimization": 5,
            "metric_processing": 20,
            "embedding_generation": 8
        }
        return batch_sizes.get(operation_type, 5)
    
    async def parallel_token_calculation_optimized(self, tasks: list) -> list:
        """
        Cálculo de tokens con paralelización optimizada
        """
        batch_size = self.get_optimized_batch_size("token_calculation")
        results = []
        
        # Procesar en batches para evitar saturar el sistema
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)
            
            # Pequeña pausa entre batches para no saturar
            if i + batch_size < len(tasks):
                await asyncio.sleep(0.01)
        
        return results
    
    def should_use_cache(self, message: str) -> bool:
        """
        Determina si un mensaje debería usar cache basado en patrones
        """
        # Patrones que se benefician de cache
        cache_patterns = [
            "hola", "hello", "hi", "buenos días", "buenas tardes",
            "¿cómo estás?", "how are you", "help", "ayuda",
            "qué puedes hacer", "what can you do"
        ]
        
        message_lower = message.lower().strip()
        
        # Cache para saludos y preguntas frecuentes
        for pattern in cache_patterns:
            if pattern in message_lower:
                return True
        
        # Cache para mensajes muy cortos (probablemente preguntas simples)
        if len(message.split()) <= 3:
            return True
            
        return False 