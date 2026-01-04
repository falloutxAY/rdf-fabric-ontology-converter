"""
CDM (Common Data Model) Import Module

This module provides functionality to parse CDM schema files and convert them
to Microsoft Fabric Ontology API format.

CDM is the foundation for:
- Dynamics 365 / Dataverse schemas
- Power Platform CDM folders
- Azure Data Lake CDM folders
- Industry Accelerators (Healthcare, Financial Services, etc.)

Key Components:
- cdm_parser: Parse CDM manifests and entity schemas
- cdm_validator: Validate CDM structure for Fabric compatibility
- cdm_converter: Convert CDM entities to Fabric Ontology format
- cdm_type_mapper: CDM to Fabric type mappings

Supported Document Types:
- *.manifest.cdm.json (entry point)
- *.cdm.json (entity definitions)
- model.json (legacy format)

Usage:
    from formats.cdm import CDMParser, CDMValidator, CDMToFabricConverter
    
    parser = CDMParser()
    manifest = parser.parse_file("model.manifest.cdm.json")
    
    validator = CDMValidator()
    result = validator.validate(manifest)
    
    converter = CDMToFabricConverter()
    conversion_result = converter.convert(manifest)
"""

from .cdm_models import (
    CDMAttribute,
    CDMEntity,
    CDMRelationship,
    CDMManifest,
    CDMTrait,
    CDMTraitArgument,
)

from .cdm_parser import CDMParser

from .cdm_validator import CDMValidator

from .cdm_converter import CDMToFabricConverter

from .cdm_type_mapper import (
    CDMTypeMapper,
    CDM_TYPE_MAPPINGS,
    CDM_SEMANTIC_TYPE_MAPPINGS,
    FabricValueType,
)

__all__ = [
    # Models
    'CDMAttribute',
    'CDMEntity',
    'CDMRelationship',
    'CDMManifest',
    'CDMTrait',
    'CDMTraitArgument',
    # Core classes
    'CDMParser',
    'CDMValidator',
    'CDMToFabricConverter',
    # Type mapping
    'CDMTypeMapper',
    'CDM_TYPE_MAPPINGS',
    'CDM_SEMANTIC_TYPE_MAPPINGS',
    'FabricValueType',
]
