"""Production database profiler — fetches table statistics safely (read-only)."""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class TableStats:
    """Statistics for a single table."""
    table_name: str
    row_count: int
    table_size_mb: float  # Total size in MB (including indexes)
    table_size_bytes: int
    index_size_mb: float
    total_size_mb: float
    has_primary_key: bool
    column_count: int
    index_count: int
    foreign_keys: List[str]  # List of referenced tables


@dataclass
class IndexInfo:
    """Information about a single index."""
    index_name: str
    table_name: str
    columns: List[str]
    is_unique: bool
    is_primary: bool
    size_mb: float


class DatabaseProfiler:
    """Read-only database profiler for PostgreSQL."""
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize the profiler with a PostgreSQL connection string.
        
        If no connection_string is provided, uses DATABASE_URL from .env.
        """
        self.conn_string = connection_string or os.getenv("DATABASE_URL")
        if not self.conn_string:
            raise ValueError(
                "No database connection string provided. "
                "Set DATABASE_URL in .env or pass connection_string."
            )
        
        # Verify we're in read-only mode (we'll enforce this at connection)
        self._connection = None
    
    def _get_connection(self):
        """Get a connection, ensuring it's read-only."""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(self.conn_string)
            # Enforce read-only mode at the session level
            with self._connection.cursor() as cur:
                cur.execute("SET session characteristics AS TRANSACTION READ ONLY;")
        return self._connection
    
    def close(self):
        """Close the database connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()
        self._connection = None
    
    def get_table_stats(self, table_name: str) -> Optional[TableStats]:
        """
        Fetch comprehensive statistics for a specific table.
        
        Returns:
            TableStats object or None if table doesn't exist.
        """
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        try:
            # 1. Get row count using pg_class (fast, approximate)
            cursor.execute("""
                SELECT 
                    c.reltuples::bigint AS row_count,
                    pg_total_relation_size(c.oid) AS total_size_bytes,
                    pg_table_size(c.oid) AS table_size_bytes,
                    pg_indexes_size(c.oid) AS index_size_bytes
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = %s
                    AND c.relkind = 'r'
                    AND n.nspname NOT IN ('information_schema', 'pg_catalog');
            """, (table_name,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            row_count = row['row_count'] or 0
            total_bytes = row['total_size_bytes']
            table_bytes = row['table_size_bytes']
            index_bytes = row['index_size_bytes']
            
            # 2. Check for primary key
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.table_constraints 
                    WHERE table_name = %s 
                        AND constraint_type = 'PRIMARY KEY'
                ) AS has_pk;
            """, (table_name,))
            has_pk = cursor.fetchone()['has_pk']
            
            # 3. Get column count
            cursor.execute("""
                SELECT COUNT(*) AS count
                FROM information_schema.columns
                WHERE table_name = %s;
            """, (table_name,))
            column_count = cursor.fetchone()['count']
            
            # 4. Get index count
            cursor.execute("""
                SELECT COUNT(*) AS count
                FROM pg_indexes
                WHERE tablename = %s;
            """, (table_name,))
            index_count = cursor.fetchone()['count']
            
            # 5. Get foreign key references
            cursor.execute("""
                SELECT 
                    conname AS constraint_name,
                    confrelid::regclass::text AS referenced_table
                FROM pg_constraint
                WHERE conrelid = %s::regclass
                    AND contype = 'f';
            """, (table_name,))
            foreign_keys = [row['referenced_table'] for row in cursor.fetchall()]
            
            return TableStats(
                table_name=table_name,
                row_count=row_count,
                table_size_mb=table_bytes / (1024 * 1024),
                table_size_bytes=table_bytes,
                index_size_mb=index_bytes / (1024 * 1024),
                total_size_mb=total_bytes / (1024 * 1024),
                has_primary_key=has_pk,
                column_count=column_count,
                index_count=index_count,
                foreign_keys=foreign_keys,
            )
            
        except Exception as e:
            raise RuntimeError(f"Error fetching stats for table '{table_name}': {e}")
        finally:
            cursor.close()
    
    def get_table_indexes(self, table_name: str) -> List[IndexInfo]:
        """Get all indexes for a specific table."""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        try:
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    indexdef,
                    pg_relation_size(indexname::regclass) AS index_size_bytes
                FROM pg_indexes
                WHERE tablename = %s;
            """, (table_name,))
            
            indexes = []
            for row in cursor.fetchall():
                # Parse index definition to get columns
                indexdef = row['indexdef']
                # Simple parsing: extract columns from indexdef
                # Example: "CREATE INDEX idx_name ON table (col1, col2)"
                import re
                match = re.search(r'\((.*?)\)', indexdef)
                columns = [c.strip() for c in match.group(1).split(',')] if match else []
                
                is_unique = 'UNIQUE' in indexdef.upper()
                is_primary = 'PRIMARY KEY' in indexdef.upper()
                
                indexes.append(IndexInfo(
                    index_name=row['indexname'],
                    table_name=row['tablename'],
                    columns=columns,
                    is_unique=is_unique,
                    is_primary=is_primary,
                    size_mb=row['index_size_bytes'] / (1024 * 1024),
                ))
            
            return indexes
            
        except Exception as e:
            raise RuntimeError(f"Error fetching indexes for table '{table_name}': {e}")
        finally:
            cursor.close()
    
    def get_all_table_names(self) -> List[str]:
        """Get all user-defined table names in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
                ORDER BY tablename;
            """)
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
    
    def get_table_summary(self, table_name: str) -> Dict:
        """
        Get a human-readable summary of a table's stats.
        """
        stats = self.get_table_stats(table_name)
        if not stats:
            return {"error": f"Table '{table_name}' not found"}
        
        return {
            "table_name": stats.table_name,
            "row_count": f"{stats.row_count:,}",
            "total_size_mb": round(stats.total_size_mb, 2),
            "table_size_mb": round(stats.table_size_mb, 2),
            "index_size_mb": round(stats.index_size_mb, 2),
            "column_count": stats.column_count,
            "index_count": stats.index_count,
            "has_primary_key": stats.has_primary_key,
            "foreign_keys": stats.foreign_keys,
        }