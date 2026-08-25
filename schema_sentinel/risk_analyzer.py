"""Risk analysis engine — assesses migration danger levels using production stats."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .models import MigrationOperation, OperationType
from .profiler import TableStats, DatabaseProfiler
from .alter_analyzer import AlterAnalyzer


class RiskLevel(Enum):
    """Overall risk levels."""
    LOW = "🟢"
    MEDIUM = "🟡"
    HIGH = "🔴"
    UNKNOWN = "⚪"


@dataclass
class RiskAssessment:
    """Complete risk assessment for a migration operation."""
    operation: MigrationOperation
    table_stats: Optional[TableStats]
    
    # Individual risk scores (0-10, where 10 is highest risk)
    lock_risk: int = 0
    data_integrity_risk: int = 0
    compatibility_risk: int = 0
    performance_risk: int = 0
    
    # Overall level
    overall_level: RiskLevel = RiskLevel.UNKNOWN
    
    # Explanation of risks
    risk_explanations: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the risk assessment."""
        lines = []
        lines.append(f"  {self.overall_level.value} Risk: {self.overall_level.name}")
        lines.append(f"  Table: {self.operation.table_name or 'unknown'}")
        lines.append(f"  Operation: {self.operation.operation_type.value.replace('_', ' ').title()}")
        
        if self.table_stats:
            lines.append(f"  Row Count: {self.table_stats.row_count:,}")
            lines.append(f"  Table Size: {self.table_stats.total_size_mb:.2f} MB")
        
        lines.append(f"  Lock Risk: {self.lock_risk}/10")
        lines.append(f"  Data Integrity Risk: {self.data_integrity_risk}/10")
        lines.append(f"  Compatibility Risk: {self.compatibility_risk}/10")
        lines.append(f"  Performance Risk: {self.performance_risk}/10")
        
        if self.risk_explanations:
            lines.append("  ⚠️  Risks:")
            for expl in self.risk_explanations:
                lines.append(f"    - {expl}")
        
        if self.recommendations:
            lines.append("  💡 Recommendations:")
            for rec in self.recommendations:
                lines.append(f"    - {rec}")
        
        return "\n".join(lines)


class RiskAnalyzer:
    """Analyzes migration operations using production database statistics."""
    
    def __init__(self, profiler: Optional[DatabaseProfiler] = None):
        """
        Initialize the risk analyzer.
        
        Args:
            profiler: DatabaseProfiler instance for fetching production stats.
                     If None, uses heuristic-based analysis only.
        """
        self.profiler = profiler
        self._stats_cache: Dict[str, TableStats] = {}
    
    def analyze_operation(self, operation: MigrationOperation) -> RiskAssessment:
        """
        Analyze a single migration operation for risk.
        
        Args:
            operation: The migration operation to analyze.
            
        Returns:
            RiskAssessment with all risk scores and recommendations.
        """
        # Fetch table stats (from cache or database)
        table_stats = None
        if operation.table_name and self.profiler:
            table_stats = self._get_table_stats(operation.table_name)
        
        assessment = RiskAssessment(
            operation=operation,
            table_stats=table_stats,
        )
        
        # Calculate risk based on operation type
        if operation.operation_type == OperationType.CREATE_TABLE:
            assessment = self._assess_create_table(operation, table_stats)
        elif operation.operation_type == OperationType.ALTER_TABLE:
            assessment = self._assess_alter_table(operation, table_stats)
        elif operation.operation_type == OperationType.DROP_TABLE:
            assessment = self._assess_drop_table(operation, table_stats)
        elif operation.operation_type == OperationType.CREATE_INDEX:
            assessment = self._assess_create_index(operation, table_stats)
        elif operation.operation_type == OperationType.DROP_INDEX:
            assessment = self._assess_drop_index(operation, table_stats)
        elif operation.operation_type in (OperationType.RENAME_TABLE, OperationType.RENAME_COLUMN):
            assessment = self._assess_rename(operation, table_stats)
        elif operation.operation_type in (OperationType.CREATE_CONSTRAINT, OperationType.DROP_CONSTRAINT):
            assessment = self._assess_constraint(operation, table_stats)
        
        # Determine overall risk level
        assessment.overall_level = self._calculate_overall_level(assessment)
        
        return assessment
    
    def _get_table_stats(self, table_name: str) -> Optional[TableStats]:
        """Get table stats from cache or database."""
        if table_name in self._stats_cache:
            return self._stats_cache[table_name]
        
        if self.profiler:
            stats = self.profiler.get_table_stats(table_name)
            if stats:
                self._stats_cache[table_name] = stats
            return stats
        
        return None
    
    def _assess_create_table(self, op: MigrationOperation, stats: Optional[TableStats]) -> RiskAssessment:
        """Assess CREATE TABLE risk."""
        assessment = RiskAssessment(operation=op, table_stats=stats)
        
        # CREATE TABLE is generally low risk
        assessment.lock_risk = 1
        assessment.data_integrity_risk = 1
        assessment.compatibility_risk = 2
        assessment.performance_risk = 1
        
        assessment.risk_explanations.append("New table creation is generally safe")
        assessment.recommendations.append("Ensure the table name doesn't conflict with existing tables")
        
        return assessment
    
    def _assess_alter_table(self, op: MigrationOperation, stats: Optional[TableStats]) -> RiskAssessment:
        """Assess ALTER TABLE risk with detailed analysis."""
        assessment = RiskAssessment(operation=op, table_stats=stats)
        
        # Add detailed ALTER analysis
        alter_analyzer = AlterAnalyzer()
        alter_detail = alter_analyzer.analyze(op, stats)
        
        # Base risk from table stats
        if not stats:
            assessment.lock_risk = 5
            assessment.data_integrity_risk = 5
            assessment.compatibility_risk = 5
            assessment.performance_risk = 5
            assessment.risk_explanations.append("⚠️  No production stats available — using default risk scores")
            assessment.recommendations.append(f"🔍 Run 'schema-sentinel profile {op.table_name}' to get real stats")
        else:
            # Lock risk based on table size
            row_count = stats.row_count
            if row_count < 10000:
                assessment.lock_risk = 2
                assessment.risk_explanations.append(f"Small table ({row_count:,} rows) — lock will be brief")
            elif row_count < 100000:
                assessment.lock_risk = 5
                assessment.risk_explanations.append(f"Medium table ({row_count:,} rows) — lock may take a few seconds")
            elif row_count < 1000000:
                assessment.lock_risk = 8
                assessment.risk_explanations.append(f"Large table ({row_count:,} rows) — ALTER TABLE could lock for minutes")
                assessment.recommendations.append("Consider using pg_repack or gh-ost for online schema changes")
            else:
                assessment.lock_risk = 10
                assessment.risk_explanations.append(f"Very large table ({row_count:,} rows) — ALTER TABLE could lock for hours")
                assessment.recommendations.append("⚠️  Use Expand-Contract pattern or dedicated online migration tool")
        
        # Add detailed risk reasons from alter_analyzer
        if alter_detail.risk_reasons:
            for reason in alter_detail.risk_reasons:
                assessment.risk_explanations.append(reason)
        
        if alter_detail.recommendations:
            for rec in alter_detail.recommendations:
                assessment.recommendations.append(rec)
        
        # Adjust risks based on detailed analysis
        if alter_detail.is_risky:
            assessment.data_integrity_risk += 3
            assessment.compatibility_risk += 3
            if assessment.data_integrity_risk > 10:
                assessment.data_integrity_risk = 10
            if assessment.compatibility_risk > 10:
                assessment.compatibility_risk = 10
        else:
            # If not risky, lower the risks
            assessment.data_integrity_risk = max(1, assessment.data_integrity_risk - 2)
            assessment.compatibility_risk = max(1, assessment.compatibility_risk - 2)
        
        # Performance risk
        if assessment.performance_risk == 5 and stats:  # Only if default was set
            assessment.performance_risk = 4
            assessment.risk_explanations.append("ALTER TABLE may affect query performance temporarily")
        
        return assessment
    
    def _assess_drop_table(self, op: MigrationOperation, stats: Optional[TableStats]) -> RiskAssessment:
        """Assess DROP TABLE risk — HIGHEST RISK."""
        assessment = RiskAssessment(operation=op, table_stats=stats)
        
        # This is always high risk
        assessment.lock_risk = 5
        assessment.data_integrity_risk = 10
        assessment.compatibility_risk = 10
        assessment.performance_risk = 3
        
        assessment.risk_explanations.append("⚠️  DROP TABLE is irreversible — all data will be lost!")
        assessment.recommendations.append("Rename the table first (RENAME TABLE) and verify before dropping")
        assessment.recommendations.append("Backup the table before dropping: CREATE TABLE backup_{table} AS SELECT * FROM {table}")
        
        if stats:
            assessment.risk_explanations.append(f"Table contains {stats.row_count:,} rows")
            if stats.foreign_keys and len(stats.foreign_keys) > 0:
                assessment.risk_explanations.append(f"⚠️  Table has foreign keys: {', '.join(stats.foreign_keys[:3])}")
                if len(stats.foreign_keys) > 3:
                    assessment.risk_explanations.append(f"   ... and {len(stats.foreign_keys) - 3} more")
                assessment.recommendations.append("Drop foreign key constraints first, or use CASCADE carefully")
        
        return assessment
    
    def _assess_create_index(self, op: MigrationOperation, stats: Optional[TableStats]) -> RiskAssessment:
        """Assess CREATE INDEX risk."""
        assessment = RiskAssessment(operation=op, table_stats=stats)
        
        if not stats:
            assessment.lock_risk = 5
            assessment.data_integrity_risk = 1
            assessment.compatibility_risk = 3
            assessment.performance_risk = 5
            assessment.risk_explanations.append("No production stats available — using default risk scores")
            return assessment
        
        # CREATE INDEX can lock tables and hurt performance
        row_count = stats.row_count
        if row_count < 10000:
            assessment.lock_risk = 2
            assessment.risk_explanations.append(f"Small table ({row_count:,} rows) — index creation will be fast")
        elif row_count < 100000:
            assessment.lock_risk = 5
            assessment.risk_explanations.append(f"Medium table ({row_count:,} rows) — index creation may take seconds")
        else:
            assessment.lock_risk = 8
            assessment.risk_explanations.append(f"Large table ({row_count:,} rows) — index creation could take minutes")
            assessment.recommendations.append("Use CONCURRENTLY for index creation: CREATE INDEX CONCURRENTLY ...")
        
        # Performance risk: new index improves reads, hurts writes
        assessment.performance_risk = 4
        assessment.risk_explanations.append("New index will improve read performance but slow down writes")
        
        assessment.data_integrity_risk = 1  # Very low
        
        # Compatibility risk: low
        assessment.compatibility_risk = 1
        
        assessment.recommendations.append("For large tables, always use CREATE INDEX CONCURRENTLY to avoid locking")
        
        return assessment
    
    def _assess_drop_index(self, op: MigrationOperation, stats: Optional[TableStats]) -> RiskAssessment:
        """Assess DROP INDEX risk."""
        assessment = RiskAssessment(operation=op, table_stats=stats)
        
        assessment.lock_risk = 2
        assessment.data_integrity_risk = 1
        assessment.compatibility_risk = 5
        assessment.performance_risk = 6
        
        assessment.risk_explanations.append("Dropping an index will slow down queries that use it")
        assessment.recommendations.append("Check query performance after dropping the index")
        assessment.recommendations.append("Consider making the index INACTIVE first (if supported)")
        
        if stats and stats.index_count <= 1:
            assessment.risk_explanations.append("⚠️  This is the only index on the table — queries may become very slow")
            assessment.performance_risk = 9
        
        return assessment
    
    def _assess_rename(self, op: MigrationOperation, stats: Optional[TableStats]) -> RiskAssessment:
        """Assess RENAME risk."""
        assessment = RiskAssessment(operation=op, table_stats=stats)
        
        assessment.lock_risk = 3
        assessment.data_integrity_risk = 3
        assessment.compatibility_risk = 8
        assessment.performance_risk = 2
        
        assessment.risk_explanations.append("Renaming breaks any application code that references the old name")
        assessment.recommendations.append("Update application code to use the new name BEFORE renaming")
        assessment.recommendations.append("Create a view with the old name temporarily to avoid breaking changes")
        
        if stats and stats.foreign_keys and len(stats.foreign_keys) > 0:
            assessment.risk_explanations.append(f"⚠️  Table has foreign keys: {', '.join(stats.foreign_keys[:3])}")
            if len(stats.foreign_keys) > 3:
                assessment.risk_explanations.append(f"   ... and {len(stats.foreign_keys) - 3} more")
            assessment.recommendations.append("Foreign key constraints reference this table — they may need to be updated")
        
        return assessment
    
    def _assess_constraint(self, op: MigrationOperation, stats: Optional[TableStats]) -> RiskAssessment:
        """Assess ADD CONSTRAINT or DROP CONSTRAINT risk."""
        assessment = RiskAssessment(operation=op, table_stats=stats)
        
        if op.operation_type == OperationType.CREATE_CONSTRAINT:
            assessment.lock_risk = 6 if stats and stats.row_count > 100000 else 3
            assessment.data_integrity_risk = 4
            assessment.compatibility_risk = 4
            assessment.performance_risk = 3
            
            assessment.risk_explanations.append("Adding constraints validates all existing data")
            assessment.recommendations.append("Use NOT VALID to add constraint without validation, then validate later")
            
            if stats and stats.row_count > 100000:
                assessment.risk_explanations.append(f"Large table ({stats.row_count:,} rows) — validation will take time")
                assessment.recommendations.append("Add constraint with NOT VALID, then VALIDATE CONSTRAINT during low traffic")
        else:  # DROP CONSTRAINT
            assessment.lock_risk = 2
            assessment.data_integrity_risk = 6
            assessment.compatibility_risk = 6
            assessment.performance_risk = 2
            
            assessment.risk_explanations.append("Dropping constraints may allow invalid data to be inserted")
            assessment.recommendations.append("Consider making the constraint INACTIVE first (if supported)")
        
        return assessment
    
    def _calculate_overall_level(self, assessment: RiskAssessment) -> RiskLevel:
        """Calculate overall risk level from individual scores."""
        # If any risk is 8+, mark as HIGH
        max_risk = max(
            assessment.lock_risk,
            assessment.data_integrity_risk,
            assessment.compatibility_risk,
            assessment.performance_risk
        )
        
        if max_risk >= 8:
            return RiskLevel.HIGH
        elif max_risk >= 5:
            return RiskLevel.MEDIUM
        elif max_risk > 0:
            return RiskLevel.LOW
        else:
            return RiskLevel.UNKNOWN