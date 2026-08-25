"""CI/CD integration — format output for GitHub Actions and other CI tools."""

import json
from typing import List

from .models import MigrationOperation
from .risk_analyzer import RiskAssessment, RiskLevel


class CIConfig:
    """Configuration for CI/CD integration."""
    
    def __init__(self, fail_on_high_risk: bool = True):
        self.fail_on_high_risk = fail_on_high_risk


class CIAnalyzer:
    """Analyzes migrations with CI/CD-friendly output."""
    
    def __init__(self, config: CIConfig = None):
        self.config = config or CIConfig()
    
    def generate_github_comment(self, assessments: List[RiskAssessment]) -> str:
        """
        Generate a GitHub comment from risk assessments.
        
        Returns:
            Markdown-formatted string for GitHub PR comments.
        """
        lines = []
        lines.append("## 🔍 Schema Sentinel Migration Analysis")
        lines.append("")
        lines.append("| Operation | Table | Risk Level | Lock Risk | Data Integrity | Compatibility | Performance |")
        lines.append("|-----------|-------|------------|-----------|----------------|--------------|-------------|")
        
        for assessment in assessments:
            risk_emoji = assessment.overall_level.value
            op_type = assessment.operation.operation_type.value.replace("_", " ").title()
            table = assessment.operation.table_name or "unknown"
            
            lines.append(
                f"| {op_type} | `{table}` | {risk_emoji} {assessment.overall_level.name} | "
                f"{assessment.lock_risk}/10 | {assessment.data_integrity_risk}/10 | "
                f"{assessment.compatibility_risk}/10 | {assessment.performance_risk}/10 |"
            )
        
        lines.append("")
        
        # Add risk details for high-risk operations
        high_risk = [a for a in assessments if a.overall_level == RiskLevel.HIGH]
        if high_risk:
            lines.append("### ⚠️ High-Risk Operations")
            for assessment in high_risk:
                lines.append("")
                lines.append(f"**{assessment.operation.operation_type.value.replace('_', ' ').title()}** on `{assessment.operation.table_name}`")
                for explanation in assessment.risk_explanations:
                    lines.append(f"- {explanation}")
                for recommendation in assessment.recommendations:
                    lines.append(f"  - 💡 {recommendation}")
                lines.append("")
        else:
            lines.append("### ✅ No high-risk operations detected")
        
        return "\n".join(lines)
    
    def generate_json_output(self, assessments: List[RiskAssessment]) -> str:
        """
        Generate JSON output for other CI tools.
        
        Returns:
            JSON string with all assessment data.
        """
        data = {
            "assessments": [],
            "summary": {
                "total_operations": len(assessments),
                "high_risk_count": len([a for a in assessments if a.overall_level == RiskLevel.HIGH]),
                "medium_risk_count": len([a for a in assessments if a.overall_level == RiskLevel.MEDIUM]),
                "low_risk_count": len([a for a in assessments if a.overall_level == RiskLevel.LOW]),
            }
        }
        
        for assessment in assessments:
            data["assessments"].append({
                "operation_type": assessment.operation.operation_type.value,
                "table_name": assessment.operation.table_name,
                "risk_level": assessment.overall_level.name,
                "risk_level_emoji": assessment.overall_level.value,
                "lock_risk": assessment.lock_risk,
                "data_integrity_risk": assessment.data_integrity_risk,
                "compatibility_risk": assessment.compatibility_risk,
                "performance_risk": assessment.performance_risk,
                "risk_explanations": assessment.risk_explanations,
                "recommendations": assessment.recommendations,
            })
        
        return json.dumps(data, indent=2)