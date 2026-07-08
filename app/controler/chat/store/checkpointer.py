"""
Native LangGraph Postgres checkpointer.

Replaces the previous manual approach (serializing MemorySaver.storage with
msgpack+base64 into the `memory_states` table). LangGraph now persists and
restores conversation state directly in Postgres via AsyncPostgresSaver, which
removes the fragile manual (de)serialization, the unbounded state growth and
the save/fetch race conditions.

Uses a single shared connection pool (psycopg3) pointing at the same Postgres
instance as the rest of the app.
"""
import logging
from typing import Optional

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.database import get_database_url

logger = logging.getLogger(__name__)

_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None


def _get_psycopg_conninfo() -> str:
    """Convert the SQLAlchemy URL into a plain psycopg3 conninfo string.

    psycopg3 expects `postgresql://...` without the SQLAlchemy driver suffix.
    """
    url = get_database_url()
    for prefix in (
        "postgresql+asyncpg://",
        "postgresql+psycopg2://",
        "postgresql+psycopg://",
    ):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url


async def get_checkpointer() -> AsyncPostgresSaver:
    """Return the shared AsyncPostgresSaver, opening the pool on first use."""
    global _pool, _checkpointer
    if _checkpointer is None:
        _pool = AsyncConnectionPool(
            conninfo=_get_psycopg_conninfo(),
            max_size=20,
            open=False,
            kwargs={
                # Required by the checkpointer: each op runs in its own txn.
                "autocommit": True,
                # Safe with connection pooling / poolers.
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
        await _pool.open(wait=True)
        _checkpointer = AsyncPostgresSaver(_pool)
        logger.info("Postgres checkpointer pool opened")
    return _checkpointer


async def setup_checkpointer() -> None:
    """Create the checkpointer tables if missing. Idempotent. Call on startup."""
    checkpointer = await get_checkpointer()
    await checkpointer.setup()
    logger.info("Postgres checkpointer tables ready")


async def close_checkpointer() -> None:
    """Close the pool on app shutdown."""
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
    _pool = None
    _checkpointer = None
    logger.info("Postgres checkpointer pool closed")
