"""Data models for Schema Sentinel."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OperationType(Enum):
    """Types of schema-changing operations."""
    CREATE_TABLE = "CREATE_TABLE"
    ALTER_TABLE = "ALTER_TABLE"
    DROP_TABLE = "DROP_TABLE"
    CREATE_INDEX = "CREATE_INDEX"
    DROP_INDEX = "DROP_INDEX"
    CREATE_CONSTRAINT = "CREATE_CONSTRAINT"
    DROP_CONSTRAINT = "DROP_CONSTRAINT"
    RENAME_TABLE = "RENAME_TABLE"
    RENAME_COLUMN = "RENAME_COLUMN"
    OTHER = "OTHER"  # Non-DDL or unsupported


@dataclass
class MigrationOperation:
    """A single operation extracted from a migration file."""
    operation_type: OperationType
    table_name: Optional[str]
    raw_statement: str
    line_number: int
    
    def __repr__(self):
        return f"<{self.operation_type.value} on {self.table_name or 'unknown'}>"