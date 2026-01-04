"""
CDM Type Mapper.

This module provides type mapping functionality between CDM (Common Data Model)
data types and Microsoft Fabric Ontology value types.

CDM supports various data types:
- Primitive types: string, integer, double, boolean, dateTime, etc.
- Semantic types: name, email, phone, url, currency, etc.
- Complex types: entity references, arrays, objects

Fabric Ontology supports a limited set of value types:
- String, Boolean, DateTime, BigInt, Double, Decimal

Usage:
    from formats.cdm.cdm_type_mapper import CDMTypeMapper, FabricValueType
    
    mapper = CDMTypeMapper()
    result = mapper.map_type("integer")
    print(result.fabric_type)  # FabricValueType.BIGINT
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FabricValueType(Enum):
    """
    Fabric Ontology value types.
    
    These are the data types supported by Microsoft Fabric Ontology API
    for entity type properties.
    """
    STRING = "String"
    BOOLEAN = "Boolean"
    DATETIME = "DateTime"
    BIGINT = "BigInt"
    DOUBLE = "Double"
    DECIMAL = "Decimal"


# =============================================================================
# CDM Primitive Type Mappings
# =============================================================================

CDM_TYPE_MAPPINGS: Dict[str, str] = {
    # String types
    "string": "String",
    "char": "String",
    "text": "String",
    
    # Integer types
    "integer": "BigInt",
    "int": "BigInt",
    "int64": "BigInt",
    "int32": "BigInt",
    "int16": "BigInt",
    "smallInteger": "BigInt",
    "bigInteger": "BigInt",
    "byte": "BigInt",
    "tinyInteger": "BigInt",
    
    # Floating point types
    "float": "Double",
    "double": "Double",
    "real": "Double",
    
    # Decimal types
    "decimal": "Decimal",
    "numeric": "Decimal",
    "money": "Decimal",
    "smallMoney": "Decimal",
    
    # Boolean types
    "boolean": "Boolean",
    "bool": "Boolean",
    
    # Date/time types
    "date": "DateTime",
    "dateTime": "DateTime",
    "dateTimeOffset": "DateTime",
    "time": "DateTime",
    "timestamp": "DateTime",
    
    # GUID/UUID types
    "GUID": "String",
    "guid": "String",
    "uuid": "String",
    "uniqueidentifier": "String",
    
    # Binary types (stored as base64 string)
    "binary": "String",
    "varbinary": "String",
    "image": "String",
    
    # JSON/object types (stored as serialized string)
    "JSON": "String",
    "json": "String",
    "object": "String",
    "variant": "String",
}


# =============================================================================
# CDM Semantic Type Mappings
# =============================================================================

CDM_SEMANTIC_TYPE_MAPPINGS: Dict[str, str] = {
    # Identity types
    "name": "String",
    "fullName": "String",
    "firstName": "String",
    "lastName": "String",
    "middleName": "String",
    
    # Contact types
    "email": "String",
    "phone": "String",
    "phoneNumber": "String",
    "fax": "String",
    
    # Internet types
    "url": "String",
    "uri": "String",
    "webAddress": "String",
    "ipAddress": "String",
    "ipV4Address": "String",
    "ipV6Address": "String",
    
    # Address types
    "address": "String",
    "city": "String",
    "stateOrProvince": "String",
    "country": "String",
    "postalCode": "String",
    "county": "String",
    "latitude": "Double",
    "longitude": "Double",
    
    # Localization types
    "languageTag": "String",
    "locale": "String",
    "cultureTag": "String",
    "timezone": "String",
    
    # Date component types
    "year": "BigInt",
    "month": "BigInt",
    "day": "BigInt",
    "week": "BigInt",
    "quarter": "BigInt",
    "fiscalYear": "BigInt",
    "fiscalMonth": "BigInt",
    "fiscalQuarter": "BigInt",
    
    # Measurement types
    "age": "BigInt",
    "duration": "BigInt",
    "distance": "Double",
    "weight": "Double",
    "height": "Double",
    "area": "Double",
    "volume": "Double",
    "temperature": "Double",
    "percentage": "Double",
    "probability": "Double",
    
    # Financial types
    "currency": "Decimal",
    "currencyCode": "String",
    "baseCurrency": "Decimal",
    "exchangeRate": "Decimal",
    "amount": "Decimal",
    "price": "Decimal",
    "tax": "Decimal",
    "discount": "Decimal",
    
    # Count types
    "count": "BigInt",
    "quantity": "BigInt",
    "sequence": "BigInt",
    "ordinal": "BigInt",
    
    # Status types
    "statusCode": "BigInt",
    "stateCode": "BigInt",
    "versionNumber": "BigInt",
    
    # Color types
    "colorName": "String",
    "colorValue": "String",
    
    # File types
    "fileName": "String",
    "filePath": "String",
    "mimeType": "String",
    "fileSize": "BigInt",
    
    # Code/identifier types
    "code": "String",
    "tickerSymbol": "String",
    "accountCode": "String",
    "productCode": "String",
    "transactionCode": "String",
    "referenceCode": "String",
}


# =============================================================================
# Unsupported Type Handling
# =============================================================================

# Types that should be expanded (attribute groups)
CDM_EXPAND_TYPES = {
    "attributeGroup",
}

# Types that represent entity references (convert to relationships)
CDM_ENTITY_REFERENCE_TYPES = {
    "entity",
    "entityId",
    "entityName",
}

# Default type when mapping fails
DEFAULT_FABRIC_TYPE = "String"


@dataclass
class TypeMappingResult:
    """
    Result of CDM to Fabric type mapping.
    
    Attributes:
        fabric_type: The mapped Fabric value type.
        original_type: The original CDM type.
        is_exact_match: Whether this was an exact type match.
        is_semantic_type: Whether the original was a semantic type.
        warning: Warning message if mapping was approximate.
        requires_expansion: Whether the type needs to be expanded.
        is_entity_reference: Whether this represents an entity reference.
    """
    fabric_type: FabricValueType
    original_type: str
    is_exact_match: bool = True
    is_semantic_type: bool = False
    warning: Optional[str] = None
    requires_expansion: bool = False
    is_entity_reference: bool = False


class CDMTypeMapper:
    """
    Maps CDM data types to Fabric Ontology value types.
    
    Handles:
    - Primitive types (string, integer, boolean, etc.)
    - Semantic types (email, phone, currency, etc.)
    - Complex types (with warnings)
    - Trait-based type inference
    
    Example:
        >>> mapper = CDMTypeMapper()
        >>> result = mapper.map_type("integer")
        >>> print(result.fabric_type)
        FabricValueType.BIGINT
        
        >>> result = mapper.map_type("email")
        >>> print(result.is_semantic_type)
        True
    """
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize the type mapper.
        
        Args:
            strict_mode: If True, raise errors for unknown types
                        instead of defaulting to String.
        """
        self.strict_mode = strict_mode
        self._primitive_mappings = CDM_TYPE_MAPPINGS.copy()
        self._semantic_mappings = CDM_SEMANTIC_TYPE_MAPPINGS.copy()
    
    def map_type(
        self, 
        cdm_type: str,
        traits: Optional[List[str]] = None
    ) -> TypeMappingResult:
        """
        Map a CDM type to Fabric value type.
        
        Args:
            cdm_type: CDM data type name.
            traits: Optional list of trait names for type inference.
            
        Returns:
            TypeMappingResult with mapping details.
            
        Raises:
            ValueError: In strict mode when type is unknown.
        """
        cdm_type_lower = cdm_type.lower()
        
        # Check for entity reference types
        if cdm_type_lower in CDM_ENTITY_REFERENCE_TYPES:
            return TypeMappingResult(
                fabric_type=FabricValueType.STRING,
                original_type=cdm_type,
                is_exact_match=False,
                is_entity_reference=True,
                warning=f"Entity reference type '{cdm_type}' should be modeled as relationship"
            )
        
        # Check for types requiring expansion
        if cdm_type_lower in CDM_EXPAND_TYPES:
            return TypeMappingResult(
                fabric_type=FabricValueType.STRING,
                original_type=cdm_type,
                is_exact_match=False,
                requires_expansion=True,
                warning=f"Type '{cdm_type}' requires expansion"
            )
        
        # Try primitive type mapping (case-insensitive)
        for key, value in self._primitive_mappings.items():
            if key.lower() == cdm_type_lower:
                return TypeMappingResult(
                    fabric_type=FabricValueType(value),
                    original_type=cdm_type,
                    is_exact_match=True
                )
        
        # Try semantic type mapping (case-insensitive)
        for key, value in self._semantic_mappings.items():
            if key.lower() == cdm_type_lower:
                return TypeMappingResult(
                    fabric_type=FabricValueType(value),
                    original_type=cdm_type,
                    is_exact_match=True,
                    is_semantic_type=True
                )
        
        # Try trait-based inference
        if traits:
            inferred = self._infer_from_traits(traits)
            if inferred:
                return TypeMappingResult(
                    fabric_type=inferred,
                    original_type=cdm_type,
                    is_exact_match=False,
                    warning=f"Type inferred from traits for '{cdm_type}'"
                )
        
        # Handle unknown types
        if self.strict_mode:
            raise ValueError(f"Unknown CDM type: {cdm_type}")
        
        logger.warning(f"Unknown CDM type '{cdm_type}', defaulting to String")
        return TypeMappingResult(
            fabric_type=FabricValueType.STRING,
            original_type=cdm_type,
            is_exact_match=False,
            warning=f"Unknown type '{cdm_type}' defaulted to String"
        )
    
    def _infer_from_traits(self, traits: List[str]) -> Optional[FabricValueType]:
        """
        Infer Fabric type from CDM traits.
        
        Args:
            traits: List of trait references.
            
        Returns:
            Inferred FabricValueType or None.
        """
        trait_type_map = {
            "is.dataFormat.integer": FabricValueType.BIGINT,
            "is.dataFormat.big": FabricValueType.BIGINT,
            "is.dataFormat.small": FabricValueType.BIGINT,
            "is.dataFormat.floatingPoint": FabricValueType.DOUBLE,
            "is.dataFormat.numeric.shaped": FabricValueType.DECIMAL,
            "is.dataFormat.boolean": FabricValueType.BOOLEAN,
            "is.dataFormat.date": FabricValueType.DATETIME,
            "is.dataFormat.time": FabricValueType.DATETIME,
            "is.dataFormat.timeOffset": FabricValueType.DATETIME,
            "is.dataFormat.character": FabricValueType.STRING,
            "is.dataFormat.array": FabricValueType.STRING,
            "is.dataFormat.guid": FabricValueType.STRING,
            "is.dataFormat.byte": FabricValueType.BIGINT,
        }
        
        for trait in traits:
            if trait in trait_type_map:
                return trait_type_map[trait]
        
        return None
    
    def get_all_mappings(self) -> Dict[str, str]:
        """
        Get all type mappings (primitive + semantic).
        
        Returns:
            Dictionary of CDM type to Fabric type string mappings.
        """
        all_mappings = self._primitive_mappings.copy()
        all_mappings.update(self._semantic_mappings)
        return all_mappings
    
    def is_supported_type(self, cdm_type: str) -> bool:
        """
        Check if a CDM type is supported.
        
        Args:
            cdm_type: CDM type name to check.
            
        Returns:
            True if type has a known mapping.
        """
        cdm_type_lower = cdm_type.lower()
        
        for key in self._primitive_mappings:
            if key.lower() == cdm_type_lower:
                return True
        
        for key in self._semantic_mappings:
            if key.lower() == cdm_type_lower:
                return True
        
        return False
    
    def get_supported_types(self) -> Tuple[List[str], List[str]]:
        """
        Get lists of supported primitive and semantic types.
        
        Returns:
            Tuple of (primitive_types, semantic_types).
        """
        return (
            list(self._primitive_mappings.keys()),
            list(self._semantic_mappings.keys())
        )
