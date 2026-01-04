"""
Shared data models for Fabric Ontology converters.

This module contains the core data classes used by both RDF and DTDL converters
to represent Fabric Ontology entities, relationships, and conversion results.

Usage:
    from models import EntityType, RelationshipType, ConversionResult
    
    # Or import specific classes
    from models.fabric_types import EntityType, EntityTypeProperty
    from models.conversion import ConversionResult, SkippedItem
    
    # For the converter protocol (also available from plugins.protocols)
    from models.base import ConverterProtocol, BaseConverter
"""

from .fabric_types import (
    EntityType,
    EntityTypeProperty,
    RelationshipType,
    RelationshipEnd,
)
from .conversion import (
    ConversionResult,
    SkippedItem,
)
from .base import (
    ConverterProtocol,
    BaseConverter,
)

__all__ = [
    # Fabric entity types
    "EntityType",
    "EntityTypeProperty",
    "RelationshipType",
    "RelationshipEnd",
    # Conversion results
    "ConversionResult",
    "SkippedItem",
    # Converter protocol and base class
    "ConverterProtocol",
    "BaseConverter",
]
