"""
Database module - PostgreSQL async connection using SQLAlchemy Core.
Replaces Supabase client with direct PostgreSQL connection.
Provides a compatible API to minimize controller changes.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import OrderedDict, defaultdict
import base64

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine = None
_async_session_factory = None


def get_database_url() -> str:
    """Build the async database URL from environment variables."""
    url = os.getenv("DATABASE_URL")
    if url:
        # Ensure it uses asyncpg driver
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
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
        rows = [dict(row._mapping) for row in result.fetchall()]

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

            result = await session.execute(text(sql), record)
            row = result.fetchone()
            if row:
                all_results.append(dict(row._mapping))

        return QueryResult(all_results)

    async def _execute_update(self, session: AsyncSession) -> QueryResult:
        params = {}
        set_parts = []
        for key, value in self._data.items():
            param_name = f"s_{key}"
            set_parts.append(f'"{key}" = :{param_name}')
            params[param_name] = value

        where = self._build_where_clause(params)
        set_str = ", ".join(set_parts)
        sql = f'UPDATE "{self._table}" SET {set_str}{where} RETURNING *'

        result = await session.execute(text(sql), params)
        rows = [dict(row._mapping) for row in result.fetchall()]
        return QueryResult(rows)

    async def _execute_delete(self, session: AsyncSession) -> QueryResult:
        params = {}
        where = self._build_where_clause(params)
        sql = f'DELETE FROM "{self._table}"{where} RETURNING *'

        result = await session.execute(text(sql), params)
        rows = [dict(row._mapping) for row in result.fetchall()]
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

            result = await session.execute(text(sql), record)
            row = result.fetchone()
            if row:
                all_results.append(dict(row._mapping))

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
                    rows = [dict(row._mapping) for row in result.fetchall()]
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
        """Execute the built query synchronously."""
        import asyncio

        async def _run():
            async with self._engine.connect() as conn:
                try:
                    if self._operation == "select":
                        return await self._execute_select(conn)
                    elif self._operation == "insert":
                        return await self._execute_insert(conn)
                    elif self._operation == "update":
                        return await self._execute_update(conn)
                    elif self._operation == "delete":
                        return await self._execute_delete(conn)
                    elif self._operation == "upsert":
                        return await self._execute_upsert(conn)
                    else:
                        raise ValueError(f"Unknown operation: {self._operation}")
                except Exception as e:
                    logger.error(f"Sync query execution error on {self._table}: {e}")
                    raise

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context; create a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _run())
                    return future.result()
            else:
                return loop.run_until_complete(_run())
        except RuntimeError:
            return asyncio.run(_run())

    async def _execute_select(self, conn) -> QueryResult:
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

        result = await conn.execute(text(sql), params)
        rows = [dict(row._mapping) for row in result.fetchall()]

        count = None
        if self._count_mode == "exact":
            count_sql = f'SELECT COUNT(*) as cnt FROM "{self._table}"{where}'
            count_result = await conn.execute(text(count_sql), params)
            count = count_result.scalar()

        return QueryResult(rows, count=count)

    async def _execute_insert(self, conn) -> QueryResult:
        records = self._data if isinstance(self._data, list) else [self._data]
        all_results = []
        for record in records:
            columns = list(record.keys())
            col_str = ", ".join(f'"{c}"' for c in columns)
            val_str = ", ".join(f":{c}" for c in columns)
            sql = f'INSERT INTO "{self._table}" ({col_str}) VALUES ({val_str}) RETURNING *'
            result = await conn.execute(text(sql), record)
            row = result.fetchone()
            if row:
                all_results.append(dict(row._mapping))
        await conn.commit()
        return QueryResult(all_results)

    async def _execute_update(self, conn) -> QueryResult:
        params = {}
        set_parts = []
        for key, value in self._data.items():
            param_name = f"s_{key}"
            set_parts.append(f'"{key}" = :{param_name}')
            params[param_name] = value
        where = self._build_where_clause(params)
        set_str = ", ".join(set_parts)
        sql = f'UPDATE "{self._table}" SET {set_str}{where} RETURNING *'
        result = await conn.execute(text(sql), params)
        rows = [dict(row._mapping) for row in result.fetchall()]
        await conn.commit()
        return QueryResult(rows)

    async def _execute_delete(self, conn) -> QueryResult:
        params = {}
        where = self._build_where_clause(params)
        sql = f'DELETE FROM "{self._table}"{where} RETURNING *'
        result = await conn.execute(text(sql), params)
        rows = [dict(row._mapping) for row in result.fetchall()]
        await conn.commit()
        return QueryResult(rows)

    async def _execute_upsert(self, conn) -> QueryResult:
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
            result = await conn.execute(text(sql), record)
            row = result.fetchone()
            if row:
                all_results.append(dict(row._mapping))
        await conn.commit()
        return QueryResult(all_results)


class SyncRpcCaller:
    """Synchronous RPC caller for stored functions."""

    def __init__(self, func_name: str, params: dict, engine):
        self._func_name = func_name
        self._params = params
        self._engine = engine

    def execute(self) -> QueryResult:
        import asyncio

        async def _run():
            async with self._engine.connect() as conn:
                param_names = list(self._params.keys())
                param_str = ", ".join(f":{p}" for p in param_names)
                sql = f"SELECT * FROM {self._func_name}({param_str})"
                result = await conn.execute(text(sql), self._params)
                try:
                    rows = [dict(row._mapping) for row in result.fetchall()]
                    return QueryResult(rows)
                except Exception:
                    return QueryResult([])

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _run())
                    return future.result()
            else:
                return loop.run_until_complete(_run())
        except RuntimeError:
            return asyncio.run(_run())


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
        self._engine = get_engine()

    def table(self, name: str) -> SyncTableQuery:
        """Start a chained sync query on a table."""
        return SyncTableQuery(name, self._engine)

    def from_(self, name: str) -> SyncTableQuery:
        return self.table(name)

    def rpc(self, func_name: str, params: dict = None) -> SyncRpcCaller:
        """Call a stored PostgreSQL function synchronously."""
        return SyncRpcCaller(func_name, params or {}, self._engine)
