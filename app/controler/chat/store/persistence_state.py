import os
import base64
import msgpack
import logging
from supabase import create_client, Client
from app.controler.chat.classes.chat_state import ChatState
from typing import List
from app.controler.chat.classes.token_metrics import TokenMetrics
from app.resources.constants import TOKEN_METRICS_TABLE
import time
from functools import lru_cache


class MemoryStatePersistence:
    def __init__(self):
        """Inicializa la conexión con Supabase con optimizaciones"""
        self.logger = logging.getLogger(__name__)
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            self.logger.error("Faltan variables de entorno SUPABASE_URL o SUPABASE_KEY")
            raise ValueError("Faltan variables de entorno para Supabase")
            
        try:
            self.client: Client = create_client(supabase_url, supabase_key)
            
            # Cache temporal para estados frecuentemente accedidos
            self._state_cache = {}
            self._cache_ttl = 60  # 1 minuto de cache
            
        except Exception as e:
            self.logger.error(f"Error al conectar con Supabase: {e}")
            raise

    def _get_cache_key(self, project_id: str, user_id: str) -> str:
        """Genera clave de cache para un estado"""
        return f"{project_id}:{user_id}"

    def _is_cache_valid(self, cache_entry) -> bool:
        """Verifica si una entrada de cache sigue siendo válida"""
        if not cache_entry:
            return False
        return (time.time() - cache_entry.get('timestamp', 0)) < self._cache_ttl

    def save_state(self, state: ChatState) -> None:
        """Guarda o actualiza el estado del chat en Supabase con optimizaciones"""
        try:
            # Serializamos el estado con msgpack y lo codificamos en base64 para evitar errores de JSON
            binary_state = msgpack.packb(state.state)
            base64_state = base64.b64encode(binary_state).decode("utf-8")

            data = {
                "project_id": state.project_id,
                "user_id": state.user_id,
                "state": base64_state
            }

            # UPSERT usando Supabase con timeout optimizado
            response = self.client.table("memory_states") \
                .upsert(data, on_conflict="project_id,user_id") \
                .execute()
            
            # Actualizar cache después de guardar exitosamente
            cache_key = self._get_cache_key(state.project_id, state.user_id)
            self._state_cache[cache_key] = {
                "data": {
                    "project_id": state.project_id,
                    "user_id": state.user_id,
                    "state": state.state
                },
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(f"Error en save_state: {e}", exc_info=True)
            raise

    def fetch_state(self, project_id: str, user_id: str) -> dict:
        """Recupera el estado del chat desde Supabase con cache optimizado"""
        try:
            # Verificar cache primero
            cache_key = self._get_cache_key(project_id, user_id)
            cached_entry = self._state_cache.get(cache_key)
            
            if cached_entry and self._is_cache_valid(cached_entry):
                return cached_entry["data"]
            
            # Si no está en cache o expiró, consultar base de datos
            response = self.client.table("memory_states") \
                .select("*") \
                .eq("project_id", project_id) \
                .eq("user_id", user_id) \
                .limit(1) \
                .execute()

            if response.data:
                row = response.data[0]
                
                # Decodificamos desde base64 y luego deserializamos con msgpack
                binary_data = base64.b64decode(row["state"])
                unpacked_state = msgpack.unpackb(binary_data, strict_map_key=False)

                result = {
                    "project_id": row["project_id"],
                    "user_id": row["user_id"],
                    "state": unpacked_state
                }
                
                # Actualizar cache
                self._state_cache[cache_key] = {
                    "data": result,
                    "timestamp": time.time()
                }
                
                return result

            return None
            
        except Exception as e:
            self.logger.error(f"Error en fetch_state: {e}", exc_info=True)
            return None

    def save_token_metrics(self, metrics: TokenMetrics):
        """Guarda las métricas de tokens en Supabase con optimizaciones"""
        try:
            data = metrics.dict()
            
            # Convertir el datetime a ISO format
            if 'timestamp' in data:
                data['timestamp'] = data['timestamp'].isoformat()
            
            # Usar insert optimizado sin verificar duplicados (asumiendo que conversation_id + message_id son únicos)
            response = self.client.table(TOKEN_METRICS_TABLE).insert(data).execute()
            
            if hasattr(response, 'error') and response.error:
                self.logger.error(f"Error de Supabase al guardar métricas: {response.error}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error al guardar métricas: {str(e)}")
            return False

    @lru_cache(maxsize=100)
    def get_project_token_metrics(self, project_id: str) -> List[TokenMetrics]:
        """Obtiene todas las métricas de un proyecto con cache LRU"""
        try:
            response = self.client.table("token_metrics") \
                .select("*") \
                .eq("project_id", project_id) \
                .order("timestamp", desc=True) \
                .limit(1000) \
                .execute()
            
            return [TokenMetrics(**row) for row in response.data]
        except Exception as e:
            self.logger.error(f"Error getting project metrics: {e}")
            return []

    @lru_cache(maxsize=100)
    def get_user_token_metrics(self, user_id: str) -> List[TokenMetrics]:
        """Obtiene todas las métricas de un usuario con cache LRU"""
        try:
            response = self.client.table("token_metrics") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("timestamp", desc=True) \
                .limit(1000) \
                .execute()
            
            return [TokenMetrics(**row) for row in response.data]
        except Exception as e:
            self.logger.error(f"Error getting user metrics: {e}")
            return []

    def get_conversation_token_metrics(self, conversation_id: str) -> List[TokenMetrics]:
        """Obtiene todas las métricas de una conversación (no cached ya que es específico)"""
        try:
            response = self.client.table("token_metrics") \
                .select("*") \
                .eq("conversation_id", conversation_id) \
                .execute()
            
            return [TokenMetrics(**row) for row in response.data]
        except Exception as e:
            self.logger.error(f"Error getting conversation metrics: {e}")
            return []

    def clear_cache(self):
        """Limpia todos los caches para liberar memoria"""
        self._state_cache.clear()
        self.get_project_token_metrics.cache_clear()
        self.get_user_token_metrics.cache_clear()
        self.logger.info("Cache cleared successfully")