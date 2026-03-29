"""
PostgreSQL database client.
Now uses direct PostgreSQL via SQLAlchemy instead of Supabase.
Provides both sync and async Database classes.
"""

import logging
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import OrderedDict, defaultdict
from app.database import Database, SyncDatabase

logger = logging.getLogger(__name__)


class SupabaseDatabase:
    """
    Synchronous database client - backward-compatible replacement.
    Uses SyncDatabase (direct PostgreSQL) for chainable queries
    and provides the same sync method signatures as the old Supabase version.
    """

    def __init__(self):
        self.client = SyncDatabase()

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

    def insert(self, table: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insert data into a table and return the complete inserted record."""
        try:
            converted_data = self._convert_data_for_json(data)
            result = self.client.table(table).insert(converted_data).execute()

            if not result.data:
                raise Exception(f"No data returned from insert operation on table {table}")

            if len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            raise Exception(f"Error inserting data: {e}")

    def select(self, table: str, filters: Dict = None, order_by: Dict = None,
               limit: int = None, offset: int = None) -> Optional[List[Dict]]:
        """Query data from a table with filters, ordering, limit and offset."""
        try:
            query = self.client.table(table).select("*")

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

            result = query.execute()
            return result.data
        except Exception as e:
            print(f"Error querying data: {e}")
            return None

    def delete(self, table: str, filters: Dict) -> None:
        """Delete records from a table based on filters."""
        try:
            query = self.client.table(table).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            query.execute()
        except Exception as e:
            print(f"Error deleting data: {e}")

    def update(self, table: str, data: Dict, filters: Dict) -> Optional[Dict]:
        """Update records in a table based on filters and return the updated record."""
        try:
            result = self.client.table(table).update(data).match(filters).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Error updating data: {e}")
            return None

    def insert_or_update(self, table: str, data: Dict, keys_to_update: Dict = None) -> None:
        """Upsert operation - insert if not exists, update if exists."""
        try:
            self.client.table(table).upsert(data).execute()
        except Exception as e:
            print(f"Error in upsert operation: {e}")

    def find_one(self, table: str, filters: Dict) -> Optional[Dict]:
        """Find a single record in a table based on filters."""
        try:
            query = self.client.table(table).select("*")

            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)

            result = query.execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error finding one record: {e}")
            return None

    def batch_insert(self, table: str, records: list) -> list:
        """Insert multiple records in a single database operation."""
        try:
            if not records:
                return []

            converted_records = [self._convert_data_for_json(record) for record in records]
            result = self.client.table(table).insert(converted_records).execute()
            return result.data if result.data else []
        except Exception as e:
            logging.error(f"Error in batch insert: {e}")
            raise

    def delete_one(self, table: str, filters: Dict) -> None:
        """Delete a single record from a table based on filters."""
        try:
            query = self.client.table(table).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            query.execute()
        except Exception as e:
            logging.error(f"Error deleting record: {e}")
            raise

    def find(self, table: str, filters: Dict) -> Optional[List[Dict]]:
        """Find multiple records in a table based on filters."""
        try:
            query = self.client.table(table).select("*")
            for key, value in filters.items():
                query = query.eq(key, value)
            return query.execute().data
        except Exception as e:
            logging.error(f"Error finding records: {e}")
            raise
