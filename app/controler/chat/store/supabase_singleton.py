"""
Database singleton - now using direct PostgreSQL via SQLAlchemy.
Kept for backward compatibility with existing imports.
"""
import logging
from app.database import SyncDatabase

logger = logging.getLogger(__name__)

# Singleton instance
_db_instance = None


class SupabaseSingleton:
    """
    Backward-compatible singleton.
    Returns a SyncDatabase instance instead of Supabase Client.
    """

    @classmethod
    def get_client(cls) -> SyncDatabase:
        """
        Returns the singleton SyncDatabase instance.
        """
        global _db_instance
        if _db_instance is None:
            _db_instance = SyncDatabase()
            logger.info("Database singleton initialized (PostgreSQL direct)")
        return _db_instance

    @classmethod
    def is_initialized(cls) -> bool:
        return _db_instance is not None

    @classmethod
    def reset(cls) -> None:
        global _db_instance
        _db_instance = None
        logger.warning("Database singleton reset")


def get_supabase_client() -> SyncDatabase:
    """Convenience function to get the database client."""
    return SupabaseSingleton.get_client()
