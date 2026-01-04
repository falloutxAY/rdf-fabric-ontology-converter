"""
Compliance validation and conversion warning system for DTDL, RDF/OWL, and Fabric IQ Ontology.

This module provides comprehensive compliance validation to:
1. Validate DTDL documents against v2/v3/v4 specifications
2. Validate RDF/OWL documents against OWL 2 and RDFS specifications
3. Detect and warn about information loss during Fabric IQ Ontology conversion
4. Generate detailed conversion reports

The compliance system helps users understand:
- What features are fully preserved in conversion
- What features are converted with limitations
- What information is lost and cannot be represented

Usage:
    from core.compliance import (
        DTDLComplianceValidator,
        RDFOWLComplianceValidator,
        FabricComplianceChecker,
        ConversionReport,
        ConversionReportGenerator,
    )
    
    # Validate DTDL compliance
    dtdl_validator = DTDLComplianceValidator()
    result = dtdl_validator.validate(interfaces)
    
    # Validate RDF/OWL compliance
    rdf_validator = RDFOWLComplianceValidator()
    result = rdf_validator.validate(graph)
    
    # Generate conversion report
    report_gen = ConversionReportGenerator()
    report = report_gen.generate_report(source_result, target_result)

Module Structure (refactored for maintainability):
- models.py: Data models (enums, dataclasses)
- constants.py: Version-specific limits and feature support tables
- dtdl_compliance.py: DTDL validation logic
- rdf_compliance.py: RDF/OWL validation logic
- fabric_compliance.py: Fabric API compliance checking
- report_generator.py: Report generation and formatting
"""

# Models - Enums and dataclasses
from .models import (
    ComplianceLevel,
    ConversionImpact,
    DTDLVersion,
    ComplianceIssue,
    ConversionWarning,
    ComplianceResult,
    ConversionReport,
)

# Constants - Limits and feature support tables
from .constants import (
    DTDL_LIMITS,
    OWL_CONSTRUCT_SUPPORT,
    DTDL_FEATURE_SUPPORT,
)

# Validators
from .dtdl_compliance import DTDLComplianceValidator
from .rdf_compliance import RDFOWLComplianceValidator
from .fabric_compliance import FabricComplianceChecker, FABRIC_LIMITS

# Report generation
from .report_generator import (
    ConversionReportGenerator,
    validate_dtdl_for_fabric,
    validate_rdf_for_conversion,
)

__all__ = [
    # Enums
    "ComplianceLevel",
    "ConversionImpact",
    "DTDLVersion",
    # Data classes
    "ComplianceIssue",
    "ConversionWarning",
    "ComplianceResult",
    "ConversionReport",
    # Constants
    "DTDL_LIMITS",
    "OWL_CONSTRUCT_SUPPORT",
    "DTDL_FEATURE_SUPPORT",
    "FABRIC_LIMITS",
    # Validators
    "DTDLComplianceValidator",
    "RDFOWLComplianceValidator",
    "FabricComplianceChecker",
    # Report generation
    "ConversionReportGenerator",
    # Convenience functions
    "validate_dtdl_for_fabric",
    "validate_rdf_for_conversion",
]
