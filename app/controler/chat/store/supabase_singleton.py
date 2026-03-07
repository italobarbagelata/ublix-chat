"""
Singleton para cliente Supabase.
Evita crear múltiples conexiones a la base de datos.
"""
import os
import logging
import threading
from supabase import create_client, Client
from typing import Optional

logger = logging.getLogger(__name__)


class SupabaseSingleton:
    """
    Patrón Singleton thread-safe para el cliente de Supabase.
    Garantiza una única instancia del cliente en toda la aplicación.
    """
    _instance: Optional[Client] = None
    _lock = threading.Lock()
    _initialized = False

    @classmethod
    def get_client(cls) -> Client:
        """
        Obtiene la instancia única del cliente Supabase.
        Thread-safe usando double-checked locking.

        Returns:
            Client: Instancia del cliente Supabase

        Raises:
            ValueError: Si las variables de entorno no están configuradas
        """
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking
                if cls._instance is None:
                    supabase_url = os.getenv("SUPABASE_URL")
                    supabase_key = os.getenv("SUPABASE_KEY")

                    if not supabase_url or not supabase_key:
                        raise ValueError(
                            "SUPABASE_URL y SUPABASE_KEY deben estar configurados"
                        )

                    cls._instance = create_client(supabase_url, supabase_key)
                    cls._initialized = True
                    logger.info("Supabase client singleton inicializado")

        return cls._instance

    @classmethod
    def is_initialized(cls) -> bool:
        """Verifica si el singleton ya fue inicializado."""
        return cls._initialized

    @classmethod
    def reset(cls) -> None:
        """
        Resetea el singleton. Útil para testing.
        NO usar en producción.
        """
        with cls._lock:
            cls._instance = None
            cls._initialized = False
            logger.warning("Supabase singleton reseteado")


# Función de conveniencia para obtener el cliente
def get_supabase_client() -> Client:
    """
    Función de conveniencia para obtener el cliente Supabase.

    Returns:
        Client: Instancia única del cliente Supabase
    """
    return SupabaseSingleton.get_client()
