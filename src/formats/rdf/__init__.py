"""
RDF package - RDF to Fabric conversion components.

This package contains modular components for converting RDF/OWL ontologies
to Microsoft Fabric Ontology format.

Components:
- rdf_converter: Main converter class and high-level functions
- streaming_converter: Memory-efficient streaming converter for large files
- preflight_validator: Pre-conversion validation for RDF/OWL files
- fabric_to_ttl: Export Fabric ontology back to TTL format
- type_mapper: XSD to Fabric type mapping
- uri_utils: URI parsing and name extraction  
- class_resolver: OWL class/union resolution
- fabric_serializer: Fabric API JSON serialization
- rdf_parser: TTL parsing with memory management
- property_extractor: Class/property extraction from RDF graphs
"""

from .type_mapper import TypeMapper, XSD_TO_FABRIC_TYPE
from .uri_utils import URIUtils
from .class_resolver import ClassResolver
from .fabric_serializer import FabricSerializer
from .rdf_parser import MemoryManager, RDFGraphParser
from .property_extractor import (
    ClassExtractor,
    DataPropertyExtractor,
    ObjectPropertyExtractor,
    EntityIdentifierSetter,
)
from .streaming_converter import StreamingRDFConverter
from .rdf_converter import (
    RDFToFabricConverter,
    FabricDefinitionValidator,
    DefinitionValidationError,
    InputValidator,
    parse_ttl_file,
    parse_ttl_content,
    parse_ttl_file_with_result,
    parse_ttl_with_result,
    parse_ttl_streaming,
    convert_to_fabric_definition,
    # Re-export models for convenience
    EntityType,
    EntityTypeProperty,
    RelationshipType,
    RelationshipEnd,
    ConversionResult,
    SkippedItem,
)
from .preflight_validator import (
    PreflightValidator,
    ValidationReport,
    ValidationIssue,
    IssueSeverity,
    IssueCategory,
    validate_ttl_file,
    validate_ttl_content,
    generate_import_log,
)
from .fabric_to_ttl import (
    FabricToTTLConverter,
    FABRIC_TO_XSD_TYPE,
    compare_ontologies,
    round_trip_test,
    export_ontology_to_ttl,
)

__all__ = [
    # Main converter
    'RDFToFabricConverter',
    'StreamingRDFConverter',
    'FabricDefinitionValidator',
    'DefinitionValidationError',
    'InputValidator',
    # High-level functions
    'parse_ttl_file',
    'parse_ttl_content',
    'parse_ttl_file_with_result',
    'parse_ttl_with_result',
    'parse_ttl_streaming',
    'convert_to_fabric_definition',
    # Validation
    'PreflightValidator',
    'ValidationReport',
    'ValidationIssue',
    'IssueSeverity',
    'IssueCategory',
    'validate_ttl_file',
    'validate_ttl_content',
    'generate_import_log',
    # Export to TTL
    'FabricToTTLConverter',
    'FABRIC_TO_XSD_TYPE',
    'compare_ontologies',
    'round_trip_test',
    'export_ontology_to_ttl',
    # Models
    'EntityType',
    'EntityTypeProperty',
    'RelationshipType',
    'RelationshipEnd',
    'ConversionResult',
    'SkippedItem',
    # Helper components
    'TypeMapper',
    'XSD_TO_FABRIC_TYPE', 
    'URIUtils',
    'ClassResolver',
    'FabricSerializer',
    'MemoryManager',
    'RDFGraphParser',
    'ClassExtractor',
    'DataPropertyExtractor',
    'ObjectPropertyExtractor',
    'EntityIdentifierSetter',
]
