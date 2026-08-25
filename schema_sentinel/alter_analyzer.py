"""Detailed ALTER TABLE analysis — detects specific dangerous patterns."""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .models import MigrationOperation
from .profiler import TableStats


@dataclass
class AlterOperationDetail:
    """Detailed breakdown of an ALTER TABLE operation."""
    operation_type: str  # 'ADD_COLUMN', 'DROP_COLUMN', 'ALTER_COLUMN', 'ADD_CONSTRAINT', 'DROP_CONSTRAINT', 'RENAME'
    column_name: Optional[str] = None
    new_name: Optional[str] = None  # For RENAME operations
    data_type: Optional[str] = None  # For ALTER COLUMN TYPE
    is_nullable: Optional[bool] = None  # For ADD COLUMN with NOT NULL
    has_default: bool = False
    constraint_type: Optional[str] = None  # 'CHECK', 'FOREIGN KEY', 'UNIQUE', etc.
    is_risky: bool = False
    risk_reasons: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class AlterAnalyzer:
    """Detailed analyzer for ALTER TABLE operations."""
    
    def __init__(self):
        pass
    
    def analyze(self, operation: MigrationOperation, stats: Optional[TableStats]) -> AlterOperationDetail:
        """
        Analyze an ALTER TABLE operation in detail.
        
        Returns:
            AlterOperationDetail with specific risks and recommendations.
        """
        stmt = operation.raw_statement.lower()
        
        # Determine the specific ALTER operation type
        if "add column" in stmt:
            return self._analyze_add_column(stmt, stats)
        elif "drop column" in stmt:
            return self._analyze_drop_column(stmt, stats)
        elif "alter column" in stmt:
            return self._analyze_alter_column(stmt, stats)
        elif "rename column" in stmt:
            return self._analyze_rename_column(stmt, stats)
        elif "rename to" in stmt:
            return self._analyze_rename_table(stmt, stats)
        elif "add constraint" in stmt:
            return self._analyze_add_constraint(stmt, stats)
        elif "drop constraint" in stmt:
            return self._analyze_drop_constraint(stmt, stats)
        else:
            # Generic ALTER TABLE
            detail = AlterOperationDetail(operation_type="GENERIC")
            detail.is_risky = True
            detail.risk_reasons.append("Generic ALTER TABLE operation — specific risk depends on context")
            detail.recommendations.append("Review the exact ALTER operation carefully")
            return detail
    
    def _analyze_add_column(self, stmt: str, stats: Optional[TableStats]) -> AlterOperationDetail:
        """Analyze ADD COLUMN operation."""
        detail = AlterOperationDetail(
            operation_type="ADD_COLUMN",
            is_risky=False
        )
        
        # Extract column name
        match = re.search(r'add column\s+([a-zA-Z_][a-zA-Z0-9_$]*)', stmt)
        if match:
            detail.column_name = match.group(1)
        
        # Check for NOT NULL
        if "not null" in stmt:
            detail.is_nullable = False
            detail.is_risky = True
            detail.risk_reasons.append("❌ Adding NOT NULL column without a default value")
            
            # Check if default exists
            if "default" in stmt:
                detail.has_default = True
                detail.is_risky = False  # Not risky if default exists
                detail.risk_reasons = []  # Clear the risk
                detail.risk_reasons.append("✅ Adding NOT NULL column with default — safe (backfill will happen)")
                detail.recommendations.append("For large tables, consider adding with default, then removing default")
            else:
                detail.risk_reasons.append("   This will fail if table has existing rows")
                detail.recommendations.append("Either: 1) Add column as NULL, backfill, then set NOT NULL")
                detail.recommendations.append("Or: 2) Add with a default value")
                if stats and stats.row_count > 0:
                    detail.risk_reasons.append(f"   ⚠️  Table has {stats.row_count:,} existing rows")
        else:
            detail.is_nullable = True
            detail.risk_reasons.append("✅ Adding nullable column — no risk")
        
        # Check for large table
        if stats and stats.row_count > 100000:
            detail.is_risky = True
            detail.risk_reasons.append(f"⚠️  Large table ({stats.row_count:,} rows) — ALTER may lock the table")
            detail.recommendations.append("Use pg_repack or gh-ost for online schema changes")
        
        return detail
    
    def _analyze_drop_column(self, stmt: str, stats: Optional[TableStats]) -> AlterOperationDetail:
        """Analyze DROP COLUMN operation."""
        detail = AlterOperationDetail(
            operation_type="DROP_COLUMN",
            is_risky=True
        )
        
        # Extract column name
        match = re.search(r'drop column\s+([a-zA-Z_][a-zA-Z0-9_$]*)', stmt)
        if match:
            detail.column_name = match.group(1)
        
        detail.risk_reasons.append("❌ DROP COLUMN removes data permanently (irreversible)")
        detail.recommendations.append("Mark column as unused first, then drop after verifying no one uses it")
        detail.recommendations.append("Backup the table before dropping: CREATE TABLE backup AS SELECT * FROM table")
        
        if stats and stats.row_count > 0:
            detail.risk_reasons.append(f"   ⚠️  Column contains data for {stats.row_count:,} rows")
        
        # Check if CASCADE is used
        if "cascade" in stmt:
            detail.risk_reasons.append("⚠️  CASCADE will drop dependent objects (views, constraints, etc.)")
            detail.recommendations.append("Review all dependent objects before using CASCADE")
        
        return detail
    
    def _analyze_alter_column(self, stmt: str, stats: Optional[TableStats]) -> AlterOperationDetail:
        """Analyze ALTER COLUMN operation."""
        detail = AlterOperationDetail(
            operation_type="ALTER_COLUMN",
            is_risky=False
        )
        
        # Extract column name
        match = re.search(r'alter column\s+([a-zA-Z_][a-zA-Z0-9_$]*)', stmt)
        if match:
            detail.column_name = match.group(1)
        
        # Check for TYPE change (data type conversion)
        if "type" in stmt:
            detail.is_risky = True
            detail.risk_reasons.append("❌ Changing column data type (requires conversion)")
            detail.recommendations.append("Test conversion on a staging environment first")
            detail.recommendations.append("Consider adding a new column with the new type, backfill, then drop old")
            
            if stats and stats.row_count > 100000:
                detail.risk_reasons.append(f"⚠️  Large table ({stats.row_count:,} rows) — conversion may take time")
                detail.recommendations.append("Use USING clause for custom conversion logic")
        
        # Check for SET NOT NULL
        if "set not null" in stmt:
            detail.is_risky = True
            detail.risk_reasons.append("❌ Setting NOT NULL on a column (will fail if null values exist)")
            detail.recommendations.append("Check for NULL values first: SELECT COUNT(*) FROM table WHERE column IS NULL")
            
            if stats and stats.row_count > 0:
                detail.risk_reasons.append(f"⚠️  Table has {stats.row_count:,} rows — some may have NULL values")
        
        # Check for DROP NOT NULL
        if "drop not null" in stmt:
            detail.is_risky = False
            detail.risk_reasons.append("✅ Dropping NOT NULL constraint — safe (allows NULL values)")
        
        # Check for SET DEFAULT
        if "set default" in stmt:
            detail.is_risky = False
            detail.risk_reasons.append("✅ Setting DEFAULT value — safe")
        
        # Check for DROP DEFAULT
        if "drop default" in stmt:
            detail.is_risky = False
            detail.risk_reasons.append("✅ Dropping DEFAULT value — safe")
        
        return detail
    
    def _analyze_rename_column(self, stmt: str, stats: Optional[TableStats]) -> AlterOperationDetail:
        """Analyze RENAME COLUMN operation."""
        detail = AlterOperationDetail(
            operation_type="RENAME",
            is_risky=True
        )
        
        # Extract old and new column names
        match = re.search(r'rename column\s+([a-zA-Z_][a-zA-Z0-9_$]*)\s+to\s+([a-zA-Z_][a-zA-Z0-9_$]*)', stmt)
        if match:
            detail.column_name = match.group(1)
            detail.new_name = match.group(2)
        
        detail.risk_reasons.append("❌ Renaming column breaks application code that references old name")
        detail.recommendations.append("Update application code to use new name BEFORE renaming")
        detail.recommendations.append("Create a view with the old name temporarily to avoid breaking changes")
        
        if stats and stats.index_count > 0:
            detail.risk_reasons.append(f"⚠️  Table has {stats.index_count} indexes — they will also need to be updated")
            detail.recommendations.append("Check indexes that reference this column")
        
        return detail
    
    def _analyze_rename_table(self, stmt: str, stats: Optional[TableStats]) -> AlterOperationDetail:
        """Analyze RENAME TABLE operation."""
        detail = AlterOperationDetail(
            operation_type="RENAME",
            is_risky=True
        )
        
        # Extract old and new table names
        match = re.search(r'rename table\s+([a-zA-Z_][a-zA-Z0-9_$]*)\s+to\s+([a-zA-Z_][a-zA-Z0-9_$]*)', stmt)
        if match:
            detail.column_name = match.group(1)  # Old table name
            detail.new_name = match.group(2)     # New table name
        
        detail.risk_reasons.append("❌ Renaming table breaks application code that references old name")
        detail.recommendations.append("Update application code to use new name BEFORE renaming")
        detail.recommendations.append("Create a view with the old name temporarily to avoid breaking changes")
        
        if stats and stats.foreign_keys:
            detail.risk_reasons.append(f"⚠️  Table has foreign keys: {', '.join(stats.foreign_keys)}")
            detail.recommendations.append("Foreign key constraints reference this table — they may need to be updated")
        
        return detail
    
    def _analyze_add_constraint(self, stmt: str, stats: Optional[TableStats]) -> AlterOperationDetail:
        """Analyze ADD CONSTRAINT operation."""
        detail = AlterOperationDetail(
            operation_type="ADD_CONSTRAINT",
            is_risky=False
        )
        
        # Determine constraint type
        if "foreign key" in stmt:
            detail.constraint_type = "FOREIGN KEY"
            detail.is_risky = True
            detail.risk_reasons.append("⚠️  Adding foreign key constraint — may fail if data doesn't match")
            detail.recommendations.append("Check for orphaned rows first: SELECT * FROM table WHERE fk_column NOT IN (SELECT id FROM referenced_table)")
            
            if stats and stats.row_count > 100000:
                detail.risk_reasons.append(f"⚠️  Large table ({stats.row_count:,} rows) — validation may take time")
                detail.recommendations.append("Use NOT VALID to add constraint without validation, then validate later")
        
        elif "unique" in stmt:
            detail.constraint_type = "UNIQUE"
            detail.is_risky = True
            detail.risk_reasons.append("⚠️  Adding UNIQUE constraint — may fail if duplicates exist")
            detail.recommendations.append("Check for duplicates first")
        
        elif "check" in stmt:
            detail.constraint_type = "CHECK"
            detail.is_risky = True
            detail.risk_reasons.append("⚠️  Adding CHECK constraint — may fail if existing data violates it")
            detail.recommendations.append("Test the check condition on existing data first")
        
        elif "primary key" in stmt:
            detail.constraint_type = "PRIMARY KEY"
            detail.is_risky = True
            detail.risk_reasons.append("⚠️  Adding PRIMARY KEY — may fail if duplicates exist")
            detail.recommendations.append("Ensure the column(s) have unique, non-null values")
        
        return detail
    
    def _analyze_drop_constraint(self, stmt: str, stats: Optional[TableStats]) -> AlterOperationDetail:
        """Analyze DROP CONSTRAINT operation."""
        detail = AlterOperationDetail(
            operation_type="DROP_CONSTRAINT",
            is_risky=True
        )
        
        detail.risk_reasons.append("❌ Dropping constraint removes data integrity rules")
        detail.recommendations.append("Consider making the constraint INACTIVE first (if supported)")
        detail.recommendations.append("Check application code that relies on this constraint")
        
        # Try to extract constraint name
        match = re.search(r'drop constraint\s+([a-zA-Z_][a-zA-Z0-9_$]*)', stmt)
        if match:
            detail.column_name = match.group(1)
            detail.risk_reasons.append(f"   Constraint: {detail.column_name}")
        
        return detail