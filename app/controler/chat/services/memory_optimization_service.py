import logging
import asyncio
from collections import OrderedDict
from app.controler.chat.classes.chat_state import ChatState
from app.controler.chat.store.persistence_state import MemoryStatePersistence

class MemoryOptimizationService:
    """Servicio para optimizar y persistir el estado de memoria"""
    
    def __init__(self, max_keys: int = 5):
        self.logger = logging.getLogger(__name__)
        self.database_state = MemoryStatePersistence()
        self.max_keys = max_keys
    
    async def optimize_and_save_state(self, graph, project_id: str, user_id: str):
        """Optimiza y guarda el estado de memoria eliminando entradas antiguas"""
        try:
            final_memory_state_dict = graph.checkpointer.storage.get(user_id)
            
            if final_memory_state_dict:
                state_to_optimize = final_memory_state_dict.get('', {})
                
                if isinstance(state_to_optimize, dict):
                    nested_dict = OrderedDict(state_to_optimize)
                    original_keys = len(nested_dict)
                    
                    # Eliminar entradas antiguas si exceden el máximo
                    while len(nested_dict) > self.max_keys:
                        nested_dict.popitem(last=False)
                    
                    final_memory_state_dict[''] = nested_dict
                    
                    # Crear estado para guardar
                    chat_state_to_save = ChatState(project_id=project_id, user_id=user_id)
                    chat_state_to_save.state = final_memory_state_dict
                    
                    # Guardar en hilo separado
                    await asyncio.to_thread(self.database_state.save_state, chat_state_to_save)
                    
                    if original_keys > self.max_keys:
                        self.logger.info(
                            f"Estado de memoria optimizado: {original_keys} -> {len(nested_dict)} keys"
                        )
                else:
                    self.logger.warning(f"Estado de memoria no válido para user {user_id}")
            else:
                self.logger.warning(f"No se encontró estado de memoria final para user {user_id}")
                
        except Exception as e:
            self.logger.error(f"Error optimizing memory state: {e}", exc_info=True)
    
    def load_initial_state(self, project_id: str, user_id: str) -> dict:
        """Carga el estado inicial de memoria desde la base de datos"""
        try:
            state = self.database_state.fetch_state(project_id, user_id)
            if state and isinstance(state.get("state"), dict):
                self.logger.info(f"Loaded state from DB for user {user_id}")
                return {user_id: state["state"]}
            else:
                if state:
                    self.logger.warning(f"Formato de estado inválido recuperado para {user_id}")
                return {}
        except Exception as e:
            self.logger.error(f"Error loading initial state: {e}", exc_info=True)
            return {} 