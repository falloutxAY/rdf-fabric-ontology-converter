"""
Data models for compliance validation and conversion reporting.

This module contains the dataclasses and enums used by the compliance
validation system.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# Enums
# =============================================================================

class ComplianceLevel(Enum):
    """Compliance validation result levels."""
    COMPLIANT = "compliant"
    WARNING = "warning"
    ERROR = "error"


class ConversionImpact(Enum):
    """Impact level of conversion transformations."""
    PRESERVED = "preserved"  # Fully preserved in conversion
    CONVERTED_WITH_LIMITATIONS = "converted_with_limitations"  # Converted but with some loss
    LOST = "lost"  # Cannot be represented in target format
    TRANSFORMED = "transformed"  # Semantically changed during conversion


class DTDLVersion(Enum):
    """Supported DTDL versions."""
    V2 = 2
    V3 = 3
    V4 = 4


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ComplianceIssue:
    """Represents a single compliance issue or warning."""
    level: ComplianceLevel
    code: str
    message: str
    location: Optional[str] = None  # File path, line number, or element identifier
    element_type: Optional[str] = None  # Interface, Property, Class, etc.
    element_name: Optional[str] = None
    suggestion: Optional[str] = None  # How to fix or workaround
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "level": self.level.value,
            "code": self.code,
            "message": self.message,
        }
        if self.location:
            result["location"] = self.location
        if self.element_type:
            result["element_type"] = self.element_type
        if self.element_name:
            result["element_name"] = self.element_name
        if self.suggestion:
            result["suggestion"] = self.suggestion
        return result


@dataclass
class ConversionWarning:
    """Represents a warning about information loss during conversion."""
    impact: ConversionImpact
    feature: str
    source_construct: str  # Original construct (e.g., "owl:Restriction", "Command")
    target_representation: Optional[str] = None  # How it's represented in target (or None if lost)
    details: Optional[str] = None
    affected_elements: List[str] = field(default_factory=list)
    workaround: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "impact": self.impact.value,
            "feature": self.feature,
            "source_construct": self.source_construct,
        }
        if self.target_representation:
            result["target_representation"] = self.target_representation
        if self.details:
            result["details"] = self.details
        if self.affected_elements:
            result["affected_elements"] = self.affected_elements
        if self.workaround:
            result["workaround"] = self.workaround
        return result


@dataclass
class ComplianceResult:
    """Result of compliance validation."""
    is_valid: bool
    source_type: str  # "DTDL" or "RDF/OWL"
    version: Optional[str] = None
    issues: List[ComplianceIssue] = field(default_factory=list)
    warnings: List[ConversionWarning] = field(default_factory=list)
    statistics: Dict[str, int] = field(default_factory=dict)
    
    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == ComplianceLevel.ERROR)
    
    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.level == ComplianceLevel.WARNING)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "source_type": self.source_type,
            "version": self.version,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [i.to_dict() for i in self.issues],
            "warnings": [w.to_dict() for w in self.warnings],
            "statistics": self.statistics,
        }


@dataclass
class ConversionReport:
    """Comprehensive report of a conversion process."""
    timestamp: str
    source_format: str
    target_format: str = "Fabric IQ Ontology"
    
    # Summary counts
    total_elements: int = 0
    preserved_count: int = 0
    converted_with_limitations_count: int = 0
    lost_count: int = 0
    
    # Detailed breakdowns
    preserved_features: List[str] = field(default_factory=list)
    limited_features: List[ConversionWarning] = field(default_factory=list)
    lost_features: List[ConversionWarning] = field(default_factory=list)
    
    # Source compliance
    compliance_result: Optional[ComplianceResult] = None
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "source_format": self.source_format,
            "target_format": self.target_format,
            "summary": {
                "total_elements": self.total_elements,
                "preserved": self.preserved_count,
                "converted_with_limitations": self.converted_with_limitations_count,
                "lost": self.lost_count,
            },
            "preserved_features": self.preserved_features,
            "limited_features": [w.to_dict() for w in self.limited_features],
            "lost_features": [w.to_dict() for w in self.lost_features],
            "compliance": self.compliance_result.to_dict() if self.compliance_result else None,
            "recommendations": self.recommendations,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def get_summary_text(self) -> str:
        """Get human-readable summary."""
        lines = [
            f"Conversion Report - {self.source_format} → {self.target_format}",
            f"Generated: {self.timestamp}",
            "",
            "Summary:",
            f"  Total elements: {self.total_elements}",
            f"  Fully preserved: {self.preserved_count}",
            f"  Converted with limitations: {self.converted_with_limitations_count}",
            f"  Information lost: {self.lost_count}",
            "",
        ]
        
        if self.limited_features:
            lines.append("Features converted with limitations:")
            for warning in self.limited_features:
                lines.append(f"  - {warning.feature}: {warning.details or warning.source_construct}")
            lines.append("")
        
        if self.lost_features:
            lines.append("Features lost in conversion:")
            for warning in self.lost_features:
                lines.append(f"  - {warning.feature}: {warning.details or warning.source_construct}")
                if warning.workaround:
                    lines.append(f"    Workaround: {warning.workaround}")
            lines.append("")
        
        if self.recommendations:
            lines.append("Recommendations:")
            for rec in self.recommendations:
                lines.append(f"  - {rec}")
        
        return "\n".join(lines)
    
    def to_markdown(self) -> str:
        """Convert report to Markdown format."""
        lines = [
            f"# Conversion Report",
            f"",
            f"**Source Format:** {self.source_format}",
            f"**Target Format:** {self.target_format}",
            f"**Generated:** {self.timestamp}",
            "",
            "## Summary",
            "",
            "| Metric | Count |",
            "|--------|-------|",
            f"| Total Elements | {self.total_elements} |",
            f"| Fully Preserved | {self.preserved_count} |",
            f"| Converted with Limitations | {self.converted_with_limitations_count} |",
            f"| Information Lost | {self.lost_count} |",
            "",
        ]
        
        if self.preserved_features:
            lines.extend([
                "## Preserved Features",
                "",
            ])
            for feat in self.preserved_features:
                lines.append(f"- {feat}")
            lines.append("")
        
        if self.limited_features:
            lines.extend([
                "## Features Converted with Limitations",
                "",
                "| Feature | Impact | Details |",
                "|---------|--------|---------|",
            ])
            for warning in self.limited_features:
                details = warning.details or warning.source_construct
                lines.append(f"| {warning.feature} | {warning.impact.value} | {details} |")
            lines.append("")
        
        if self.lost_features:
            lines.extend([
                "## Features Lost in Conversion",
                "",
                "| Feature | Details | Workaround |",
                "|---------|---------|------------|",
            ])
            for warning in self.lost_features:
                details = warning.details or warning.source_construct
                workaround = warning.workaround or "N/A"
                lines.append(f"| {warning.feature} | {details} | {workaround} |")
            lines.append("")
        
        if self.recommendations:
            lines.extend([
                "## Recommendations",
                "",
            ])
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")
        
        return "\n".join(lines)
