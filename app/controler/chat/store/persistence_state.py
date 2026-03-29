import base64
import msgpack
import logging
from app.controler.chat.classes.chat_state import ChatState
from typing import List
from app.controler.chat.classes.token_metrics import TokenMetrics
from app.resources.constants import TOKEN_METRICS_TABLE
from app.database import Database, SyncDatabase


class MemoryStatePersistence:
    def __init__(self):
        """Initializes the database connection."""
        self.logger = logging.getLogger(__name__)
        self.db = Database()
        self.sync_db = SyncDatabase()

    async def save_state(self, state: ChatState) -> None:
        """Saves or updates the chat state in the database."""
        try:
            self.logger.info(f"Iniciando save_state para project_id: {state.project_id}, user_id: {state.user_id}")
            self.logger.info(f"Estado a guardar - tipo: {type(state.state)}, keys: {list(state.state.keys()) if isinstance(state.state, dict) else 'N/A'}")

            # Serialize state with msgpack and encode in base64
            binary_state = msgpack.packb(state.state)
            base64_state = base64.b64encode(binary_state).decode("utf-8")
            self.logger.info(f"Estado serializado correctamente. Tamano: {len(base64_state)} bytes")

            data = {
                "project_id": state.project_id,
                "user_id": state.user_id,
                "state": base64_state
            }

            # UPSERT
            self.logger.info(f"Ejecutando upsert en tabla memory_states...")
            response = await self.db.table("memory_states") \
                .upsert(data, on_conflict="project_id,user_id") \
                .execute()

            self.logger.info(f"Upsert completado. Response data count: {len(response.data) if response.data else 0}")
            self.logger.info(f"Estado guardado exitosamente para project_id: {state.project_id}, user_id: {state.user_id}")

        except Exception as e:
            self.logger.error(f"Error en save_state: {e}", exc_info=True)
            raise

    async def fetch_state(self, project_id: str, user_id: str) -> dict:
        """Retrieves the chat state from the database."""
        try:
            self.logger.info(f"Iniciando fetch_state para project_id: {project_id}, user_id: {user_id}")

            response = await self.db.table("memory_states") \
                .select("*") \
                .eq("project_id", project_id) \
                .eq("user_id", user_id) \
                .limit(1) \
                .execute()

            self.logger.info(f"Query ejecutada. Response data count: {len(response.data) if response.data else 0}")

            if response.data:
                row = response.data[0]
                self.logger.info(f"Registro encontrado. Deserializando estado...")

                # Decode from base64 and deserialize with msgpack
                binary_data = base64.b64decode(row["state"])
                unpacked_state = msgpack.unpackb(binary_data, strict_map_key=False)

                self.logger.debug(f"Estado recuperado para usuario {user_id}")

                return {
                    "project_id": row["project_id"],
                    "user_id": row["user_id"],
                    "state": unpacked_state
                }
            else:
                self.logger.debug(f"Sin estado previo para usuario {user_id}")

            return None

        except Exception as e:
            self.logger.error(f"Error en fetch_state: {e}", exc_info=True)
            return None

    def save_token_metrics(self, metrics: TokenMetrics):
        """Saves token metrics to the database (synchronous for executor)."""
        try:
            data = metrics.dict()

            # Convert datetime to ISO format
            if 'timestamp' in data:
                data['timestamp'] = data['timestamp'].isoformat()

            response = self.sync_db.table(TOKEN_METRICS_TABLE).insert(data).execute()

            if not response.data:
                self.logger.error(f"Error al guardar metricas de tokens")
                return False

            self.logger.info(f"Token metrics guardadas exitosamente en DB")
            return True

        except Exception as e:
            self.logger.error(f"Error al guardar metricas: {str(e)}")
            return False

    async def get_project_token_metrics(self, project_id: str) -> List[TokenMetrics]:
        """Gets all metrics for a project."""
        response = await self.db.table("token_metrics") \
            .select("*") \
            .eq("project_id", project_id) \
            .execute()

        return [TokenMetrics(**row) for row in response.data]

    async def get_user_token_metrics(self, user_id: str) -> List[TokenMetrics]:
        """Gets all metrics for a user."""
        response = await self.db.table("token_metrics") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()

        return [TokenMetrics(**row) for row in response.data]

    async def get_conversation_token_metrics(self, conversation_id: str) -> List[TokenMetrics]:
        """Gets all metrics for a conversation."""
        response = await self.db.table("token_metrics") \
            .select("*") \
            .eq("conversation_id", conversation_id) \
            .execute()

        return [TokenMetrics(**row) for row in response.data]
