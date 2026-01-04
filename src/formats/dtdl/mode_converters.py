"""
DTDL Mode-Specific Converters.

This module provides specialized converters for handling DTDL elements
based on configuration modes:
- ComponentConverter: Handles Component to Entity/Relationship conversion
- CommandConverter: Handles Command to Entity conversion
- ScaledDecimalConverter: Handles scaledDecimal type conversion

These were extracted from dtdl_converter.py for better separation of concerns.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from shared.models import (
    EntityType,
    EntityTypeProperty,
    RelationshipType,
    RelationshipEnd,
)

logger = logging.getLogger(__name__)


class ComponentMode(str, Enum):
    """Component handling modes for DTDL to Fabric conversion."""
    FLATTEN = "flatten"  # Flatten properties into parent entity (legacy)
    SEPARATE = "separate"  # Create separate entity types with relationships
    SKIP = "skip"  # Skip components entirely


class CommandMode(str, Enum):
    """Command handling modes for DTDL to Fabric conversion."""
    SKIP = "skip"  # Skip commands entirely (legacy)
    PROPERTY = "property"  # Create string property (legacy include_commands=True)
    ENTITY = "entity"  # Create separate CommandType entity with parameters


class ScaledDecimalMode(str, Enum):
    """ScaledDecimal handling modes for DTDL to Fabric conversion."""
    JSON_STRING = "json_string"  # Store as JSON string: {"scale": n, "value": "x"}
    STRUCTURED = "structured"  # Store with separate _scale and _value properties
    CALCULATED = "calculated"  # Store calculated numeric value as Double


@dataclass
class ScaledDecimalValue:
    """
    Represents a parsed scaledDecimal value.
    
    The scaledDecimal schema type combines a decimal value with an explicit scale,
    useful for representing very large or small values efficiently.
    
    Attributes:
        scale: Count of decimal places to shift (positive=left, negative=right)
        value: The significand as a decimal string
    """
    scale: int
    value: str
    
    def calculate_actual_value(self) -> float:
        """
        Calculate the actual numeric value.
        
        Returns:
            float: The computed value (value * 10^scale)
            
        Example:
            ScaledDecimalValue(scale=7, value="1234.56").calculate_actual_value()
            # Returns 12345600000.0
        """
        try:
            base_value = float(self.value)
            return base_value * (10 ** self.scale)
        except (ValueError, OverflowError):
            return float('nan')
    
    def to_json_object(self) -> Dict[str, Any]:
        """Return JSON-serializable representation."""
        return {
            "scale": self.scale,
            "value": self.value,
            "calculatedValue": self.calculate_actual_value()
        }


class ComponentConverter:
    """
    Converts DTDL Components based on ComponentMode.
    
    Supports:
    - FLATTEN: Flatten component properties into parent entity
    - SEPARATE: Create separate entity types with relationships
    - SKIP: Skip components entirely
    """
    
    def __init__(
        self,
        mode: ComponentMode,
        namespace: str = "usertypes",
        id_generator: Optional[callable] = None,
        name_sanitizer: Optional[callable] = None,
    ):
        """
        Initialize the component converter.
        
        Args:
            mode: How to handle components
            namespace: Namespace for generated entities
            id_generator: Callable to generate unique IDs
            name_sanitizer: Callable to sanitize names
        """
        self.mode = mode
        self.namespace = namespace
        self._id_generator = id_generator
        self._name_sanitizer = name_sanitizer or self._default_sanitize
    
    def _default_sanitize(self, name: str) -> str:
        """Default name sanitization."""
        if not name:
            return "Entity"
        sanitized = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
        if not sanitized[0].isalpha():
            sanitized = 'E_' + sanitized
        return sanitized[:90]
    
    def _create_property_id(self, base_id: str, property_name: str) -> str:
        """Create a unique property ID."""
        prop_hash = hashlib.md5(property_name.encode()).hexdigest()[:8]
        return f"{base_id}{int(prop_hash, 16) % 10000:04d}"
    
    def convert_to_entity(
        self,
        component,
        source_interface,
        source_entity_id: str,
        interface_map: Dict[str, Any],
        dtmi_to_id: Dict[str, str],
        schema_to_type: callable,
    ) -> Tuple[Optional[EntityType], Optional[RelationshipType]]:
        """
        Convert a DTDL Component to a separate EntityType with relationship.
        
        Args:
            component: The DTDL component to convert
            source_interface: The parent interface
            source_entity_id: Parent entity's Fabric ID
            interface_map: Map of DTMI to interface objects
            dtmi_to_id: Map of DTMI to Fabric IDs
            schema_to_type: Function to convert schema to Fabric type
            
        Returns:
            Tuple of (EntityType, RelationshipType) or (None, None) if skipped
        """
        if self.mode != ComponentMode.SEPARATE:
            return None, None
        
        # Look up the component's interface schema
        component_interface = interface_map.get(component.schema)
        
        if component_interface:
            # Component references an interface we already converted
            target_id = dtmi_to_id.get(component.schema)
            if not target_id:
                return None, None
            
            rel_id = self._create_property_id(source_entity_id, f"comp_{component.name}")
            rel_type = RelationshipType(
                id=rel_id,
                name=self._name_sanitizer(f"has_{component.name}"),
                source=RelationshipEnd(entityTypeId=source_entity_id),
                target=RelationshipEnd(entityTypeId=target_id),
                namespace=self.namespace,
                namespaceType="Custom",
            )
            
            logger.info(
                f"Component '{component.name}' converted to relationship to existing "
                f"interface '{component_interface.name}'"
            )
            return None, rel_type
        else:
            # Component references an external interface - create stub entity
            stub_entity_id = dtmi_to_id.get(component.schema)
            if not stub_entity_id and self._id_generator:
                stub_entity_id = self._id_generator()
            
            # Extract name from schema DTMI
            schema_name = component.schema.replace("dtmi:", "").split(";")[0].split(":")[-1]
            
            stub_entity = EntityType(
                id=stub_entity_id,
                name=self._name_sanitizer(f"{component.name}_{schema_name}"),
                namespace=self.namespace,
                namespaceType="Custom",
                visibility="Visible",
                baseEntityTypeId=None,
                entityIdParts=[],
                displayNamePropertyId=None,
                properties=[
                    EntityTypeProperty(
                        id=self._create_property_id(stub_entity_id, "componentId"),
                        name="componentId",
                        valueType="String",
                    )
                ],
                timeseriesProperties=[],
            )
            
            stub_entity.entityIdParts = [stub_entity.properties[0].id]
            
            rel_id = self._create_property_id(source_entity_id, f"comp_{component.name}")
            rel_type = RelationshipType(
                id=rel_id,
                name=self._name_sanitizer(f"has_{component.name}"),
                source=RelationshipEnd(entityTypeId=source_entity_id),
                target=RelationshipEnd(entityTypeId=stub_entity_id),
                namespace=self.namespace,
                namespaceType="Custom",
            )
            
            logger.warning(
                f"Component '{component.name}' references external interface "
                f"'{component.schema}'; created stub entity"
            )
            return stub_entity, rel_type
    
    def flatten_properties(
        self,
        component,
        parent_entity_id: str,
        interface_map: Dict[str, Any],
        schema_to_type: callable,
    ) -> List[EntityTypeProperty]:
        """
        Flatten a Component's properties into the parent entity.
        
        Args:
            component: The DTDL component
            parent_entity_id: Parent entity's Fabric ID
            interface_map: Map of DTMI to interface objects
            schema_to_type: Function to convert schema to Fabric type
            
        Returns:
            List of properties with prefixed names
        """
        if self.mode != ComponentMode.FLATTEN:
            return []
        
        properties: List[EntityTypeProperty] = []
        
        component_interface = interface_map.get(component.schema)
        if not component_interface:
            logger.warning(f"Component schema not found: {component.schema}")
            return properties
        
        prefix = f"{component.name}_"
        
        for prop in component_interface.properties:
            prefixed_name = prefix + prop.name
            entity_prop = EntityTypeProperty(
                id=self._create_property_id(parent_entity_id, prefixed_name),
                name=self._name_sanitizer(prefixed_name),
                valueType=schema_to_type(prop.schema),
            )
            properties.append(entity_prop)
        
        return properties


class CommandConverter:
    """
    Converts DTDL Commands based on CommandMode.
    
    Supports:
    - SKIP: Skip commands entirely
    - PROPERTY: Create string property per command
    - ENTITY: Create separate CommandType entities
    """
    
    def __init__(
        self,
        mode: CommandMode,
        namespace: str = "usertypes",
        id_generator: Optional[callable] = None,
        name_sanitizer: Optional[callable] = None,
    ):
        """
        Initialize the command converter.
        
        Args:
            mode: How to handle commands
            namespace: Namespace for generated entities
            id_generator: Callable to generate unique IDs
            name_sanitizer: Callable to sanitize names
        """
        self.mode = mode
        self.namespace = namespace
        self._id_generator = id_generator
        self._name_sanitizer = name_sanitizer or self._default_sanitize
    
    def _default_sanitize(self, name: str) -> str:
        """Default name sanitization."""
        if not name:
            return "Entity"
        sanitized = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
        if not sanitized[0].isalpha():
            sanitized = 'E_' + sanitized
        return sanitized[:90]
    
    def _create_property_id(self, base_id: str, property_name: str) -> str:
        """Create a unique property ID."""
        prop_hash = hashlib.md5(property_name.encode()).hexdigest()[:8]
        return f"{base_id}{int(prop_hash, 16) % 10000:04d}"
    
    def convert_to_property(
        self,
        command,
        entity_id: str,
    ) -> Optional[EntityTypeProperty]:
        """
        Convert a command to a string property.
        
        Args:
            command: The DTDL command
            entity_id: Parent entity's Fabric ID
            
        Returns:
            EntityTypeProperty or None if mode is not PROPERTY
        """
        if self.mode != CommandMode.PROPERTY:
            return None
        
        return EntityTypeProperty(
            id=self._create_property_id(entity_id, f"cmd_{command.name}"),
            name=f"command_{command.name}",
            valueType="String",
        )
    
    def convert_to_entity(
        self,
        command,
        source_interface,
        source_entity_id: str,
        dtmi_to_id: Dict[str, str],
        schema_to_type: callable,
    ) -> Tuple[Optional[EntityType], Optional[RelationshipType]]:
        """
        Convert a DTDL Command to a separate CommandType EntityType.
        
        Args:
            command: The DTDL command to convert
            source_interface: The parent interface
            source_entity_id: Parent entity's Fabric ID
            dtmi_to_id: Map of DTMI to Fabric IDs
            schema_to_type: Function to convert schema to Fabric type
            
        Returns:
            Tuple of (EntityType for command, RelationshipType linking to parent)
        """
        if self.mode != CommandMode.ENTITY:
            return None, None
        
        cmd_dtmi = command.dtmi or f"{source_interface.dtmi}:cmd:{command.name}"
        cmd_entity_id = dtmi_to_id.get(cmd_dtmi)
        if not cmd_entity_id and self._id_generator:
            cmd_entity_id = self._id_generator()
        
        properties: List[EntityTypeProperty] = []
        
        # Command name property (identifier)
        name_prop = EntityTypeProperty(
            id=self._create_property_id(cmd_entity_id, "commandName"),
            name="commandName",
            valueType="String",
        )
        properties.append(name_prop)
        
        # Request schema as JSON property if present
        if command.request:
            req_prop = EntityTypeProperty(
                id=self._create_property_id(cmd_entity_id, "requestSchema"),
                name="requestSchema",
                valueType="String",
            )
            properties.append(req_prop)
            
            # Add individual request parameter properties
            if command.request.schema:
                req_params = self._extract_command_parameters(
                    command.request, cmd_entity_id, "request", schema_to_type
                )
                properties.extend(req_params)
        
        # Response schema as JSON property if present
        if command.response:
            resp_prop = EntityTypeProperty(
                id=self._create_property_id(cmd_entity_id, "responseSchema"),
                name="responseSchema",
                valueType="String",
            )
            properties.append(resp_prop)
            
            # Add individual response parameter properties
            if command.response.schema:
                resp_params = self._extract_command_parameters(
                    command.response, cmd_entity_id, "response", schema_to_type
                )
                properties.extend(resp_params)
        
        cmd_entity = EntityType(
            id=cmd_entity_id,
            name=self._name_sanitizer(f"Command_{command.name}"),
            namespace=self.namespace,
            namespaceType="Custom",
            visibility="Visible",
            baseEntityTypeId=None,
            entityIdParts=[name_prop.id],
            displayNamePropertyId=name_prop.id,
            properties=properties,
            timeseriesProperties=[],
        )
        
        rel_id = self._create_property_id(source_entity_id, f"cmd_rel_{command.name}")
        cmd_rel = RelationshipType(
            id=rel_id,
            name=self._name_sanitizer(f"supports_{command.name}"),
            source=RelationshipEnd(entityTypeId=source_entity_id),
            target=RelationshipEnd(entityTypeId=cmd_entity_id),
            namespace=self.namespace,
            namespaceType="Custom",
        )
        
        logger.info(f"Command '{command.name}' converted to entity type with relationship")
        return cmd_entity, cmd_rel
    
    def _extract_command_parameters(
        self,
        payload,
        entity_id: str,
        prefix: str,
        schema_to_type: callable,
    ) -> List[EntityTypeProperty]:
        """
        Extract properties from a command payload schema.
        
        Args:
            payload: The command request or response payload
            entity_id: Parent command entity ID
            prefix: Property name prefix ("request" or "response")
            schema_to_type: Function to convert schema to Fabric type
            
        Returns:
            List of EntityTypeProperty for the parameters
        """
        properties: List[EntityTypeProperty] = []
        
        # Check for DTDLObject schema
        if hasattr(payload.schema, 'fields'):
            for field in payload.schema.fields:
                field_type = schema_to_type(field.schema)
                prop = EntityTypeProperty(
                    id=self._create_property_id(entity_id, f"{prefix}_{field.name}"),
                    name=self._name_sanitizer(f"{prefix}_{field.name}"),
                    valueType=field_type,
                )
                properties.append(prop)
        elif isinstance(payload.schema, str):
            param_type = schema_to_type(payload.schema)
            prop = EntityTypeProperty(
                id=self._create_property_id(entity_id, f"{prefix}_{payload.name}"),
                name=self._name_sanitizer(f"{prefix}_{payload.name}"),
                valueType=param_type,
            )
            properties.append(prop)
        
        return properties


class ScaledDecimalConverter:
    """
    Converts DTDL scaledDecimal schema based on ScaledDecimalMode.
    
    Supports:
    - JSON_STRING: Store as JSON string {"scale": n, "value": "x"}
    - STRUCTURED: Create _scale and _value suffix properties
    - CALCULATED: Calculate and store as Double
    """
    
    def __init__(
        self,
        mode: ScaledDecimalMode,
        name_sanitizer: Optional[callable] = None,
    ):
        """
        Initialize the scaled decimal converter.
        
        Args:
            mode: How to handle scaledDecimal properties
            name_sanitizer: Callable to sanitize names
        """
        self.mode = mode
        self._name_sanitizer = name_sanitizer or self._default_sanitize
    
    def _default_sanitize(self, name: str) -> str:
        """Default name sanitization."""
        if not name:
            return "property"
        sanitized = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
        if not sanitized[0].isalpha():
            sanitized = 'p_' + sanitized
        return sanitized[:90]
    
    def _create_property_id(self, base_id: str, property_name: str) -> str:
        """Create a unique property ID."""
        prop_hash = hashlib.md5(property_name.encode()).hexdigest()[:8]
        return f"{base_id}{int(prop_hash, 16) % 10000:04d}"
    
    def get_fabric_type(self) -> str:
        """
        Get the Fabric type for scaledDecimal based on mode.
        
        Returns:
            Fabric value type string
        """
        if self.mode == ScaledDecimalMode.CALCULATED:
            return "Double"
        return "String"
    
    def create_structured_properties(
        self,
        prop_name: str,
        entity_id: str,
    ) -> List[EntityTypeProperty]:
        """
        Create structured properties for scaledDecimal in STRUCTURED mode.
        
        Args:
            prop_name: Base property name
            entity_id: Parent entity ID
            
        Returns:
            List containing _scale and _value properties
        """
        if self.mode != ScaledDecimalMode.STRUCTURED:
            return []
        
        scale_prop = EntityTypeProperty(
            id=self._create_property_id(entity_id, f"{prop_name}_scale"),
            name=self._name_sanitizer(f"{prop_name}_scale"),
            valueType="BigInt",
        )
        value_prop = EntityTypeProperty(
            id=self._create_property_id(entity_id, f"{prop_name}_value"),
            name=self._name_sanitizer(f"{prop_name}_value"),
            valueType="String",
        )
        
        return [scale_prop, value_prop]
    
    def convert_value(self, scale: int, value: str) -> Any:
        """
        Convert a scaledDecimal value based on mode.
        
        Args:
            scale: The scale factor
            value: The significand value
            
        Returns:
            Converted value (JSON string, dict, or float)
        """
        sd = ScaledDecimalValue(scale=scale, value=value)
        
        if self.mode == ScaledDecimalMode.CALCULATED:
            return sd.calculate_actual_value()
        elif self.mode == ScaledDecimalMode.STRUCTURED:
            return {"scale": scale, "value": value}
        else:  # JSON_STRING
            return json.dumps(sd.to_json_object())
