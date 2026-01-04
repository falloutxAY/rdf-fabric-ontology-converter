"""
DTDL (Digital Twins Definition Language) Import Module

This module provides functionality to parse DTDL JSON/JSON-LD files and convert them
to Microsoft Fabric Ontology API format.

Key Components:
- dtdl_parser: Parse DTDL files (single, array, directory)
- dtdl_validator: Validate DTDL structure and references
- dtdl_converter: Convert DTDL to Fabric Ontology format
- mode_converters: Specialized converters for Components, Commands, ScaledDecimal

Usage:
    from dtdl import DTDLParser, DTDLValidator, DTDLToFabricConverter
    
    parser = DTDLParser()
    interfaces = parser.parse_file("model.json")
    
    validator = DTDLValidator()
    errors = validator.validate(interfaces)
    
    converter = DTDLToFabricConverter()
    result = converter.convert(interfaces)
"""

from .dtdl_models import (
    DTDLInterface,
    DTDLProperty,
    DTDLTelemetry,
    DTDLRelationship,
    DTDLComponent,
    DTDLCommand,
    DTDLCommandPayload,
    DTDLEnum,
    DTDLEnumValue,
    DTDLObject,
    DTDLArray,
    DTDLMap,
    DTDLContext,
    DTDLScaledDecimal,
    DTDLPrimitiveSchema,
    GEOSPATIAL_SCHEMA_DTMIS,
    SCALED_DECIMAL_SCHEMA_DTMI,
)

from .dtdl_parser import DTDLParser
from .dtdl_validator import DTDLValidator, DTDLValidationError
from .dtdl_converter import (
    DTDLToFabricConverter,
    DTDL_TO_FABRIC_TYPE,
    ComponentMode,
    CommandMode,
    ScaledDecimalMode,
    ScaledDecimalValue,
)
from .mode_converters import (
    ComponentConverter,
    CommandConverter,
    ScaledDecimalConverter,
)
from .dtdl_type_mapper import (
    DTDLTypeMapper,
    TypeMappingResult,
    FabricValueType,
    PRIMITIVE_TYPE_MAP,
    flatten_object_fields,
    get_semantic_type_info,
)

__all__ = [
    # Models
    'DTDLInterface',
    'DTDLProperty',
    'DTDLTelemetry',
    'DTDLRelationship',
    'DTDLComponent',
    'DTDLCommand',
    'DTDLCommandPayload',
    'DTDLEnum',
    'DTDLEnumValue',
    'DTDLObject',
    'DTDLArray',
    'DTDLMap',
    'DTDLContext',
    'DTDLScaledDecimal',
    'DTDLPrimitiveSchema',
    # DTDL v4 Schema DTMIs
    'GEOSPATIAL_SCHEMA_DTMIS',
    'SCALED_DECIMAL_SCHEMA_DTMI',
    # Core classes
    'DTDLParser',
    'DTDLValidator',
    'DTDLValidationError',
    'DTDLToFabricConverter',
    'DTDL_TO_FABRIC_TYPE',
    # Converter mode enums
    'ComponentMode',
    'CommandMode',
    'ScaledDecimalMode',
    'ScaledDecimalValue',
    # Mode-specific converters
    'ComponentConverter',
    'CommandConverter',
    'ScaledDecimalConverter',
    # Type Mapper
    'DTDLTypeMapper',
    'TypeMappingResult',
    'FabricValueType',
    'PRIMITIVE_TYPE_MAP',
    'flatten_object_fields',
    'get_semantic_type_info',
]
