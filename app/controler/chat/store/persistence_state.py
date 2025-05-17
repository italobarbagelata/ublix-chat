import os
import base64
import msgpack
import logging
from supabase import create_client, Client
from app.controler.chat.classes.chat_state import ChatState
from typing import List
from app.controler.chat.classes.token_metrics import TokenMetrics
from app.resources.constants import TOKEN_METRICS_TABLE


class MemoryStatePersistence:
    def __init__(self):
        """Inicializa la conexión con Supabase"""
        self.logger = logging.getLogger(__name__)
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            self.logger.error("Faltan variables de entorno SUPABASE_URL o SUPABASE_KEY")
            raise ValueError("Faltan variables de entorno para Supabase")
            
        try:
            self.client: Client = create_client(supabase_url, supabase_key)
        except Exception as e:
            self.logger.error(f"Error al conectar con Supabase: {e}")
            raise

    def save_state(self, state: ChatState) -> None:
        """Guarda o actualiza el estado del chat en Supabase"""
        # Serializamos el estado con msgpack y lo codificamos en base64 para evitar errores de JSON
        binary_state = msgpack.packb(state.state)
        base64_state = base64.b64encode(binary_state).decode("utf-8")

        data = {
            "project_id": state.project_id,
            "user_id": state.user_id,
            "state": base64_state
        }

        # UPSERT usando Supabase
        self.client.table("memory_states") \
            .upsert(data, on_conflict="project_id,user_id") \
            .execute()

    def fetch_state(self, project_id: str, user_id: str) -> dict:
        """Recupera el estado del chat desde Supabase"""
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

            return {
                "project_id": row["project_id"],
                "user_id": row["user_id"],
                "state": unpacked_state
            }

        return None

    def save_token_metrics(self, metrics: TokenMetrics):
        """Guarda las métricas de tokens en Supabase"""
        try:
            data = metrics.dict()
            
            # Convertir el datetime a ISO format
            if 'timestamp' in data:
                data['timestamp'] = data['timestamp'].isoformat()
                
            response = self.client.table(TOKEN_METRICS_TABLE).insert(data).execute()
            
            if hasattr(response, 'error') and response.error:
                self.logger.error(f"Error de Supabase al guardar métricas: {response.error}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error al guardar métricas: {str(e)}")
            return False

    def get_project_token_metrics(self, project_id: str) -> List[TokenMetrics]:
        """Obtiene todas las métricas de un proyecto"""
        response = self.client.table("token_metrics") \
            .select("*") \
            .eq("project_id", project_id) \
            .execute()
        
        return [TokenMetrics(**row) for row in response.data]

    def get_user_token_metrics(self, user_id: str) -> List[TokenMetrics]:
        """Obtiene todas las métricas de un usuario"""
        response = self.client.table("token_metrics") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()
        
        return [TokenMetrics(**row) for row in response.data]

    def get_conversation_token_metrics(self, conversation_id: str) -> List[TokenMetrics]:
        """Obtiene todas las métricas de una conversación"""
        response = self.client.table("token_metrics") \
            .select("*") \
            .eq("conversation_id", conversation_id) \
            .execute()
        
        return [TokenMetrics(**row) for row in response.data]