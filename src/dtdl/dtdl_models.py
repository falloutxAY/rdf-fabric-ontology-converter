"""
DTDL Data Models

This module defines the data classes representing DTDL elements.
These classes provide a typed, in-memory representation of parsed DTDL documents.

Based on DTDL v4 specification:
https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v4/DTDL.v4.md
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, Literal
from enum import Enum


# =============================================================================
# DTDL Primitive Schema Types
# =============================================================================

class DTDLPrimitiveSchema(str, Enum):
    """DTDL primitive schema types."""
    BOOLEAN = "boolean"
    BYTE = "byte"
    BYTES = "bytes"
    DATE = "date"
    DATETIME = "dateTime"
    DECIMAL = "decimal"
    DOUBLE = "double"
    DURATION = "duration"
    FLOAT = "float"
    INTEGER = "integer"
    LONG = "long"
    SHORT = "short"
    STRING = "string"
    TIME = "time"
    UNSIGNED_BYTE = "unsignedByte"
    UNSIGNED_INTEGER = "unsignedInteger"
    UNSIGNED_LONG = "unsignedLong"
    UNSIGNED_SHORT = "unsignedShort"
    UUID = "uuid"
    # Geospatial schemas (DTDL v4)
    POINT = "point"
    LINE_STRING = "lineString"
    POLYGON = "polygon"
    MULTI_POINT = "multiPoint"
    MULTI_LINE_STRING = "multiLineString"
    MULTI_POLYGON = "multiPolygon"
    # Scaled Decimal (DTDL v4)
    SCALED_DECIMAL = "scaledDecimal"


# DTDL v4 Geospatial Schema DTMIs
GEOSPATIAL_SCHEMA_DTMIS = {
    "point": "dtmi:standard:schema:geospatial:point;4",
    "lineString": "dtmi:standard:schema:geospatial:lineString;4",
    "polygon": "dtmi:standard:schema:geospatial:polygon;4",
    "multiPoint": "dtmi:standard:schema:geospatial:multiPoint;4",
    "multiLineString": "dtmi:standard:schema:geospatial:multiLineString;4",
    "multiPolygon": "dtmi:standard:schema:geospatial:multiPolygon;4",
}

# DTDL v4 Scaled Decimal Schema DTMI
SCALED_DECIMAL_SCHEMA_DTMI = "dtmi:standard:schema:scaledDecimal;4"


# =============================================================================
# DTDL Context
# =============================================================================

@dataclass
class DTDLContext:
    """
    Represents the @context of a DTDL document.
    
    The context specifies the DTDL version and any language extensions.
    """
    dtdl_version: int  # 2, 3, or 4
    extensions: List[str] = field(default_factory=list)
    raw_context: Union[str, List[str]] = ""
    
    @classmethod
    def from_json(cls, context: Union[str, List[str]]) -> 'DTDLContext':
        """
        Parse @context from JSON.
        
        Args:
            context: The @context value (string or array of strings)
            
        Returns:
            Parsed DTDLContext object
        """
        if isinstance(context, str):
            contexts = [context]
        else:
            contexts = context
        
        version = 0
        extensions = []
        
        for ctx in contexts:
            if ctx.startswith("dtmi:dtdl:context;"):
                version_str = ctx.split(";")[-1].split("#")[0]
                version = int(version_str)
            elif ctx.startswith("dtmi:"):
                extensions.append(ctx)
        
        return cls(
            dtdl_version=version,
            extensions=extensions,
            raw_context=context
        )


# =============================================================================
# Complex Schema Types
# =============================================================================

@dataclass(init=False)
class DTDLEnumValue:
    """
    Represents an EnumValue in a DTDL Enum schema.
    
    Attributes:
        name: The programming name
        value: The on-the-wire value (integer or string)
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
        comment: Optional comment for model authors
    """
    name: str
    value: Union[int, str]
    dtmi: Optional[str]
    display_name: Optional[Union[str, Dict[str, str]]]
    description: Optional[Union[str, Dict[str, str]]]
    comment: Optional[str]

    def __init__(
        self,
        name: str,
        value: Optional[Union[int, str]] = None,
        *,
        enum_value: Optional[Union[int, str]] = None,
        dtmi: Optional[str] = None,
        display_name: Optional[Union[str, Dict[str, str]]] = None,
        description: Optional[Union[str, Dict[str, str]]] = None,
        comment: Optional[str] = None,
    ) -> None:
        resolved_value = value if value is not None else enum_value
        if resolved_value is None:
            raise ValueError("value or enum_value must be provided")
        self.name = name
        self.value = resolved_value
        self.dtmi = dtmi
        self.display_name = display_name
        self.description = description
        self.comment = comment
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {
            "name": self.name,
            "enumValue": self.value,
        }
        if self.dtmi:
            result["@id"] = self.dtmi
        if self.display_name:
            result["displayName"] = self.display_name
        if self.description:
            result["description"] = self.description
        if self.comment:
            result["comment"] = self.comment
        return result
    
    @property
    def enum_value(self) -> Union[int, str]:
        """Backward compatible alias for enum value."""
        return self.value
    
    @enum_value.setter
    def enum_value(self, new_value: Union[int, str]) -> None:
        self.value = new_value


@dataclass
class DTDLEnum:
    """
    Represents a DTDL Enum schema.
    
    Attributes:
        value_schema: The data type (integer or string)
        enum_values: List of EnumValue definitions
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
    """
    value_schema: Literal["integer", "string"]
    enum_values: List[DTDLEnumValue] = field(default_factory=list)
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {
            "@type": "Enum",
            "valueSchema": self.value_schema,
            "enumValues": [ev.to_dict() for ev in self.enum_values],
        }
        if self.dtmi:
            result["@id"] = self.dtmi
        if self.display_name:
            result["displayName"] = self.display_name
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class DTDLField:
    """
    Represents a Field in a DTDL Object schema.
    
    Attributes:
        name: The programming name
        schema: The field's data type
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
    """
    name: str
    schema: Union[str, 'DTDLObject', 'DTDLArray', 'DTDLEnum', 'DTDLMap']
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None


@dataclass
class DTDLObject:
    """
    Represents a DTDL Object schema (struct-like).
    
    Attributes:
        fields: List of Field definitions
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
    """
    fields: List[DTDLField] = field(default_factory=list)
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None


@dataclass
class DTDLArray:
    """
    Represents a DTDL Array schema.
    
    Attributes:
        element_schema: The schema of array elements
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
    """
    element_schema: Union[str, DTDLObject, 'DTDLArray', DTDLEnum, 'DTDLMap']
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None


@dataclass
class DTDLMapKey:
    """Represents the key definition in a DTDL Map."""
    name: str
    schema: str = "string"  # Must always be string
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None


@dataclass
class DTDLMapValue:
    """Represents the value definition in a DTDL Map."""
    name: str
    schema: Union[str, DTDLObject, DTDLArray, DTDLEnum, 'DTDLMap']
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None


@dataclass
class DTDLMap:
    """
    Represents a DTDL Map schema (key-value pairs).
    
    Attributes:
        map_key: MapKey definition
        map_value: MapValue definition
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
    """
    map_key: DTDLMapKey
    map_value: DTDLMapValue
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None


@dataclass
class DTDLScaledDecimal:
    """
    Represents a DTDL v4 Scaled Decimal schema.
    
    The scaledDecimal schema type combines a decimal value with an explicit scale,
    useful for representing very large or small values efficiently.
    
    Structure:
        - scale: Count of decimal places to shift value (positive left, negative right)
        - value: The significand of the scaled decimal value (as decimal string)
    
    Example JSON representation:
        {
            "distance": {
                "scale": 7,
                "value": "1234.56"
            }
        }
        This represents the value 12345600000.
    
    Attributes:
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
        comment: Optional comment for model authors
    """
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        # scaledDecimal is referenced by name, not as a complex type definition
        return "scaledDecimal"
    
    @staticmethod
    def get_json_schema() -> Dict[str, Any]:
        """Get JSON Schema representation for scaledDecimal values."""
        return {
            "type": "object",
            "properties": {
                "scale": {
                    "type": "integer",
                    "description": "Count of decimal places to shift value (positive left, negative right)"
                },
                "value": {
                    "type": "string",
                    "description": "The significand as a decimal string"
                }
            },
            "required": ["scale", "value"]
        }


# Type alias for any schema
DTDLSchema = Union[str, DTDLObject, DTDLArray, DTDLEnum, DTDLMap, DTDLScaledDecimal]


# =============================================================================
# Interface Content Types
# =============================================================================

@dataclass
class DTDLProperty:
    """
    Represents a DTDL Property element.
    
    Properties describe the read-only and read/write state of a digital twin.
    
    Attributes:
        name: The programming name (required)
        schema: The data type (required)
        writable: Whether the property is writable (default: False)
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
        comment: Optional comment for model authors
    """
    name: str
    schema: DTDLSchema
    writable: bool = False
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None
    # Semantic type annotations (from extensions)
    semantic_types: List[str] = field(default_factory=list)
    unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {
            "@type": "Property",
            "name": self.name,
        }
        if isinstance(self.schema, str):
            result["schema"] = self.schema
        else:
            result["schema"] = self.schema.to_dict() if hasattr(self.schema, 'to_dict') else str(self.schema)
        if self.writable:
            result["writable"] = self.writable
        if self.dtmi:
            result["@id"] = self.dtmi
        if self.display_name:
            result["displayName"] = self.display_name
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class DTDLTelemetry:
    """
    Represents a DTDL Telemetry element.
    
    Telemetry describes data emitted by a digital twin (sensor readings, alerts, etc.).
    
    Attributes:
        name: The programming name (required)
        schema: The data type (required)
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
        comment: Optional comment for model authors
    """
    name: str
    schema: DTDLSchema
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None
    # Semantic type annotations (from extensions)
    semantic_types: List[str] = field(default_factory=list)
    unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {
            "@type": "Telemetry",
            "name": self.name,
        }
        if isinstance(self.schema, str):
            result["schema"] = self.schema
        else:
            result["schema"] = self.schema.to_dict() if hasattr(self.schema, 'to_dict') else str(self.schema)
        if self.dtmi:
            result["@id"] = self.dtmi
        if self.display_name:
            result["displayName"] = self.display_name
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class DTDLRelationship:
    """
    Represents a DTDL Relationship element.
    
    Relationships describe links to other digital twins, enabling graphs.
    
    Attributes:
        name: The programming name (required)
        target: DTMI of target Interface (optional - any Interface if not specified)
        min_multiplicity: Minimum instances (default: 0)
        max_multiplicity: Maximum instances (default: unlimited)
        writable: Whether the relationship is writable (default: False)
        properties: Properties attached to the relationship
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
    """
    name: str
    target: Optional[str] = None  # DTMI of target Interface
    min_multiplicity: int = 0
    max_multiplicity: Optional[int] = None
    writable: bool = False
    properties: List[DTDLProperty] = field(default_factory=list)
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {
            "@type": "Relationship",
            "name": self.name,
        }
        if self.target:
            result["target"] = self.target
        if self.min_multiplicity != 0:
            result["minMultiplicity"] = self.min_multiplicity
        if self.max_multiplicity is not None:
            result["maxMultiplicity"] = self.max_multiplicity
        if self.writable:
            result["writable"] = self.writable
        if self.properties:
            result["properties"] = [p.to_dict() for p in self.properties]
        if self.dtmi:
            result["@id"] = self.dtmi
        if self.display_name:
            result["displayName"] = self.display_name
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class DTDLComponent:
    """
    Represents a DTDL Component element.
    
    Components enable composition - including another Interface "by value".
    
    Attributes:
        name: The programming name (required)
        schema: DTMI of the Interface to include (required)
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
    """
    name: str
    schema: str  # DTMI of the Interface
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {
            "@type": "Component",
            "name": self.name,
            "schema": self.schema,
        }
        if self.dtmi:
            result["@id"] = self.dtmi
        if self.display_name:
            result["displayName"] = self.display_name
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class DTDLCommandPayload:
    """
    Represents a Command request or response payload.
    
    Attributes:
        name: The programming name (required)
        schema: The data type (required)
        nullable: Whether the payload may be null (default: False)
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
    """
    name: str
    schema: DTDLSchema
    nullable: bool = False
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None


@dataclass
class DTDLCommand:
    """
    Represents a DTDL Command element.
    
    Commands describe functions or operations that can be performed on a digital twin.
    
    Attributes:
        name: The programming name (required)
        request: The input to the command (optional)
        response: The output of the command (optional)
        dtmi: Optional @id
        display_name: Optional display name
        description: Optional description
    """
    name: str
    request: Optional[DTDLCommandPayload] = None
    response: Optional[DTDLCommandPayload] = None
    dtmi: Optional[str] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {
            "@type": "Command",
            "name": self.name,
        }
        if self.request:
            result["request"] = {
                "name": self.request.name,
                "schema": self.request.schema if isinstance(self.request.schema, str) else "object",
            }
            if self.request.nullable:
                result["request"]["nullable"] = True
        if self.response:
            result["response"] = {
                "name": self.response.name,
                "schema": self.response.schema if isinstance(self.response.schema, str) else "object",
            }
            if self.response.nullable:
                result["response"]["nullable"] = True
        if self.dtmi:
            result["@id"] = self.dtmi
        if self.display_name:
            result["displayName"] = self.display_name
        if self.description:
            result["description"] = self.description
        return result


# Type alias for Interface contents
DTDLContent = Union[DTDLProperty, DTDLTelemetry, DTDLRelationship, DTDLComponent, DTDLCommand]


# =============================================================================
# Interface (Top-level DTDL Element)
# =============================================================================

@dataclass
class DTDLInterface:
    """
    Represents a DTDL Interface - the top-level element.
    
    An Interface describes the contents (Commands, Components, Properties,
    Relationships, and Telemetries) of a digital twin.
    
    Attributes:
        dtmi: The @id (required) - Digital Twin Model Identifier
        type: Literal Interface type (defaults to "Interface" for compatibility)
        contents: List of Commands, Components, Properties, Relationships, Telemetries
        extends: List of DTMIs of parent Interfaces
        schemas: Reusable complex schemas defined in this Interface
        context: The @context specifying DTDL version and extensions
        display_name: Optional display name
        description: Optional description
        comment: Optional comment for model authors
    """
    dtmi: str
    type: str = "Interface"
    contents: List[DTDLContent] = field(default_factory=list)
    extends: List[str] = field(default_factory=list)
    schemas: List[Union[DTDLObject, DTDLArray, DTDLEnum, DTDLMap]] = field(default_factory=list)
    context: Optional[DTDLContext] = None
    display_name: Optional[Union[str, Dict[str, str]]] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    comment: Optional[str] = None
    # Source tracking for error messages
    source_file: Optional[str] = None
    
    def _replace_contents(self, cls: type, new_items: List[DTDLContent]) -> None:
        """Replace items of a specific type within contents."""
        self.contents = [c for c in self.contents if not isinstance(c, cls)]
        self.contents.extend(new_items)
    
    @property
    def properties(self) -> List[DTDLProperty]:
        """Get all Property elements from contents."""
        return [c for c in self.contents if isinstance(c, DTDLProperty)]
    
    @properties.setter
    def properties(self, items: List[DTDLProperty]) -> None:
        self._replace_contents(DTDLProperty, items)
    
    @property
    def telemetries(self) -> List[DTDLTelemetry]:
        """Get all Telemetry elements from contents."""
        return [c for c in self.contents if isinstance(c, DTDLTelemetry)]
    
    @telemetries.setter
    def telemetries(self, items: List[DTDLTelemetry]) -> None:
        self._replace_contents(DTDLTelemetry, items)
    
    @property
    def relationships(self) -> List[DTDLRelationship]:
        """Get all Relationship elements from contents."""
        return [c for c in self.contents if isinstance(c, DTDLRelationship)]
    
    @relationships.setter
    def relationships(self, items: List[DTDLRelationship]) -> None:
        self._replace_contents(DTDLRelationship, items)
    
    @property
    def components(self) -> List[DTDLComponent]:
        """Get all Component elements from contents."""
        return [c for c in self.contents if isinstance(c, DTDLComponent)]
    
    @components.setter
    def components(self, items: List[DTDLComponent]) -> None:
        self._replace_contents(DTDLComponent, items)
    
    @property
    def commands(self) -> List[DTDLCommand]:
        """Get all Command elements from contents."""
        return [c for c in self.contents if isinstance(c, DTDLCommand)]
    
    @commands.setter
    def commands(self, items: List[DTDLCommand]) -> None:
        self._replace_contents(DTDLCommand, items)
    
    @property
    def name(self) -> str:
        """
        Extract a name from the DTMI.
        
        Returns the last path segment before the version.
        Example: dtmi:com:example:Thermostat;1 -> Thermostat
        """
        if not self.dtmi:
            return "Unknown"
        # Remove dtmi: prefix and version suffix
        path = self.dtmi.replace("dtmi:", "").split(";")[0]
        # Get last segment
        return path.split(":")[-1]
    
    @property
    def resolved_display_name(self) -> str:
        """
        Get the display name, falling back to extracted name from DTMI.
        
        Returns:
            Display name string (resolves localized strings to default)
        """
        if self.display_name:
            if isinstance(self.display_name, str):
                return self.display_name
            # Return English or first available language
            return self.display_name.get("en", list(self.display_name.values())[0])
        return self.name
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (JSON representation)."""
        result: Dict[str, Any] = {
            "@id": self.dtmi,
            "@type": "Interface",
        }
        if self.context:
            result["@context"] = self.context.raw_context
        if self.display_name:
            result["displayName"] = self.display_name
        if self.description:
            result["description"] = self.description
        if self.comment:
            result["comment"] = self.comment
        if self.extends:
            result["extends"] = self.extends if len(self.extends) > 1 else self.extends[0]
        if self.contents:
            result["contents"] = [c.to_dict() for c in self.contents]
        if self.schemas:
            result["schemas"] = [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.schemas]
        return result
    
    def __repr__(self) -> str:
        return f"DTDLInterface(dtmi='{self.dtmi}', name='{self.name}')"
