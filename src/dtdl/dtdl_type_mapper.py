"""
DTDL Type Mapper

Provides comprehensive type mapping from DTDL schemas to Fabric value types,
including handling of complex types, semantic types, and unit information.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Union

from .dtdl_models import (
    DTDLPrimitiveSchema,
    DTDLEnum,
    DTDLObject,
    DTDLArray,
    DTDLMap,
    DTDLField,
    DTDLScaledDecimal,
)


class FabricValueType(str, Enum):
    """Supported Fabric ontology value types."""
    STRING = "String"
    BIG_INT = "BigInt"
    DOUBLE = "Double"
    BOOLEAN = "Boolean"
    DATE_TIME = "DateTime"


@dataclass
class TypeMappingResult:
    """Result of a type mapping operation."""
    fabric_type: FabricValueType
    is_complex: bool = False
    is_array: bool = False
    semantic_type: Optional[str] = None
    unit: Optional[str] = None
    original_schema: Optional[str] = None
    json_schema: Optional[Dict[str, Any]] = None


# Primitive type mapping
PRIMITIVE_TYPE_MAP: Dict[str, FabricValueType] = {
    # Boolean
    "boolean": FabricValueType.BOOLEAN,
    
    # Integers
    "byte": FabricValueType.BIG_INT,
    "short": FabricValueType.BIG_INT,
    "integer": FabricValueType.BIG_INT,
    "long": FabricValueType.BIG_INT,
    "unsignedByte": FabricValueType.BIG_INT,
    "unsignedShort": FabricValueType.BIG_INT,
    "unsignedInteger": FabricValueType.BIG_INT,
    "unsignedLong": FabricValueType.BIG_INT,
    
    # Floats
    "float": FabricValueType.DOUBLE,
    "double": FabricValueType.DOUBLE,
    "decimal": FabricValueType.DOUBLE,
    
    # Scaled Decimal (DTDL v4) - stored as JSON object with scale and value
    "scaledDecimal": FabricValueType.STRING,
    
    # Strings
    "string": FabricValueType.STRING,
    "uuid": FabricValueType.STRING,
    "bytes": FabricValueType.STRING,
    
    # Date/Time
    "date": FabricValueType.DATE_TIME,
    "dateTime": FabricValueType.DATE_TIME,
    "time": FabricValueType.STRING,  # No native time type
    "duration": FabricValueType.STRING,
    
    # Geospatial (stored as GeoJSON strings)
    "point": FabricValueType.STRING,
    "lineString": FabricValueType.STRING,
    "polygon": FabricValueType.STRING,
    "multiPoint": FabricValueType.STRING,
    "multiLineString": FabricValueType.STRING,
    "multiPolygon": FabricValueType.STRING,
}


# DTDL v4 Semantic Types with their associated schemas
SEMANTIC_TYPE_SCHEMAS: Dict[str, List[str]] = {
    # Temperature semantic type
    "Temperature": ["double"],
    
    # Length semantic type
    "Length": ["double"],
    "Distance": ["double"],
    
    # Velocity semantic type
    "Velocity": ["double"],
    "Speed": ["double"],
    
    # Pressure semantic type
    "Pressure": ["double"],
    
    # Mass semantic type
    "Mass": ["double"],
    "Weight": ["double"],
    
    # Energy semantic type
    "Energy": ["double"],
    "Power": ["double"],
    
    # Electrical semantic types
    "Voltage": ["double"],
    "Current": ["double"],
    "Resistance": ["double"],
    "Capacitance": ["double"],
    "Frequency": ["double"],
    
    # Other common types
    "Humidity": ["double"],
    "Illuminance": ["double"],
    "Luminance": ["double"],
    "Angle": ["double"],
    "Area": ["double"],
    "Volume": ["double"],
    "TimeSpan": ["duration"],
    "Percentage": ["double"],
    "Ratio": ["double"],
    "Concentration": ["double"],
}


class DTDLTypeMapper:
    """
    Maps DTDL schemas to Fabric value types.
    
    Handles:
    - Primitive types
    - Complex types (Array, Map, Object, Enum)
    - Semantic types (Temperature, Velocity, etc.)
    - Unit information preservation
    
    Example usage:
        mapper = DTDLTypeMapper()
        result = mapper.map_schema("double")
        # result.fabric_type == FabricValueType.DOUBLE
        
        result = mapper.map_schema(DTDLArray(element_schema="integer"))
        # result.fabric_type == FabricValueType.STRING  (JSON encoded)
        # result.is_array == True
    """
    
    def __init__(self, preserve_complex_as_json: bool = True):
        """
        Initialize the type mapper.
        
        Args:
            preserve_complex_as_json: If True, complex types become JSON strings.
                                      If False, use best approximation.
        """
        self.preserve_complex_as_json = preserve_complex_as_json
    
    def map_schema(
        self,
        schema: Union[str, DTDLEnum, DTDLObject, DTDLArray, DTDLMap, DTDLScaledDecimal, Any],
        semantic_type: Optional[str] = None,
        unit: Optional[str] = None
    ) -> TypeMappingResult:
        """
        Map a DTDL schema to a Fabric value type.
        
        Args:
            schema: The DTDL schema to map
            semantic_type: Optional semantic type (e.g., "Temperature")
            unit: Optional unit annotation (e.g., "degreeCelsius")
            
        Returns:
            TypeMappingResult with mapping details
        """
        if isinstance(schema, str):
            return self._map_primitive(schema, semantic_type, unit)
        
        if isinstance(schema, DTDLEnum):
            return self._map_enum(schema, semantic_type)
        
        if isinstance(schema, DTDLArray):
            return self._map_array(schema, semantic_type)
        
        if isinstance(schema, DTDLMap):
            return self._map_map(schema)
        
        if isinstance(schema, DTDLObject):
            return self._map_object(schema)
        
        if isinstance(schema, DTDLScaledDecimal):
            return self._map_scaled_decimal(schema, semantic_type, unit)
        
        # Unknown schema type - default to string
        return TypeMappingResult(
            fabric_type=FabricValueType.STRING,
            is_complex=True,
            original_schema=str(type(schema).__name__),
        )
    
    def _map_primitive(
        self,
        schema: str,
        semantic_type: Optional[str],
        unit: Optional[str]
    ) -> TypeMappingResult:
        """Map a primitive DTDL schema to Fabric type."""
        fabric_type = PRIMITIVE_TYPE_MAP.get(schema, FabricValueType.STRING)
        
        return TypeMappingResult(
            fabric_type=fabric_type,
            is_complex=False,
            is_array=False,
            semantic_type=semantic_type,
            unit=unit,
            original_schema=schema,
        )
    
    def _map_enum(
        self,
        enum: DTDLEnum,
        semantic_type: Optional[str]
    ) -> TypeMappingResult:
        """Map a DTDL Enum to Fabric type."""
        # Use the enum's value schema for the Fabric type
        base_type = PRIMITIVE_TYPE_MAP.get(
            enum.value_schema,
            FabricValueType.STRING
        )
        
        # Generate JSON schema for documentation
        json_schema = {
            "type": "enum",
            "valueSchema": enum.value_schema,
            "values": [
                {"name": ev.name, "value": ev.value}
                for ev in enum.enum_values
            ]
        }
        
        return TypeMappingResult(
            fabric_type=base_type,
            is_complex=True,
            semantic_type=semantic_type,
            original_schema="Enum",
            json_schema=json_schema,
        )
    
    def _map_array(
        self,
        array: DTDLArray,
        semantic_type: Optional[str]
    ) -> TypeMappingResult:
        """Map a DTDL Array to Fabric type."""
        # Arrays are stored as JSON strings in Fabric
        element_schema = array.element_schema
        
        # Get element type for documentation
        if isinstance(element_schema, str):
            element_type = element_schema
        else:
            element_type = type(element_schema).__name__
        
        json_schema = {
            "type": "array",
            "elementSchema": element_type
        }
        
        return TypeMappingResult(
            fabric_type=FabricValueType.STRING,
            is_complex=True,
            is_array=True,
            semantic_type=semantic_type,
            original_schema="Array",
            json_schema=json_schema,
        )
    
    def _map_map(self, map_schema: DTDLMap) -> TypeMappingResult:
        """Map a DTDL Map to Fabric type."""
        json_schema = {
            "type": "map",
            "mapKey": {
                "name": map_schema.map_key.name if map_schema.map_key else "key",
                "schema": map_schema.map_key.schema if map_schema.map_key else "string"
            },
            "mapValue": {
                "name": map_schema.map_value.name if map_schema.map_value else "value",
                "schema": (
                    map_schema.map_value.schema
                    if map_schema.map_value and isinstance(map_schema.map_value.schema, str)
                    else "object"
                )
            }
        }
        
        return TypeMappingResult(
            fabric_type=FabricValueType.STRING,
            is_complex=True,
            original_schema="Map",
            json_schema=json_schema,
        )
    
    def _map_object(self, obj: DTDLObject) -> TypeMappingResult:
        """Map a DTDL Object to Fabric type."""
        json_schema = {
            "type": "object",
            "fields": [
                {
                    "name": field.name,
                    "schema": (
                        field.schema
                        if isinstance(field.schema, str)
                        else type(field.schema).__name__
                    )
                }
                for field in obj.fields
            ]
        }
        
        return TypeMappingResult(
            fabric_type=FabricValueType.STRING,
            is_complex=True,
            original_schema="Object",
            json_schema=json_schema,
        )
    
    def _map_scaled_decimal(
        self,
        scaled_decimal: DTDLScaledDecimal,
        semantic_type: Optional[str] = None,
        unit: Optional[str] = None
    ) -> TypeMappingResult:
        """
        Map a DTDL v4 ScaledDecimal to Fabric type.
        
        ScaledDecimal is stored as a JSON object with 'scale' and 'value' fields,
        so it maps to String in Fabric (JSON encoded).
        
        Args:
            scaled_decimal: The ScaledDecimal schema
            semantic_type: Optional semantic type annotation
            unit: Optional unit annotation
            
        Returns:
            TypeMappingResult with mapping details
        """
        json_schema = DTDLScaledDecimal.get_json_schema()
        
        return TypeMappingResult(
            fabric_type=FabricValueType.STRING,
            is_complex=True,
            semantic_type=semantic_type,
            unit=unit,
            original_schema="scaledDecimal",
            json_schema=json_schema,
        )
    
    def generate_documentation(
        self,
        mappings: List[TypeMappingResult]
    ) -> str:
        """
        Generate documentation for type mappings.
        
        Args:
            mappings: List of type mapping results
            
        Returns:
            Markdown documentation string
        """
        lines = ["# Type Mapping Documentation\n"]
        lines.append("| Original Schema | Fabric Type | Complex | Notes |")
        lines.append("|-----------------|-------------|---------|-------|")
        
        for mapping in mappings:
            notes = []
            if mapping.semantic_type:
                notes.append(f"Semantic: {mapping.semantic_type}")
            if mapping.unit:
                notes.append(f"Unit: {mapping.unit}")
            if mapping.is_array:
                notes.append("Array (JSON encoded)")
            
            lines.append(
                f"| {mapping.original_schema or 'unknown'} "
                f"| {mapping.fabric_type.value} "
                f"| {'Yes' if mapping.is_complex else 'No'} "
                f"| {', '.join(notes) or '-'} |"
            )
        
        return "\n".join(lines)


def flatten_object_fields(obj: DTDLObject, prefix: str = "") -> List[Dict[str, Any]]:
    """
    Flatten a DTDL Object into a list of property definitions.
    
    Useful when converting Object types to individual Fabric properties
    instead of JSON strings.
    
    Args:
        obj: The DTDL Object to flatten
        prefix: Optional prefix for field names
        
    Returns:
        List of property definitions with name and fabric_type
    """
    mapper = DTDLTypeMapper()
    properties = []
    
    for field in obj.fields:
        field_name = f"{prefix}_{field.name}" if prefix else field.name
        mapping = mapper.map_schema(field.schema)
        
        properties.append({
            "name": field_name,
            "fabric_type": mapping.fabric_type.value,
            "original_schema": mapping.original_schema,
        })
    
    return properties


def get_semantic_type_info(semantic_type: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a DTDL semantic type.
    
    Args:
        semantic_type: Name of the semantic type
        
    Returns:
        Dictionary with schema info, or None if unknown
    """
    schemas = SEMANTIC_TYPE_SCHEMAS.get(semantic_type)
    if not schemas:
        return None
    
    return {
        "name": semantic_type,
        "allowed_schemas": schemas,
        "recommended_fabric_type": FabricValueType.DOUBLE.value,
    }
