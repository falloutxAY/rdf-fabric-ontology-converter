"""
DTDL Parser

This module provides functionality to parse DTDL JSON/JSON-LD files into
structured Python objects.

Supports:
- Single Interface files (.json)
- Array of Interfaces in a single file
- Directory traversal with recursive option
- DTDL versions 2, 3, and 4
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Set
from dataclasses import dataclass, field

from .dtdl_models import (
    DTDLInterface,
    DTDLProperty,
    DTDLTelemetry,
    DTDLRelationship,
    DTDLComponent,
    DTDLCommand,
    DTDLCommandPayload,
    DTDLContext,
    DTDLEnum,
    DTDLEnumValue,
    DTDLObject,
    DTDLArray,
    DTDLMap,
    DTDLMapKey,
    DTDLMapValue,
    DTDLField,
    DTDLSchema,
    DTDLScaledDecimal,
)

logger = logging.getLogger(__name__)


@dataclass
class ParseError:
    """Represents a parsing error."""
    file_path: str
    message: str
    line: Optional[int] = None
    
    def __str__(self) -> str:
        loc = f" (line {self.line})" if self.line else ""
        return f"{self.file_path}{loc}: {self.message}"


@dataclass
class ParseResult:
    """Result of parsing DTDL files."""
    interfaces: List[DTDLInterface] = field(default_factory=list)
    errors: List[ParseError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    files_parsed: int = 0
    
    @property
    def success(self) -> bool:
        """Check if parsing was successful (no errors)."""
        return len(self.errors) == 0
    
    def get_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Parse Summary:",
            f"  Files parsed: {self.files_parsed}",
            f"  Interfaces found: {len(self.interfaces)}",
        ]
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
            for err in self.errors[:5]:
                lines.append(f"    - {err}")
            if len(self.errors) > 5:
                lines.append(f"    ... and {len(self.errors) - 5} more")
        if self.warnings:
            lines.append(f"  Warnings: {len(self.warnings)}")
        return "\n".join(lines)


class DTDLParser:
    """
    Parse DTDL JSON files into structured objects.
    
    Supports:
    - Single Interface files
    - Array of Interfaces
    - Directory traversal (recursive)
    - DTDL versions 2, 3, and 4
    
    Example usage:
        parser = DTDLParser()
        result = parser.parse_file("model.json")
        if result.success:
            for interface in result.interfaces:
                print(f"Found: {interface.dtmi}")
    """
    
    # Supported DTDL context patterns
    SUPPORTED_CONTEXTS = [
        "dtmi:dtdl:context;2",
        "dtmi:dtdl:context;3",
        "dtmi:dtdl:context;4",
    ]
    
    # Valid file extensions for DTDL files
    DTDL_EXTENSIONS = {".json", ".dtdl"}
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize the parser.
        
        Args:
            strict_mode: If True, treat warnings as errors
        """
        self.strict_mode = strict_mode
        self._schema_cache: Dict[str, DTDLSchema] = {}
    
    def parse_file(self, file_path: Union[str, Path]) -> ParseResult:
        """
        Parse a single DTDL file.
        
        Args:
            file_path: Path to the DTDL JSON file
            
        Returns:
            ParseResult with interfaces and any errors
        """
        path = Path(file_path)
        result = ParseResult()
        
        if not path.exists():
            result.errors.append(ParseError(str(path), "File not found"))
            return result
        
        if not path.is_file():
            result.errors.append(ParseError(str(path), "Not a file"))
            return result
        
        if path.suffix.lower() not in self.DTDL_EXTENSIONS:
            result.warnings.append(f"Unexpected file extension: {path.suffix}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            result.errors.append(ParseError(str(path), f"Invalid JSON: {e}"))
            return result
        except UnicodeDecodeError as e:
            result.errors.append(ParseError(str(path), f"Encoding error: {e}"))
            return result
        except Exception as e:
            result.errors.append(ParseError(str(path), f"Error reading file: {e}"))
            return result
        
        result.files_parsed = 1
        
        # Parse the JSON content
        self._parse_json_content(data, str(path), result)
        
        return result
    
    def parse_directory(
        self,
        dir_path: Union[str, Path],
        recursive: bool = True
    ) -> ParseResult:
        """
        Parse all DTDL files in a directory.
        
        Args:
            dir_path: Path to the directory
            recursive: Whether to search subdirectories
            
        Returns:
            ParseResult with all interfaces and any errors
        """
        path = Path(dir_path)
        result = ParseResult()
        
        if not path.exists():
            result.errors.append(ParseError(str(path), "Directory not found"))
            return result
        
        if not path.is_dir():
            result.errors.append(ParseError(str(path), "Not a directory"))
            return result
        
        # Find all DTDL files
        pattern = "**/*" if recursive else "*"
        files: List[Path] = []
        
        for ext in self.DTDL_EXTENSIONS:
            files.extend(path.glob(f"{pattern}{ext}"))
        
        if not files:
            result.warnings.append(f"No DTDL files found in {path}")
            return result
        
        logger.info(f"Found {len(files)} DTDL files in {path}")
        
        # Parse each file
        for file_path in sorted(files):
            file_result = self.parse_file(file_path)
            result.interfaces.extend(file_result.interfaces)
            result.errors.extend(file_result.errors)
            result.warnings.extend(file_result.warnings)
            result.files_parsed += file_result.files_parsed
        
        return result
    
    def parse_string(self, content: str, source_name: str = "<string>") -> ParseResult:
        """
        Parse DTDL from a JSON string.
        
        Args:
            content: JSON string containing DTDL
            source_name: Name to use for error messages
            
        Returns:
            ParseResult with interfaces and any errors
        """
        result = ParseResult()
        
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            result.errors.append(ParseError(source_name, f"Invalid JSON: {e}"))
            return result
        
        result.files_parsed = 1
        self._parse_json_content(data, source_name, result)
        
        return result
    
    def _parse_json_content(
        self,
        data: Any,
        source: str,
        result: ParseResult
    ) -> None:
        """
        Parse JSON content that may be a single Interface or array of Interfaces.
        
        Args:
            data: Parsed JSON data
            source: Source file path for error messages
            result: ParseResult to populate
        """
        if isinstance(data, list):
            # Array of Interfaces
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    try:
                        interface = self._parse_interface(item, source)
                        if interface:
                            result.interfaces.append(interface)
                    except Exception as e:
                        result.errors.append(ParseError(
                            source, f"Error parsing Interface at index {i}: {e}"
                        ))
                else:
                    result.warnings.append(
                        f"{source}: Array item at index {i} is not an object"
                    )
        
        elif isinstance(data, dict):
            # Could be single Interface or document with nested Interfaces
            if data.get("@type") == "Interface":
                try:
                    interface = self._parse_interface(data, source)
                    if interface:
                        result.interfaces.append(interface)
                except Exception as e:
                    result.errors.append(ParseError(source, f"Error parsing Interface: {e}"))
            else:
                # Check for @graph (JSON-LD expanded form)
                if "@graph" in data:
                    for item in data["@graph"]:
                        if isinstance(item, dict) and item.get("@type") == "Interface":
                            try:
                                interface = self._parse_interface(item, source)
                                if interface:
                                    result.interfaces.append(interface)
                            except Exception as e:
                                result.errors.append(ParseError(
                                    source, f"Error parsing Interface in @graph: {e}"
                                ))
                else:
                    result.warnings.append(
                        f"{source}: Document does not contain an Interface"
                    )
        else:
            result.errors.append(ParseError(
                source, f"Expected object or array, got {type(data).__name__}"
            ))
    
    def _parse_interface(
        self,
        data: Dict[str, Any],
        source: str
    ) -> Optional[DTDLInterface]:
        """
        Parse an Interface from a JSON dictionary.
        
        Args:
            data: JSON dictionary representing the Interface
            source: Source file for error messages
            
        Returns:
            Parsed DTDLInterface or None if invalid
        """
        # Validate required fields
        dtmi = data.get("@id")
        if not dtmi:
            raise ValueError("Interface missing required @id field")
        
        if data.get("@type") != "Interface":
            raise ValueError(f"Expected @type='Interface', got '{data.get('@type')}'")
        
        # Parse @context
        context = None
        if "@context" in data:
            context = DTDLContext.from_json(data["@context"])
            if context.dtdl_version not in [2, 3, 4]:
                logger.warning(f"Unsupported DTDL version: {context.dtdl_version}")
        
        # Parse extends (can be string or array)
        extends: List[str] = []
        extends_data = data.get("extends")
        if extends_data:
            if isinstance(extends_data, str):
                extends = [extends_data]
            elif isinstance(extends_data, list):
                extends = [e for e in extends_data if isinstance(e, str)]
        
        # Parse contents
        contents = self._parse_contents(data.get("contents", []), source)
        
        # Parse reusable schemas
        schemas = self._parse_schemas(data.get("schemas", []), source)
        
        return DTDLInterface(
            dtmi=dtmi,
            contents=contents,
            extends=extends,
            schemas=schemas,
            context=context,
            display_name=data.get("displayName"),
            description=data.get("description"),
            comment=data.get("comment"),
            source_file=source,
        )
    
    def _parse_contents(
        self,
        contents: List[Dict[str, Any]],
        source: str
    ) -> List:
        """
        Parse Interface contents (Property, Telemetry, Relationship, etc.).
        
        Args:
            contents: List of content dictionaries
            source: Source file for error messages
            
        Returns:
            List of parsed content objects
        """
        parsed = []
        
        for item in contents:
            if not isinstance(item, dict):
                continue
            
            # Get @type (can be string or array for semantic types)
            type_val = item.get("@type")
            if isinstance(type_val, list):
                # First element is the base type
                base_type = type_val[0]
                semantic_types = type_val[1:] if len(type_val) > 1 else []
            else:
                base_type = type_val
                semantic_types = []
            
            try:
                if base_type == "Property":
                    parsed.append(self._parse_property(item, semantic_types))
                elif base_type == "Telemetry":
                    parsed.append(self._parse_telemetry(item, semantic_types))
                elif base_type == "Relationship":
                    parsed.append(self._parse_relationship(item))
                elif base_type == "Component":
                    parsed.append(self._parse_component(item))
                elif base_type == "Command":
                    parsed.append(self._parse_command(item))
                else:
                    logger.warning(f"{source}: Unknown content type: {base_type}")
            except Exception as e:
                logger.warning(f"{source}: Error parsing {base_type}: {e}")
        
        return parsed
    
    def _parse_property(
        self,
        data: Dict[str, Any],
        semantic_types: List[str] = None
    ) -> DTDLProperty:
        """Parse a Property element."""
        name = data.get("name")
        if not name:
            raise ValueError("Property missing required 'name' field")
        
        schema = self._parse_schema(data.get("schema"))
        
        return DTDLProperty(
            name=name,
            schema=schema,
            writable=data.get("writable", False),
            dtmi=data.get("@id"),
            display_name=data.get("displayName"),
            description=data.get("description"),
            comment=data.get("comment"),
            semantic_types=semantic_types or [],
            unit=data.get("unit"),
        )
    
    def _parse_telemetry(
        self,
        data: Dict[str, Any],
        semantic_types: List[str] = None
    ) -> DTDLTelemetry:
        """Parse a Telemetry element."""
        name = data.get("name")
        if not name:
            raise ValueError("Telemetry missing required 'name' field")
        
        schema = self._parse_schema(data.get("schema"))
        
        return DTDLTelemetry(
            name=name,
            schema=schema,
            dtmi=data.get("@id"),
            display_name=data.get("displayName"),
            description=data.get("description"),
            comment=data.get("comment"),
            semantic_types=semantic_types or [],
            unit=data.get("unit"),
        )
    
    def _parse_relationship(self, data: Dict[str, Any]) -> DTDLRelationship:
        """Parse a Relationship element."""
        name = data.get("name")
        if not name:
            raise ValueError("Relationship missing required 'name' field")
        
        # Parse relationship properties
        properties = []
        for prop_data in data.get("properties", []):
            if isinstance(prop_data, dict):
                properties.append(self._parse_property(prop_data))
        
        return DTDLRelationship(
            name=name,
            target=data.get("target"),
            min_multiplicity=data.get("minMultiplicity", 0),
            max_multiplicity=data.get("maxMultiplicity"),
            writable=data.get("writable", False),
            properties=properties,
            dtmi=data.get("@id"),
            display_name=data.get("displayName"),
            description=data.get("description"),
            comment=data.get("comment"),
        )
    
    def _parse_component(self, data: Dict[str, Any]) -> DTDLComponent:
        """Parse a Component element."""
        name = data.get("name")
        if not name:
            raise ValueError("Component missing required 'name' field")
        
        schema = data.get("schema")
        if not schema:
            raise ValueError("Component missing required 'schema' field")
        
        # Schema must be a DTMI string for Components
        if not isinstance(schema, str):
            raise ValueError("Component schema must be a DTMI string")
        
        return DTDLComponent(
            name=name,
            schema=schema,
            dtmi=data.get("@id"),
            display_name=data.get("displayName"),
            description=data.get("description"),
            comment=data.get("comment"),
        )
    
    def _parse_command(self, data: Dict[str, Any]) -> DTDLCommand:
        """Parse a Command element."""
        name = data.get("name")
        if not name:
            raise ValueError("Command missing required 'name' field")
        
        request = None
        if "request" in data:
            request = self._parse_command_payload(data["request"])
        
        response = None
        if "response" in data:
            response = self._parse_command_payload(data["response"])
        
        return DTDLCommand(
            name=name,
            request=request,
            response=response,
            dtmi=data.get("@id"),
            display_name=data.get("displayName"),
            description=data.get("description"),
            comment=data.get("comment"),
        )
    
    def _parse_command_payload(self, data: Dict[str, Any]) -> DTDLCommandPayload:
        """Parse a CommandRequest or CommandResponse."""
        name = data.get("name", "payload")
        schema = self._parse_schema(data.get("schema", "string"))
        
        return DTDLCommandPayload(
            name=name,
            schema=schema,
            nullable=data.get("nullable", False),
            dtmi=data.get("@id"),
            display_name=data.get("displayName"),
            description=data.get("description"),
            comment=data.get("comment"),
        )
    
    def _parse_schema(
        self,
        schema: Union[str, Dict[str, Any], None]
    ) -> DTDLSchema:
        """
        Parse a schema definition.
        
        Args:
            schema: Schema as string (primitive/DTMI) or dict (complex)
            
        Returns:
            Parsed schema (string for primitives, object for complex)
        """
        if schema is None:
            return "string"  # Default to string
        
        if isinstance(schema, str):
            # Handle scaledDecimal as a string reference (DTDL v4)
            if schema == "scaledDecimal":
                return DTDLScaledDecimal()
            return schema  # Primitive type or DTMI reference
        
        if isinstance(schema, dict):
            schema_type = schema.get("@type")
            
            if schema_type == "Enum":
                return self._parse_enum(schema)
            elif schema_type == "Object":
                return self._parse_object(schema)
            elif schema_type == "Array":
                return self._parse_array(schema)
            elif schema_type == "Map":
                return self._parse_map(schema)
            else:
                logger.warning(f"Unknown schema type: {schema_type}")
                return "string"
        
        return "string"
    
    def _parse_enum(self, data: Dict[str, Any]) -> DTDLEnum:
        """Parse an Enum schema."""
        value_schema = data.get("valueSchema", "integer")
        
        enum_values = []
        for ev_data in data.get("enumValues", []):
            if isinstance(ev_data, dict):
                enum_values.append(DTDLEnumValue(
                    name=ev_data.get("name", ""),
                    enum_value=ev_data.get("enumValue", 0),
                    dtmi=ev_data.get("@id"),
                    display_name=ev_data.get("displayName"),
                    description=ev_data.get("description"),
                    comment=ev_data.get("comment"),
                ))
        
        return DTDLEnum(
            value_schema=value_schema,
            enum_values=enum_values,
            dtmi=data.get("@id"),
            display_name=data.get("displayName"),
            description=data.get("description"),
            comment=data.get("comment"),
        )
    
    def _parse_object(self, data: Dict[str, Any]) -> DTDLObject:
        """Parse an Object schema."""
        fields = []
        for field_data in data.get("fields", []):
            if isinstance(field_data, dict):
                fields.append(DTDLField(
                    name=field_data.get("name", ""),
                    schema=self._parse_schema(field_data.get("schema")),
                    dtmi=field_data.get("@id"),
                    display_name=field_data.get("displayName"),
                    description=field_data.get("description"),
                    comment=field_data.get("comment"),
                ))
        
        return DTDLObject(
            fields=fields,
            dtmi=data.get("@id"),
            display_name=data.get("displayName"),
            description=data.get("description"),
            comment=data.get("comment"),
        )
    
    def _parse_array(self, data: Dict[str, Any]) -> DTDLArray:
        """Parse an Array schema."""
        element_schema = self._parse_schema(data.get("elementSchema"))
        
        return DTDLArray(
            element_schema=element_schema,
            dtmi=data.get("@id"),
            display_name=data.get("displayName"),
            description=data.get("description"),
            comment=data.get("comment"),
        )
    
    def _parse_map(self, data: Dict[str, Any]) -> DTDLMap:
        """Parse a Map schema."""
        map_key_data = data.get("mapKey", {})
        map_value_data = data.get("mapValue", {})
        
        map_key = DTDLMapKey(
            name=map_key_data.get("name", "key"),
            schema=map_key_data.get("schema", "string"),
            dtmi=map_key_data.get("@id"),
            display_name=map_key_data.get("displayName"),
            description=map_key_data.get("description"),
        )
        
        map_value = DTDLMapValue(
            name=map_value_data.get("name", "value"),
            schema=self._parse_schema(map_value_data.get("schema")),
            dtmi=map_value_data.get("@id"),
            display_name=map_value_data.get("displayName"),
            description=map_value_data.get("description"),
        )
        
        return DTDLMap(
            map_key=map_key,
            map_value=map_value,
            dtmi=data.get("@id"),
            display_name=data.get("displayName"),
            description=data.get("description"),
            comment=data.get("comment"),
        )
    
    def _parse_schemas(
        self,
        schemas: List[Dict[str, Any]],
        source: str
    ) -> List:
        """Parse reusable schemas defined in an Interface."""
        parsed = []
        
        for schema_data in schemas:
            if not isinstance(schema_data, dict):
                continue
            
            schema_type = schema_data.get("@type")
            
            try:
                if schema_type == "Enum":
                    parsed.append(self._parse_enum(schema_data))
                elif schema_type == "Object":
                    parsed.append(self._parse_object(schema_data))
                elif schema_type == "Array":
                    parsed.append(self._parse_array(schema_data))
                elif schema_type == "Map":
                    parsed.append(self._parse_map(schema_data))
                else:
                    logger.warning(f"{source}: Unknown schema type: {schema_type}")
            except Exception as e:
                logger.warning(f"{source}: Error parsing schema: {e}")
        
        return parsed
