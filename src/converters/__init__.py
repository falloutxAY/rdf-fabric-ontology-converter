"""
Converters package - Refactored RDF to Fabric conversion components.

This package contains modular components extracted from the original
RDFToFabricConverter God class for better maintainability and testability.

Components:
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

__all__ = [
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
