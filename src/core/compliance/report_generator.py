"""
Conversion Report Generator.

Creates comprehensive reports from compliance validation results.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .models import (
    ComplianceLevel,
    ComplianceIssue,
    ComplianceResult,
    ConversionImpact,
    ConversionReport,
    ConversionWarning,
    DTDLVersion,
)

if TYPE_CHECKING:
    from rdflib import Graph

logger = logging.getLogger(__name__)


class ConversionReportGenerator:
    """
    Generates comprehensive conversion reports.
    
    Combines compliance results with conversion outcomes
    to produce actionable reports.
    """
    
    def __init__(self, include_statistics: bool = True):
        """
        Initialize generator.
        
        Args:
            include_statistics: Include detailed statistics in reports
        """
        self.include_statistics = include_statistics
    
    def generate_dtdl_report(self, interfaces: List[Any]) -> ConversionReport:
        """
        Generate a conversion report for DTDL to Fabric conversion.
        
        Args:
            interfaces: List of DTDLInterface objects
            
        Returns:
            ConversionReport with detailed findings
        """
        from .dtdl_compliance import DTDLComplianceValidator
        from .constants import DTDL_FEATURE_SUPPORT
        
        report = ConversionReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_format="DTDL",
        )
        
        # Validate DTDL compliance first
        validator = DTDLComplianceValidator()
        report.compliance_result = validator.validate(interfaces)
        
        # Analyze features
        feature_counts: Dict[str, int] = {}
        
        for iface in interfaces:
            report.total_elements += 1
            
            # Properties (full support)
            props = getattr(iface, 'properties', []) or []
            feature_counts["Property"] = feature_counts.get("Property", 0) + len(props)
            
            # Relationships (full support)
            rels = getattr(iface, 'relationships', []) or []
            feature_counts["Relationship"] = feature_counts.get("Relationship", 0) + len(rels)
            
            # Telemetry (partial support)
            tels = getattr(iface, 'telemetries', []) or []
            feature_counts["Telemetry"] = feature_counts.get("Telemetry", 0) + len(tels)
            
            # Commands (not supported)
            cmds = getattr(iface, 'commands', []) or []
            feature_counts["Command"] = feature_counts.get("Command", 0) + len(cmds)
            
            # Components (partial support)
            comps = getattr(iface, 'components', []) or []
            feature_counts["Component"] = feature_counts.get("Component", 0) + len(comps)
            
            # Check for complex schemas
            for prop in props:
                schema = getattr(prop, 'schema', None)
                if schema and not isinstance(schema, str):
                    schema_type = type(schema).__name__
                    feature_counts[schema_type] = feature_counts.get(schema_type, 0) + 1
        
        # Categorize features
        for feature, count in feature_counts.items():
            if count == 0:
                continue
            
            support_info = DTDL_FEATURE_SUPPORT.get(feature, {})
            support_level = support_info.get("support", "partial")
            
            if support_level == "full":
                report.preserved_count += count
                if feature not in report.preserved_features:
                    report.preserved_features.append(f"{feature} ({count})")
            
            elif support_level == "partial":
                report.converted_with_limitations_count += count
                report.limited_features.append(ConversionWarning(
                    impact=ConversionImpact.CONVERTED_WITH_LIMITATIONS,
                    feature=feature,
                    source_construct=feature,
                    target_representation=support_info.get("notes", "Converted with modifications"),
                    details=f"{count} {feature}(s) converted with limitations",
                ))
            
            else:  # none
                report.lost_count += count
                report.lost_features.append(ConversionWarning(
                    impact=ConversionImpact.LOST,
                    feature=feature,
                    source_construct=feature,
                    details=f"{count} {feature}(s) cannot be represented in Fabric",
                    workaround=support_info.get("notes"),
                ))
        
        # Add recommendations
        if feature_counts.get("Command", 0) > 0:
            report.recommendations.append(
                "Commands are not supported in Fabric IQ Ontology. "
                "Consider implementing command logic in your application layer."
            )
        
        if feature_counts.get("Component", 0) > 0:
            report.recommendations.append(
                "Components are flattened into parent entities. "
                "Component reference semantics are lost."
            )
        
        return report
    
    def generate_rdf_report(self, graph: Any) -> ConversionReport:
        """
        Generate a conversion report for RDF/OWL to Fabric conversion.
        
        Args:
            graph: RDFLib Graph object
            
        Returns:
            ConversionReport with detailed findings
        """
        from rdflib import RDF, RDFS, OWL
        from .rdf_compliance import RDFOWLComplianceValidator
        from .constants import OWL_CONSTRUCT_SUPPORT
        
        report = ConversionReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_format="RDF/OWL",
        )
        
        # Validate RDF/OWL compliance first
        validator = RDFOWLComplianceValidator()
        report.compliance_result = validator.validate(graph)
        
        # Count constructs
        construct_counts: Dict[str, int] = {}
        
        # Classes
        for _ in graph.subjects(RDF.type, OWL.Class):
            construct_counts["owl:Class"] = construct_counts.get("owl:Class", 0) + 1
            report.total_elements += 1
        
        # Properties
        for _ in graph.subjects(RDF.type, OWL.DatatypeProperty):
            construct_counts["owl:DatatypeProperty"] = construct_counts.get("owl:DatatypeProperty", 0) + 1
            report.total_elements += 1
        
        for _ in graph.subjects(RDF.type, OWL.ObjectProperty):
            construct_counts["owl:ObjectProperty"] = construct_counts.get("owl:ObjectProperty", 0) + 1
            report.total_elements += 1
        
        # Restrictions
        for _ in graph.subjects(RDF.type, OWL.Restriction):
            construct_counts["owl:Restriction"] = construct_counts.get("owl:Restriction", 0) + 1
        
        # Property characteristics
        for char in [OWL.FunctionalProperty, OWL.TransitiveProperty, OWL.SymmetricProperty]:
            for _ in graph.subjects(RDF.type, char):
                char_name = str(char).split("#")[-1]
                construct_counts[f"owl:{char_name}"] = construct_counts.get(f"owl:{char_name}", 0) + 1
        
        # Categorize by support level
        for construct, count in construct_counts.items():
            if count == 0:
                continue
            
            support_info = OWL_CONSTRUCT_SUPPORT.get(construct, {})
            support_level = support_info.get("support", "none")
            
            if support_level == "full":
                report.preserved_count += count
                report.preserved_features.append(f"{construct} ({count})")
            
            elif support_level in ["partial", "metadata"]:
                report.converted_with_limitations_count += count
                report.limited_features.append(ConversionWarning(
                    impact=ConversionImpact.CONVERTED_WITH_LIMITATIONS,
                    feature=construct,
                    source_construct=construct,
                    target_representation=support_info.get("notes", ""),
                    details=f"{count} occurrence(s)",
                ))
            
            else:  # none
                report.lost_count += count
                report.lost_features.append(ConversionWarning(
                    impact=ConversionImpact.LOST,
                    feature=construct,
                    source_construct=construct,
                    details=f"{count} occurrence(s) - {support_info.get('notes', 'Not supported')}",
                    workaround=self._get_workaround(construct),
                ))
        
        # Add recommendations
        if construct_counts.get("owl:Restriction", 0) > 0:
            report.recommendations.append(
                "OWL Restrictions are not supported. Consider expressing constraints "
                "as explicit properties or external validation rules."
            )
        
        if any(k.startswith("owl:") and "Property" in k and k != "owl:DatatypeProperty" and k != "owl:ObjectProperty" 
               for k in construct_counts.keys()):
            report.recommendations.append(
                "Property characteristics (transitive, symmetric, etc.) are not materialized. "
                "If you need these semantics, implement them in your application logic."
            )
        
        return report
    
    def _get_workaround(self, construct: str) -> Optional[str]:
        """Get workaround suggestion for unsupported construct."""
        workarounds = {
            "owl:Restriction": "Express constraints as documentation or use SHACL for validation before import",
            "owl:FunctionalProperty": "Enforce functional constraint in application logic",
            "owl:TransitiveProperty": "Materialize transitive closure before import or query dynamically",
            "owl:SymmetricProperty": "Create inverse relationships explicitly",
            "owl:inverseOf": "Create both relationship types explicitly",
            "owl:equivalentClass": "Merge equivalent classes or use explicit mappings",
            "owl:imports": "Use ontology merge tools (robot, rapper) before conversion",
        }
        return workarounds.get(construct)
    
    def generate_report(
        self,
        source_result: ComplianceResult,
        target_result: Optional[ComplianceResult] = None,
        conversion_warnings: Optional[List[ConversionWarning]] = None,
        conversion_duration: Optional[float] = None,
    ) -> ConversionReport:
        """
        Generate a comprehensive conversion report.
        
        Args:
            source_result: Compliance result from source validation
            target_result: Compliance result from target validation (optional)
            conversion_warnings: Warnings generated during conversion
            conversion_duration: Time taken for conversion in seconds
            
        Returns:
            ConversionReport with combined findings
        """
        warnings = conversion_warnings or []
        
        # Combine issues from both validations
        all_issues = list(source_result.issues)
        if target_result:
            all_issues.extend(target_result.issues)
        
        # Generate statistics
        statistics = {}
        if self.include_statistics:
            statistics = self._generate_statistics(
                source_result,
                target_result,
                all_issues,
                warnings,
            )
        
        # Determine overall success
        success = source_result.is_valid
        if target_result:
            success = success and target_result.is_valid
        
        # Calculate counts
        error_count = sum(1 for i in all_issues if i.level == ComplianceLevel.ERROR)
        warning_count = sum(1 for i in all_issues if i.level == ComplianceLevel.WARNING)
        info_count = sum(1 for i in all_issues if i.level == ComplianceLevel.INFO)
        
        return ConversionReport(
            timestamp=datetime.now(timezone.utc),
            success=success,
            source_type=source_result.source_type,
            target_type=target_result.source_type if target_result else "N/A",
            source_version=source_result.version,
            target_version=target_result.version if target_result else "N/A",
            compliance_issues=all_issues,
            conversion_warnings=warnings,
            statistics=statistics,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            duration_seconds=conversion_duration,
        )
    
    def _generate_statistics(
        self,
        source_result: ComplianceResult,
        target_result: Optional[ComplianceResult],
        issues: List[ComplianceIssue],
        warnings: List[ConversionWarning],
    ) -> Dict[str, Any]:
        """Generate detailed statistics."""
        stats = {
            "source": source_result.statistics.copy(),
            "issues_by_level": {
                "error": sum(1 for i in issues if i.level == ComplianceLevel.ERROR),
                "warning": sum(1 for i in issues if i.level == ComplianceLevel.WARNING),
                "info": sum(1 for i in issues if i.level == ComplianceLevel.INFO),
            },
            "issues_by_type": {},
            "conversion_impact": {
                "none": 0,
                "partial": 0,
                "full": 0,
            },
        }
        
        # Count issues by element type
        for issue in issues:
            elem_type = issue.element_type
            if elem_type not in stats["issues_by_type"]:
                stats["issues_by_type"][elem_type] = 0
            stats["issues_by_type"][elem_type] += 1
            
            # Count conversion impact
            if issue.conversion_impact:
                impact_key = issue.conversion_impact.value
                stats["conversion_impact"][impact_key] += 1
        
        if target_result:
            stats["target"] = target_result.statistics.copy()
        
        # Add warning statistics
        stats["warnings_count"] = len(warnings)
        
        return stats
    
    def to_json(self, report: ConversionReport, indent: int = 2) -> str:
        """
        Convert report to JSON string.
        
        Args:
            report: ConversionReport to serialize
            indent: JSON indentation level
            
        Returns:
            JSON string representation
        """
        data = {
            "timestamp": report.timestamp.isoformat(),
            "success": report.success,
            "source_type": report.source_type,
            "target_type": report.target_type,
            "source_version": report.source_version,
            "target_version": report.target_version,
            "error_count": report.error_count,
            "warning_count": report.warning_count,
            "info_count": report.info_count,
            "duration_seconds": report.duration_seconds,
            "compliance_issues": [
                {
                    "level": issue.level.value,
                    "code": issue.code,
                    "message": issue.message,
                    "element_type": issue.element_type,
                    "element_name": issue.element_name,
                    "suggestion": issue.suggestion,
                    "conversion_impact": issue.conversion_impact.value if issue.conversion_impact else None,
                }
                for issue in report.compliance_issues
            ],
            "conversion_warnings": [
                {
                    "code": w.code,
                    "message": w.message,
                    "source_element": w.source_element,
                    "target_element": w.target_element,
                    "resolution": w.resolution,
                }
                for w in report.conversion_warnings
            ],
            "statistics": report.statistics,
        }
        return json.dumps(data, indent=indent, default=str)
    
    def to_markdown(self, report: ConversionReport) -> str:
        """
        Convert report to Markdown format.
        
        Args:
            report: ConversionReport to format
            
        Returns:
            Markdown string representation
        """
        lines = [
            "# Ontology Conversion Report",
            "",
            f"**Generated:** {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "## Summary",
            "",
            f"- **Status:** {'✅ Success' if report.success else '❌ Failed'}",
            f"- **Source:** {report.source_type} ({report.source_version})",
            f"- **Target:** {report.target_type} ({report.target_version})",
            "",
            "### Issue Counts",
            "",
            f"| Level | Count |",
            f"|-------|-------|",
            f"| 🔴 Error | {report.error_count} |",
            f"| 🟡 Warning | {report.warning_count} |",
            f"| ℹ️ Info | {report.info_count} |",
            "",
        ]
        
        if report.duration_seconds is not None:
            lines.extend([
                f"**Duration:** {report.duration_seconds:.2f}s",
                "",
            ])
        
        # Issues section
        if report.compliance_issues:
            lines.extend([
                "## Compliance Issues",
                "",
            ])
            
            # Group by level
            errors = [i for i in report.compliance_issues if i.level == ComplianceLevel.ERROR]
            warnings = [i for i in report.compliance_issues if i.level == ComplianceLevel.WARNING]
            infos = [i for i in report.compliance_issues if i.level == ComplianceLevel.INFO]
            
            if errors:
                lines.extend([
                    "### Errors",
                    "",
                ])
                for issue in errors:
                    lines.append(f"- **[{issue.code}]** {issue.message}")
                    if issue.element_name:
                        lines.append(f"  - Element: `{issue.element_name}` ({issue.element_type})")
                    if issue.suggestion:
                        lines.append(f"  - Suggestion: {issue.suggestion}")
                lines.append("")
            
            if warnings:
                lines.extend([
                    "### Warnings",
                    "",
                ])
                for issue in warnings:
                    lines.append(f"- **[{issue.code}]** {issue.message}")
                    if issue.element_name:
                        lines.append(f"  - Element: `{issue.element_name}` ({issue.element_type})")
                    if issue.suggestion:
                        lines.append(f"  - Suggestion: {issue.suggestion}")
                lines.append("")
            
            if infos:
                lines.extend([
                    "### Information",
                    "",
                ])
                for issue in infos:
                    lines.append(f"- **[{issue.code}]** {issue.message}")
                lines.append("")
        
        # Conversion warnings section
        if report.conversion_warnings:
            lines.extend([
                "## Conversion Warnings",
                "",
            ])
            for warning in report.conversion_warnings:
                lines.append(f"- **[{warning.code}]** {warning.message}")
                if warning.source_element:
                    lines.append(f"  - Source: `{warning.source_element}`")
                if warning.target_element:
                    lines.append(f"  - Target: `{warning.target_element}`")
                if warning.resolution:
                    lines.append(f"  - Resolution: {warning.resolution}")
            lines.append("")
        
        # Statistics section
        if report.statistics:
            lines.extend([
                "## Statistics",
                "",
            ])
            if "source" in report.statistics:
                lines.append("### Source Statistics")
                lines.append("")
                for key, value in report.statistics["source"].items():
                    lines.append(f"- {key}: {value}")
                lines.append("")
            
            if "target" in report.statistics:
                lines.append("### Target Statistics")
                lines.append("")
                for key, value in report.statistics["target"].items():
                    lines.append(f"- {key}: {value}")
                lines.append("")
        
        return "\n".join(lines)


# Convenience functions

def validate_dtdl_for_fabric(
    interfaces: List[Any],
    version: Optional[DTDLVersion] = None,
    strict: bool = False,
) -> ConversionReport:
    """
    Validate DTDL interfaces for Fabric upload.
    
    Args:
        interfaces: List of DTDLInterface objects
        version: Expected DTDL version
        strict: If True, treat warnings as errors
        
    Returns:
        ConversionReport with validation results
    """
    from .dtdl_compliance import DTDLComplianceValidator
    from .fabric_compliance import FabricComplianceChecker
    
    dtdl_validator = DTDLComplianceValidator(strict=strict)
    fabric_checker = FabricComplianceChecker(strict=strict)
    
    dtdl_result = dtdl_validator.validate(interfaces, version)
    fabric_result = fabric_checker.check_dtdl(interfaces)
    
    generator = ConversionReportGenerator()
    return generator.generate_report(dtdl_result, fabric_result)


def validate_rdf_for_conversion(
    graph: "Graph",
    target_version: DTDLVersion = DTDLVersion.V3,
    strict: bool = False,
) -> ConversionReport:
    """
    Validate RDF/OWL graph for DTDL conversion.
    
    Args:
        graph: RDFLib Graph
        target_version: Target DTDL version
        strict: If True, treat warnings as errors
        
    Returns:
        ConversionReport with validation results
    """
    from .rdf_compliance import RDFOWLComplianceValidator
    from .fabric_compliance import FabricComplianceChecker
    
    rdf_validator = RDFOWLComplianceValidator(
        target_version=target_version,
        strict=strict
    )
    fabric_checker = FabricComplianceChecker(strict=strict)
    
    rdf_result = rdf_validator.validate(graph)
    fabric_result = fabric_checker.check_rdf(graph)
    
    generator = ConversionReportGenerator()
    return generator.generate_report(rdf_result, fabric_result)
