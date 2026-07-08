"""
Database module - PostgreSQL async connection using SQLAlchemy Core.
Replaces Supabase client with direct PostgreSQL connection.
Provides a compatible API to minimize controller changes.
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from uuid import UUID
from collections import OrderedDict, defaultdict
import base64

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Global engines
_engine = None  # async (asyncpg)
_sync_engine = None  # sync (psycopg2)
_async_session_factory = None

_ISO_DATETIME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}')


def _coerce_param(value: Any) -> Any:
    """Coerce Python values into types the DB driver accepts.

    - ISO-8601 datetime strings -> datetime objects.
    - list/dict -> JSON string, since neither asyncpg nor psycopg2
      auto-serialize Python containers for json/jsonb columns.
    """
    if isinstance(value, str) and _ISO_DATETIME_RE.match(value):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return value


def _row_to_dict(row) -> Dict:
    """Convert a SQLAlchemy row to a JSON-friendly dict.

    asyncpg/psycopg2 deserialize uuid columns as UUID instances and
    timestamptz columns as datetime instances. Most call sites in this
    codebase were written against the Supabase REST client and expect
    plain strings (they pass values straight into Pydantic models or
    format them with `.replace(...)`/`fromisoformat`). Stringify here.
    """
    out = {}
    for k, v in row._mapping.items():
        if isinstance(v, UUID):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, date):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def get_database_url() -> str:
    """Build the async database URL from environment variables."""
    url = os.getenv("DATABASE_URL")
    if url:
        # Ensure it uses asyncpg driver - handle all possible URL schemes
        if "postgresql+asyncpg://" not in url:
            url = url.split("://", 1)
            url = f"postgresql+asyncpg://{url[1]}" if len(url) > 1 else url[0]
        return url

    # Fallback to individual env vars
    host = os.getenv("PSQL_DATABASE_URL", "localhost")
    name = os.getenv("PSQL_DATABASE_NAME", "ublix")
    user = os.getenv("PSQL_DATABASE_USER", "postgres")
    password = os.getenv("PSQL_DATABASE_PASSWORD", "")
    port = os.getenv("PSQL_DATABASE_PORT", "5432")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


def get_engine():
    """Get or create the global async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_database_url(),
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine


def _get_sync_database_url() -> str:
    """Build a sync (psycopg2) URL from the same source as the async one."""
    url = get_database_url()
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def get_sync_engine():
    """Get or create the global sync engine (psycopg2) for SyncDatabase.

    Using a real sync engine avoids the broken sync-over-async pattern that
    blew up with "asyncio.run() cannot be called from a running event loop"
    whenever SyncDatabase was used from inside a FastAPI request.
    """
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            _get_sync_database_url(),
            pool_size=10,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
    return _sync_engine


def get_session_factory():
    """Get or create the global async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def init_db():
    """Initialize the database engine. Call on app startup."""
    get_engine()
    logger.info("Database engine initialized")


async def close_db():
    """Close the database engine. Call on app shutdown."""
    global _engine, _async_session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
    logger.info("Database engine closed")


class QueryResult:
    """Mimics Supabase's response object with a .data attribute."""
    def __init__(self, data: Optional[List[Dict]] = None, count: Optional[int] = None):
        self.data = data or []
        self.count = count


class TableQuery:
    """
    Chainable query builder that mimics the Supabase client API.
    Usage: db.table('projects').select('*').eq('project_id', id).execute()
    """

    def __init__(self, table_name: str, session_factory):
        self._table = table_name
        self._session_factory = session_factory
        self._operation = None  # 'select', 'insert', 'update', 'delete'
        self._select_columns = "*"
        self._count_mode = None  # 'exact', 'planned', 'estimated'
        self._filters: List[tuple] = []  # (column, operator, value)
        self._or_filters: List[str] = []
        self._order_by: List[tuple] = []
        self._limit_val: Optional[int] = None
        self._offset_val: Optional[int] = None
        self._data: Optional[Any] = None
        self._upsert_on_conflict: Optional[str] = None

    def select(self, columns: str = "*", count: str = None) -> "TableQuery":
        self._operation = "select"
        self._select_columns = columns
        self._count_mode = count
        return self

    def insert(self, data: Any) -> "TableQuery":
        self._operation = "insert"
        self._data = data
        return self

    def update(self, data: Dict) -> "TableQuery":
        self._operation = "update"
        self._data = data
        return self

    def upsert(self, data: Any, on_conflict: str = None) -> "TableQuery":
        self._operation = "upsert"
        self._data = data
        self._upsert_on_conflict = on_conflict
        return self

    def delete(self) -> "TableQuery":
        self._operation = "delete"
        return self

    # Filter methods
    def eq(self, column: str, value: Any) -> "TableQuery":
        self._filters.append((column, "=", value))
        return self

    def neq(self, column: str, value: Any) -> "TableQuery":
        self._filters.append((column, "!=", value))
        return self

    def gt(self, column: str, value: Any) -> "TableQuery":
        self._filters.append((column, ">", value))
        return self

    def gte(self, column: str, value: Any) -> "TableQuery":
        self._filters.append((column, ">=", value))
        return self

    def lt(self, column: str, value: Any) -> "TableQuery":
        self._filters.append((column, "<", value))
        return self

    def lte(self, column: str, value: Any) -> "TableQuery":
        self._filters.append((column, "<=", value))
        return self

    def like(self, column: str, pattern: str) -> "TableQuery":
        self._filters.append((column, "LIKE", pattern))
        return self

    def ilike(self, column: str, pattern: str) -> "TableQuery":
        self._filters.append((column, "ILIKE", pattern))
        return self

    def is_(self, column: str, value: Any) -> "TableQuery":
        if value is None:
            self._filters.append((column, "IS", None))
        else:
            self._filters.append((column, "IS", value))
        return self

    def in_(self, column: str, values: list) -> "TableQuery":
        self._filters.append((column, "IN", values))
        return self

    def or_(self, filter_string: str) -> "TableQuery":
        """Handle Supabase-style OR filters like 'name.ilike.%term%,email.ilike.%term%'."""
        self._or_filters.append(filter_string)
        return self

    def filter(self, column: str, operator: str, value: Any) -> "TableQuery":
        """Generic filter - maps Supabase operators to SQL."""
        op_map = {
            "eq": "=", "neq": "!=", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=", "like": "LIKE", "ilike": "ILIKE",
            "is": "IS", "in": "IN",
        }
        sql_op = op_map.get(operator, operator)
        self._filters.append((column, sql_op, value))
        return self

    def match(self, filters: Dict) -> "TableQuery":
        """Add multiple equality filters at once."""
        for key, value in filters.items():
            self._filters.append((key, "=", value))
        return self

    def order(self, column: str, desc: bool = False) -> "TableQuery":
        self._order_by.append((column, desc))
        return self

    def limit(self, count: int) -> "TableQuery":
        self._limit_val = count
        return self

    def offset(self, count: int) -> "TableQuery":
        self._offset_val = count
        return self

    def single(self) -> "TableQuery":
        """Limit to single result (Supabase compatibility)."""
        self._limit_val = 1
        return self

    def range(self, start: int, end: int) -> "TableQuery":
        """Set offset and limit from range (Supabase compatibility)."""
        self._offset_val = start
        self._limit_val = end - start + 1
        return self

    def _build_where_clause(self, params: dict) -> str:
        """Build WHERE clause from filters."""
        conditions = []

        for i, (column, operator, value) in enumerate(self._filters):
            param_name = f"w_{i}"
            if operator == "IS" and value is None:
                conditions.append(f'"{column}" IS NULL')
            elif operator == "IS":
                conditions.append(f'"{column}" IS :w_{i}')
                params[param_name] = value
            elif operator == "IN":
                # Handle IN with tuple
                placeholders = ", ".join(f":in_{i}_{j}" for j in range(len(value)))
                conditions.append(f'"{column}" IN ({placeholders})')
                for j, v in enumerate(value):
                    params[f"in_{i}_{j}"] = v
            else:
                conditions.append(f'"{column}" {operator} :{param_name}')
                params[param_name] = value

        # Handle OR filters (Supabase-style: 'name.ilike.%term%,email.ilike.%term%')
        for or_idx, or_filter in enumerate(self._or_filters):
            or_parts = []
            for part_idx, part in enumerate(or_filter.split(",")):
                segments = part.strip().split(".", 2)
                if len(segments) == 3:
                    col, op, val = segments
                    op_map = {"ilike": "ILIKE", "like": "LIKE", "eq": "=", "neq": "!=",
                              "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
                    sql_op = op_map.get(op, op)
                    p_name = f"or_{or_idx}_{part_idx}"
                    or_parts.append(f'"{col}" {sql_op} :{p_name}')
                    params[p_name] = val
            if or_parts:
                conditions.append(f"({' OR '.join(or_parts)})")

        if not conditions:
            return ""

        return " WHERE " + " AND ".join(conditions)

    async def execute(self) -> QueryResult:
        """Execute the built query and return results."""
        async with self._session_factory() as session:
            async with session.begin():
                try:
                    if self._operation == "select":
                        return await self._execute_select(session)
                    elif self._operation == "insert":
                        return await self._execute_insert(session)
                    elif self._operation == "update":
                        return await self._execute_update(session)
                    elif self._operation == "delete":
                        return await self._execute_delete(session)
                    elif self._operation == "upsert":
                        return await self._execute_upsert(session)
                    else:
                        raise ValueError(f"Unknown operation: {self._operation}")
                except Exception as e:
                    logger.error(f"Query execution error on {self._table}: {e}")
                    raise

    async def _execute_select(self, session: AsyncSession) -> QueryResult:
        params = {}
        where = self._build_where_clause(params)

        cols = self._select_columns if self._select_columns != "*" else "*"
        sql = f'SELECT {cols} FROM "{self._table}"{where}'

        if self._order_by:
            order_parts = []
            for col, desc in self._order_by:
                order_parts.append(f'"{col}" {"DESC" if desc else "ASC"}')
            sql += " ORDER BY " + ", ".join(order_parts)

        if self._limit_val is not None:
            sql += f" LIMIT {self._limit_val}"

        if self._offset_val is not None:
            sql += f" OFFSET {self._offset_val}"

        result = await session.execute(text(sql), params)
        rows = [_row_to_dict(row) for row in result.fetchall()]

        # Handle count if requested
        count = None
        if self._count_mode == "exact":
            count_sql = f'SELECT COUNT(*) as cnt FROM "{self._table}"{where}'
            count_result = await session.execute(text(count_sql), params)
            count = count_result.scalar()

        return QueryResult(rows, count=count)

    async def _execute_insert(self, session: AsyncSession) -> QueryResult:
        records = self._data if isinstance(self._data, list) else [self._data]
        all_results = []

        for record in records:
            columns = list(record.keys())
            col_str = ", ".join(f'"{c}"' for c in columns)
            val_str = ", ".join(f":{c}" for c in columns)
            sql = f'INSERT INTO "{self._table}" ({col_str}) VALUES ({val_str}) RETURNING *'

            coerced = {k: _coerce_param(v) for k, v in record.items()}
            result = await session.execute(text(sql), coerced)
            row = result.fetchone()
            if row:
                all_results.append(_row_to_dict(row))

        return QueryResult(all_results)

    async def _execute_update(self, session: AsyncSession) -> QueryResult:
        params = {}
        set_parts = []
        for key, value in self._data.items():
            param_name = f"s_{key}"
            set_parts.append(f'"{key}" = :{param_name}')
            params[param_name] = _coerce_param(value)

        where = self._build_where_clause(params)
        set_str = ", ".join(set_parts)
        sql = f'UPDATE "{self._table}" SET {set_str}{where} RETURNING *'

        result = await session.execute(text(sql), params)
        rows = [_row_to_dict(row) for row in result.fetchall()]
        return QueryResult(rows)

    async def _execute_delete(self, session: AsyncSession) -> QueryResult:
        params = {}
        where = self._build_where_clause(params)
        sql = f'DELETE FROM "{self._table}"{where} RETURNING *'

        result = await session.execute(text(sql), params)
        rows = [_row_to_dict(row) for row in result.fetchall()]
        return QueryResult(rows)

    async def _execute_upsert(self, session: AsyncSession) -> QueryResult:
        records = self._data if isinstance(self._data, list) else [self._data]
        all_results = []

        for record in records:
            columns = list(record.keys())
            col_str = ", ".join(f'"{c}"' for c in columns)
            val_str = ", ".join(f":{c}" for c in columns)

            # Determine conflict columns
            conflict_cols = self._upsert_on_conflict if self._upsert_on_conflict else "id"

            update_parts = ", ".join(
                f'"{c}" = EXCLUDED."{c}"' for c in columns if c not in conflict_cols.split(",")
            )

            if update_parts:
                sql = (
                    f'INSERT INTO "{self._table}" ({col_str}) VALUES ({val_str}) '
                    f'ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_parts} RETURNING *'
                )
            else:
                sql = (
                    f'INSERT INTO "{self._table}" ({col_str}) VALUES ({val_str}) '
                    f'ON CONFLICT ({conflict_cols}) DO NOTHING RETURNING *'
                )

            coerced = {k: _coerce_param(v) for k, v in record.items()}
            result = await session.execute(text(sql), coerced)
            row = result.fetchone()
            if row:
                all_results.append(_row_to_dict(row))

        return QueryResult(all_results)


class RpcCaller:
    """Handles RPC (stored function) calls, mimicking supabase.rpc()."""

    def __init__(self, func_name: str, params: dict, session_factory):
        self._func_name = func_name
        self._params = params
        self._session_factory = session_factory

    async def execute(self) -> QueryResult:
        async with self._session_factory() as session:
            async with session.begin():
                # Build function call
                param_names = list(self._params.keys())
                param_str = ", ".join(f":{p}" for p in param_names)
                sql = f"SELECT * FROM {self._func_name}({param_str})"

                result = await session.execute(text(sql), self._params)

                try:
                    rows = [_row_to_dict(row) for row in result.fetchall()]
                    return QueryResult(rows)
                except Exception:
                    # For functions that return a scalar
                    return QueryResult([])


class SyncTableQuery:
    """
    Synchronous version of TableQuery for code that cannot use async.
    Uses the async engine but runs queries synchronously via run_sync.
    """

    def __init__(self, table_name: str, engine):
        self._table = table_name
        self._engine = engine
        self._operation = None
        self._select_columns = "*"
        self._count_mode = None
        self._filters: List[tuple] = []
        self._or_filters: List[str] = []
        self._order_by: List[tuple] = []
        self._limit_val: Optional[int] = None
        self._offset_val: Optional[int] = None
        self._data: Optional[Any] = None
        self._upsert_on_conflict: Optional[str] = None

    def select(self, columns: str = "*", count: str = None) -> "SyncTableQuery":
        self._operation = "select"
        self._select_columns = columns
        self._count_mode = count
        return self

    def insert(self, data: Any) -> "SyncTableQuery":
        self._operation = "insert"
        self._data = data
        return self

    def update(self, data: Dict) -> "SyncTableQuery":
        self._operation = "update"
        self._data = data
        return self

    def upsert(self, data: Any, on_conflict: str = None) -> "SyncTableQuery":
        self._operation = "upsert"
        self._data = data
        self._upsert_on_conflict = on_conflict
        return self

    def delete(self) -> "SyncTableQuery":
        self._operation = "delete"
        return self

    def eq(self, column: str, value: Any) -> "SyncTableQuery":
        self._filters.append((column, "=", value))
        return self

    def neq(self, column: str, value: Any) -> "SyncTableQuery":
        self._filters.append((column, "!=", value))
        return self

    def gt(self, column: str, value: Any) -> "SyncTableQuery":
        self._filters.append((column, ">", value))
        return self

    def gte(self, column: str, value: Any) -> "SyncTableQuery":
        self._filters.append((column, ">=", value))
        return self

    def lt(self, column: str, value: Any) -> "SyncTableQuery":
        self._filters.append((column, "<", value))
        return self

    def lte(self, column: str, value: Any) -> "SyncTableQuery":
        self._filters.append((column, "<=", value))
        return self

    def like(self, column: str, pattern: str) -> "SyncTableQuery":
        self._filters.append((column, "LIKE", pattern))
        return self

    def ilike(self, column: str, pattern: str) -> "SyncTableQuery":
        self._filters.append((column, "ILIKE", pattern))
        return self

    def is_(self, column: str, value: Any) -> "SyncTableQuery":
        if value is None:
            self._filters.append((column, "IS", None))
        else:
            self._filters.append((column, "IS", value))
        return self

    def in_(self, column: str, values: list) -> "SyncTableQuery":
        self._filters.append((column, "IN", values))
        return self

    def or_(self, filter_string: str) -> "SyncTableQuery":
        self._or_filters.append(filter_string)
        return self

    def filter(self, column: str, operator: str, value: Any) -> "SyncTableQuery":
        op_map = {
            "eq": "=", "neq": "!=", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=", "like": "LIKE", "ilike": "ILIKE",
            "is": "IS", "in": "IN",
        }
        sql_op = op_map.get(operator, operator)
        self._filters.append((column, sql_op, value))
        return self

    def match(self, filters: Dict) -> "SyncTableQuery":
        for key, value in filters.items():
            self._filters.append((key, "=", value))
        return self

    def order(self, column: str, desc: bool = False) -> "SyncTableQuery":
        self._order_by.append((column, desc))
        return self

    def limit(self, count: int) -> "SyncTableQuery":
        self._limit_val = count
        return self

    def offset(self, count: int) -> "SyncTableQuery":
        self._offset_val = count
        return self

    def single(self) -> "SyncTableQuery":
        self._limit_val = 1
        return self

    def range(self, start: int, end: int) -> "SyncTableQuery":
        self._offset_val = start
        self._limit_val = end - start + 1
        return self

    def _build_where_clause(self, params: dict) -> str:
        conditions = []

        for i, (column, operator, value) in enumerate(self._filters):
            param_name = f"w_{i}"
            if operator == "IS" and value is None:
                conditions.append(f'"{column}" IS NULL')
            elif operator == "IS":
                conditions.append(f'"{column}" IS :w_{i}')
                params[param_name] = value
            elif operator == "IN":
                placeholders = ", ".join(f":in_{i}_{j}" for j in range(len(value)))
                conditions.append(f'"{column}" IN ({placeholders})')
                for j, v in enumerate(value):
                    params[f"in_{i}_{j}"] = v
            else:
                conditions.append(f'"{column}" {operator} :{param_name}')
                params[param_name] = value

        for or_idx, or_filter in enumerate(self._or_filters):
            or_parts = []
            for part_idx, part in enumerate(or_filter.split(",")):
                segments = part.strip().split(".", 2)
                if len(segments) == 3:
                    col, op, val = segments
                    op_map = {"ilike": "ILIKE", "like": "LIKE", "eq": "=", "neq": "!=",
                              "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
                    sql_op = op_map.get(op, op)
                    p_name = f"or_{or_idx}_{part_idx}"
                    or_parts.append(f'"{col}" {sql_op} :{p_name}')
                    params[p_name] = val
            if or_parts:
                conditions.append(f"({' OR '.join(or_parts)})")

        if not conditions:
            return ""
        return " WHERE " + " AND ".join(conditions)

    def execute(self) -> QueryResult:
        """Execute the built query against the sync engine (psycopg2)."""
        try:
            with self._engine.begin() as conn:
                if self._operation == "select":
                    return self._execute_select(conn)
                elif self._operation == "insert":
                    return self._execute_insert(conn)
                elif self._operation == "update":
                    return self._execute_update(conn)
                elif self._operation == "delete":
                    return self._execute_delete(conn)
                elif self._operation == "upsert":
                    return self._execute_upsert(conn)
                else:
                    raise ValueError(f"Unknown operation: {self._operation}")
        except Exception as e:
            logger.error(f"Sync query execution error on {self._table}: {e}")
            raise

    def _execute_select(self, conn) -> QueryResult:
        params = {}
        where = self._build_where_clause(params)
        cols = self._select_columns if self._select_columns != "*" else "*"
        sql = f'SELECT {cols} FROM "{self._table}"{where}'

        if self._order_by:
            order_parts = [f'"{col}" {"DESC" if desc else "ASC"}' for col, desc in self._order_by]
            sql += " ORDER BY " + ", ".join(order_parts)
        if self._limit_val is not None:
            sql += f" LIMIT {self._limit_val}"
        if self._offset_val is not None:
            sql += f" OFFSET {self._offset_val}"

        result = conn.execute(text(sql), params)
        rows = [_row_to_dict(row) for row in result.fetchall()]

        count = None
        if self._count_mode == "exact":
            count_sql = f'SELECT COUNT(*) as cnt FROM "{self._table}"{where}'
            count_result = conn.execute(text(count_sql), params)
            count = count_result.scalar()

        return QueryResult(rows, count=count)

    def _execute_insert(self, conn) -> QueryResult:
        records = self._data if isinstance(self._data, list) else [self._data]
        all_results = []
        for record in records:
            columns = list(record.keys())
            col_str = ", ".join(f'"{c}"' for c in columns)
            val_str = ", ".join(f":{c}" for c in columns)
            sql = f'INSERT INTO "{self._table}" ({col_str}) VALUES ({val_str}) RETURNING *'
            coerced = {k: _coerce_param(v) for k, v in record.items()}
            result = conn.execute(text(sql), coerced)
            row = result.fetchone()
            if row:
                all_results.append(_row_to_dict(row))
        return QueryResult(all_results)

    def _execute_update(self, conn) -> QueryResult:
        params = {}
        set_parts = []
        for key, value in self._data.items():
            param_name = f"s_{key}"
            set_parts.append(f'"{key}" = :{param_name}')
            params[param_name] = _coerce_param(value)
        where = self._build_where_clause(params)
        set_str = ", ".join(set_parts)
        sql = f'UPDATE "{self._table}" SET {set_str}{where} RETURNING *'
        result = conn.execute(text(sql), params)
        rows = [_row_to_dict(row) for row in result.fetchall()]
        return QueryResult(rows)

    def _execute_delete(self, conn) -> QueryResult:
        params = {}
        where = self._build_where_clause(params)
        sql = f'DELETE FROM "{self._table}"{where} RETURNING *'
        result = conn.execute(text(sql), params)
        rows = [_row_to_dict(row) for row in result.fetchall()]
        return QueryResult(rows)

    def _execute_upsert(self, conn) -> QueryResult:
        records = self._data if isinstance(self._data, list) else [self._data]
        all_results = []
        for record in records:
            columns = list(record.keys())
            col_str = ", ".join(f'"{c}"' for c in columns)
            val_str = ", ".join(f":{c}" for c in columns)
            conflict_cols = self._upsert_on_conflict if self._upsert_on_conflict else "id"
            update_parts = ", ".join(
                f'"{c}" = EXCLUDED."{c}"' for c in columns if c not in conflict_cols.split(",")
            )
            if update_parts:
                sql = (
                    f'INSERT INTO "{self._table}" ({col_str}) VALUES ({val_str}) '
                    f'ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_parts} RETURNING *'
                )
            else:
                sql = (
                    f'INSERT INTO "{self._table}" ({col_str}) VALUES ({val_str}) '
                    f'ON CONFLICT ({conflict_cols}) DO NOTHING RETURNING *'
                )
            coerced = {k: _coerce_param(v) for k, v in record.items()}
            result = conn.execute(text(sql), coerced)
            row = result.fetchone()
            if row:
                all_results.append(_row_to_dict(row))
        return QueryResult(all_results)


class SyncRpcCaller:
    """Synchronous RPC caller for stored functions."""

    def __init__(self, func_name: str, params: dict, engine):
        self._func_name = func_name
        self._params = params
        self._engine = engine

    def execute(self) -> QueryResult:
        with self._engine.begin() as conn:
            param_names = list(self._params.keys())
            param_str = ", ".join(f":{p}" for p in param_names)
            sql = f"SELECT * FROM {self._func_name}({param_str})"
            coerced = {k: _coerce_param(v) for k, v in self._params.items()}
            result = conn.execute(text(sql), coerced)
            try:
                rows = [_row_to_dict(row) for row in result.fetchall()]
                return QueryResult(rows)
            except Exception:
                return QueryResult([])


class Database:
    """
    Async PostgreSQL database client.
    Drop-in replacement for SupabaseDatabase with compatible API.

    Supports two usage patterns:
    1. Direct methods: db.insert('table', data), db.select('table', filters)
    2. Chained queries: db.table('name').select('*').eq('col', val).execute()
    """

    def __init__(self):
        self._session_factory = get_session_factory()

    def table(self, name: str) -> TableQuery:
        """Start a chained query on a table (Supabase-compatible)."""
        return TableQuery(name, self._session_factory)

    # Alias for Supabase compatibility: db.from_('table')
    def from_(self, name: str) -> TableQuery:
        return self.table(name)

    def rpc(self, func_name: str, params: dict = None) -> RpcCaller:
        """Call a stored PostgreSQL function (Supabase RPC compatible)."""
        return RpcCaller(func_name, params or {}, self._session_factory)

    def _convert_data_for_json(self, data: Any) -> Any:
        """Convert non-JSON-serializable objects to serializable format."""
        if isinstance(data, (bytes, bytearray)):
            return base64.b64encode(data).decode('utf-8')

        if isinstance(data, datetime):
            return data.isoformat()

        if isinstance(data, (dict, OrderedDict, defaultdict)):
            result = {}
            for key, value in (data.items() if hasattr(data, 'items') else data):
                if key == 'additional_fields' and isinstance(value, dict):
                    result[key] = value
                elif isinstance(value, (dict, OrderedDict, defaultdict)):
                    result[key] = self._convert_data_for_json(value)
                elif isinstance(value, (list, tuple)):
                    result[key] = [self._convert_data_for_json(item) for item in value]
                elif isinstance(value, datetime):
                    result[key] = value.isoformat()
                else:
                    result[key] = value
            return result

        if isinstance(data, (list, tuple)):
            return [self._convert_data_for_json(item) for item in data]

        if isinstance(data, (set, frozenset)):
            return [self._convert_data_for_json(item) for item in sorted(data)]

        if hasattr(data, '__dict__'):
            return self._convert_data_for_json(data.__dict__)

        return data

    async def insert(self, table: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insert data into a table and return the complete inserted record."""
        try:
            converted_data = self._convert_data_for_json(data)
            result = await self.table(table).insert(converted_data).execute()

            if not result.data:
                raise Exception(f"No data returned from insert operation on table {table}")

            if len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            raise Exception(f"Error inserting data: {e}")

    async def select(self, table: str, filters: Dict = None, order_by: Dict = None,
                     limit: int = None, offset: int = None) -> Optional[List[Dict]]:
        """Query data from a table with filters, ordering, limit and offset."""
        try:
            query = self.table(table).select("*")

            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)

            if order_by:
                for key, direction in order_by.items():
                    query = query.order(key, desc=(direction.lower() == 'desc'))

            if limit:
                query = query.limit(limit)

            if offset:
                query = query.offset(offset)

            result = await query.execute()
            return result.data
        except Exception as e:
            logger.error(f"Error querying data: {e}")
            return None

    async def delete(self, table: str, filters: Dict) -> None:
        """Delete records from a table based on filters."""
        try:
            query = self.table(table).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            await query.execute()
        except Exception as e:
            logger.error(f"Error deleting data: {e}")

    async def update(self, table: str, data: Dict, filters: Dict) -> Optional[Dict]:
        """Update records in a table based on filters and return the updated record."""
        try:
            result = await self.table(table).update(data).match(filters).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error updating data: {e}")
            return None

    async def insert_or_update(self, table: str, data: Dict, keys_to_update: Dict = None) -> None:
        """Upsert operation - insert if not exists, update if exists."""
        try:
            await self.table(table).upsert(data).execute()
        except Exception as e:
            logger.error(f"Error in upsert operation: {e}")

    async def find_one(self, table: str, filters: Dict) -> Optional[Dict]:
        """Find a single record in a table based on filters."""
        try:
            query = self.table(table).select("*")

            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)

            result = await query.execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error finding one record: {e}")
            return None

    async def batch_insert(self, table: str, records: list) -> list:
        """Insert multiple records in a single database operation."""
        try:
            if not records:
                return []

            converted_records = [self._convert_data_for_json(record) for record in records]
            result = await self.table(table).insert(converted_records).execute()
            return result.data if result.data else []
        except Exception as e:
            logging.error(f"Error in batch insert: {e}")
            raise

    async def delete_one(self, table: str, filters: Dict) -> None:
        """Delete a single record from a table based on filters."""
        try:
            query = self.table(table).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            await query.execute()
        except Exception as e:
            logging.error(f"Error deleting record: {e}")
            raise

    async def find(self, table: str, filters: Dict) -> Optional[List[Dict]]:
        """Find multiple records in a table based on filters."""
        try:
            query = self.table(table).select("*")
            for key, value in filters.items():
                query = query.eq(key, value)
            result = await query.execute()
            return result.data
        except Exception as e:
            logging.error(f"Error finding records: {e}")
            raise


class SyncDatabase:
    """
    Synchronous PostgreSQL database client.
    Drop-in replacement for SupabaseClient / supabase.Client for sync code.
    Uses the same global engine but runs queries synchronously.
    """

    def __init__(self):
        self._engine = get_sync_engine()

    def table(self, name: str) -> SyncTableQuery:
        """Start a chained sync query on a table."""
        return SyncTableQuery(name, self._engine)

    def from_(self, name: str) -> SyncTableQuery:
        return self.table(name)

    def rpc(self, func_name: str, params: dict = None) -> SyncRpcCaller:
        """Call a stored PostgreSQL function synchronously."""
        return SyncRpcCaller(func_name, params or {}, self._engine)
