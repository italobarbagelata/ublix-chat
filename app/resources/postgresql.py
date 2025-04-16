from supabase import create_client
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import os
import base64
from datetime import datetime
from collections import OrderedDict, defaultdict
import logging

load_dotenv()

class SupabaseDatabase:
    def __init__(self):
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        self.supabase = create_client(supabase_url, supabase_key)

    def _convert_data_for_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert non-JSON-serializable objects to serializable format."""
        if isinstance(data, (bytes, bytearray)):
            return base64.b64encode(data).decode('utf-8')
        
        if isinstance(data, (datetime)):
            return data.isoformat()
            
        if isinstance(data, (dict, OrderedDict, defaultdict)):
            return {
                key: self._convert_data_for_json(value)
                for key, value in (data.items() if hasattr(data, 'items') else data)
            }
            
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
            # Convert any non-JSON-serializable objects to serializable format
            converted_data = self._convert_data_for_json(data)
            
            # Log the data being sent
            #print(f"Inserting into table {table} with data: {converted_data}")
            
            result = self.supabase.from_(table).insert(converted_data).execute()
            
            if not result.data:
                raise Exception(f"No data returned from insert operation on table {table}")
                
            if len(result.data) > 0:
                return result.data[0]  # Return the complete inserted record
            return None
        except Exception as e:
            raise Exception(f"Error inserting data: {e}")

    def select(self, table: str, filters: Dict = None, order_by: Dict = None, 
               limit: int = None, offset: int = None) -> Optional[List[Dict]]:
        """Query data from a table with filters, ordering, limit and offset."""
        try:
            query = self.supabase.from_(table).select("*")
            
            if filters:
                for key, value in filters.items():
                    query = query.filter(key, "eq", value)
            
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
            query = self.supabase.from_(table).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            query.execute()
        except Exception as e:
            print(f"Error deleting data: {e}")

    def update(self, table: str, data: Dict, filters: Dict) -> Optional[Dict]:
        """Update records in a table based on filters and return the updated record."""
        try:
            result = self.supabase.from_(table).update(data).match(filters).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Error updating data: {e}")
            return None

    def insert_or_update(self, table: str, data: Dict, keys_to_update: Dict) -> None:
        """Upsert operation - insert if not exists, update if exists."""
        try:
            self.supabase.from_(table).upsert(data).execute()
        except Exception as e:
            print(f"Error in upsert operation: {e}")
            
    def find_one(self, table: str, filters: Dict) -> Optional[Dict]:
        """Find a single record in a table based on filters."""
        try:
            query = self.supabase.from_(table).select("*")
            
            if filters:
                for key, value in filters.items():
                    query = query.filter(key, "eq", value)
            
            result = query.execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error finding one record: {e}")
            return None

    def batch_insert(self, table: str, records: list) -> list:
        """Insert multiple records in a single database operation.
        
        Args:
            table: Name of the table to insert into
            records: List of dictionaries containing the records to insert
            
        Returns:
            list: List of inserted records with their IDs
        """
        try:
            if not records:
                return []
                
            # Convertir los registros a formato JSON serializable
            converted_records = [self._convert_data_for_json(record) for record in records]
            
            # Usar la API de Supabase para inserción en lote
            result = self.supabase.from_(table).insert(converted_records).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logging.error(f"Error in batch insert: {e}")
            raise

    def delete_one(self, table: str, filters: Dict) -> None:
        """Delete a single record from a table based on filters."""
        try:
            query = self.supabase.from_(table).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            query.execute() 
        except Exception as e:
            logging.error(f"Error deleting record: {e}")
            raise
    
    def find(self, table: str, filters: Dict) -> Optional[List[Dict]]:
        """Find multiple records in a table based on filters."""
        try:
            query = self.supabase.from_(table).select("*")
            for key, value in filters.items():
                query = query.filter(key, "eq", value)
            return query.execute().data
        except Exception as e:
            logging.error(f"Error finding records: {e}")
            raise
