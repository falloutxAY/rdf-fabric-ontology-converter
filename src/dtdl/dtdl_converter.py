"""
DTDL to Fabric Converter

This module converts parsed DTDL interfaces to Microsoft Fabric Ontology format.

Mapping Strategy:
- DTDLInterface -> EntityType
- DTDLProperty -> EntityTypeProperty
- DTDLTelemetry -> EntityTypeProperty (timeseries)
- DTDLRelationship -> RelationshipType
- DTDLComponent -> Flattened properties from referenced Interface
- DTDLCommand -> Custom metadata or skipped
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path

from .dtdl_models import (
    DTDLInterface,
    DTDLProperty,
    DTDLTelemetry,
    DTDLRelationship,
    DTDLComponent,
    DTDLCommand,
    DTDLEnum,
    DTDLObject,
    DTDLArray,
    DTDLMap,
    DTDLPrimitiveSchema,
    DTDLScaledDecimal,
)

# Import shared Fabric models
try:
    from ..models import (
        EntityType,
        EntityTypeProperty,
        RelationshipType,
        RelationshipEnd,
        ConversionResult,
        SkippedItem,
    )
except ImportError:
    # Fallback for direct script execution
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models import (
        EntityType,
        EntityTypeProperty,
        RelationshipType,
        RelationshipEnd,
        ConversionResult,
        SkippedItem,
    )

logger = logging.getLogger(__name__)


# Type mapping from DTDL to Fabric
DTDL_TO_FABRIC_TYPE: Dict[str, str] = {
    # Numeric types
    "boolean": "Boolean",
    "byte": "BigInt",
    "short": "BigInt",
    "integer": "BigInt",
    "long": "BigInt",
    "unsignedByte": "BigInt",
    "unsignedShort": "BigInt",
    "unsignedInteger": "BigInt",
    "unsignedLong": "BigInt",
    "float": "Double",
    "double": "Double",
    "decimal": "Double",
    # String types
    "string": "String",
    "uuid": "String",
    "bytes": "String",  # Base64 encoded
    # Date/time types
    "date": "DateTime",
    "dateTime": "DateTime",
    "time": "String",  # Time-only not directly supported
    "duration": "String",
    # Geospatial types (stored as JSON strings)
    "point": "String",
    "lineString": "String",
    "polygon": "String",
    "multiPoint": "String",
    "multiLineString": "String",
    "multiPolygon": "String",
    # DTDL v4 Scaled Decimal (stored as JSON object with scale and value)
    "scaledDecimal": "String",
}


class DTDLToFabricConverter:
    """
    Convert parsed DTDL interfaces to Microsoft Fabric Ontology format.
    
    This converter handles:
    - Interface to EntityType mapping
    - Property/Telemetry to EntityTypeProperty mapping
    - Relationship to RelationshipType mapping
    - Component flattening (optional)
    - Inheritance resolution
    - Complex schema type handling
    
    Example usage:
        converter = DTDLToFabricConverter()
        result = converter.convert(interfaces)
        definition = converter.to_fabric_definition(result, "MyOntology")
    """
    
    def __init__(
        self,
        id_prefix: int = 1000000000000,
        namespace: str = "usertypes",
        flatten_components: bool = False,
        include_commands: bool = False
    ):
        """
        Initialize the converter.
        
        Args:
            id_prefix: Base prefix for generated IDs
            namespace: Namespace for entity types
            flatten_components: If True, flatten Component contents into parent
            include_commands: If True, create properties for commands
        """
        self.id_prefix = id_prefix
        self.namespace = namespace
        self.flatten_components = flatten_components
        self.include_commands = include_commands
        
        # Mapping tables
        self._dtmi_to_fabric_id: Dict[str, str] = {}
        self._interface_map: Dict[str, DTDLInterface] = {}
        self._property_id_counter = 0
        
        # Track property names and types across the entire hierarchy
        # Used to detect and resolve conflicts
        self._property_registry: Dict[str, str] = {}  # property_name -> first_seen_type
    
    def _get_ancestor_properties(self, interface: DTDLInterface) -> Dict[str, str]:
        """
        Get all property names and types from ancestor interfaces.
        
        Args:
            interface: The interface to check ancestors for
            
        Returns:
            Dict mapping property name to Fabric value type
        """
        ancestor_props: Dict[str, str] = {}
        
        for parent_dtmi in interface.extends:
            if parent_dtmi in self._interface_map:
                parent = self._interface_map[parent_dtmi]
                # Add parent's direct properties
                for prop in parent.properties:
                    prop_type = self._schema_to_fabric_type(prop.schema)
                    ancestor_props[prop.name] = prop_type
                # Recursively add grandparent properties
                ancestor_props.update(self._get_ancestor_properties(parent))
        
        return ancestor_props
    
    def _resolve_property_name(
        self,
        prop_name: str,
        prop_type: str,
        interface: DTDLInterface
    ) -> str:
        """
        Resolve a property name, adding type suffix if there's a conflict.
        
        Args:
            prop_name: Original property name
            prop_type: Fabric value type of the property
            interface: The interface containing the property
            
        Returns:
            Resolved property name (possibly with type suffix)
        """
        # Check if this property name exists in ancestors with a different type
        ancestor_props = self._get_ancestor_properties(interface)
        
        if prop_name in ancestor_props:
            ancestor_type = ancestor_props[prop_name]
            if ancestor_type != prop_type:
                # Conflict detected - add type suffix
                type_suffix = prop_type.lower()
                resolved_name = f"{prop_name}_{type_suffix}"
                logger.warning(
                    f"Property '{prop_name}' in {interface.name} conflicts with ancestor "
                    f"(ancestor type: {ancestor_type}, this type: {prop_type}). "
                    f"Renaming to '{resolved_name}'"
                )
                return resolved_name
        
        # Check global registry for sibling conflicts
        registry_key = prop_name
        if registry_key in self._property_registry:
            registered_type = self._property_registry[registry_key]
            if registered_type != prop_type:
                # Sibling conflict - add type suffix
                type_suffix = prop_type.lower()
                resolved_name = f"{prop_name}_{type_suffix}"
                logger.debug(
                    f"Property '{prop_name}' in {interface.name} has sibling with different type. "
                    f"Using name '{resolved_name}'"
                )
                return resolved_name
        else:
            # Register this property name and type
            self._property_registry[registry_key] = prop_type
        
        return prop_name
    
    def convert(self, interfaces: List[DTDLInterface]) -> ConversionResult:
        """
        Convert DTDL interfaces to Fabric ontology format.
        
        Args:
            interfaces: List of parsed DTDL interfaces
            
        Returns:
            ConversionResult with entity types, relationships, and any skipped items
        """
        result = ConversionResult()
        
        # Reset property registry for this conversion
        self._property_registry = {}
        
        # Build interface map for lookups
        self._interface_map = {iface.dtmi: iface for iface in interfaces}
        
        # Pre-generate Fabric IDs for all interfaces
        for interface in interfaces:
            self._get_or_create_fabric_id(interface.dtmi)
        
        # Sort interfaces so parents come before children
        sorted_interfaces = self._topological_sort(interfaces)
        
        # Convert each interface
        for interface in sorted_interfaces:
            try:
                entity_type = self._convert_interface(interface)
                result.entity_types.append(entity_type)
            except Exception as e:
                logger.warning(f"Failed to convert interface {interface.dtmi}: {e}")
                result.skipped_items.append(SkippedItem(
                    item_type="interface",
                    name=interface.name,
                    reason=str(e),
                    uri=interface.dtmi,
                ))
        
        # Convert relationships (second pass to ensure all entity IDs exist)
        for interface in interfaces:
            for rel in interface.relationships:
                try:
                    rel_type = self._convert_relationship(rel, interface)
                    if rel_type:
                        result.relationship_types.append(rel_type)
                except Exception as e:
                    logger.warning(f"Failed to convert relationship {rel.name}: {e}")
                    result.skipped_items.append(SkippedItem(
                        item_type="relationship",
                        name=rel.name,
                        reason=str(e),
                        uri=rel.dtmi or f"{interface.dtmi}:{rel.name}",
                    ))
        
        return result
    
    def _get_or_create_fabric_id(self, dtmi: str) -> str:
        """
        Get or create a Fabric-compatible ID for a DTMI.
        
        Uses a hash-based approach to create deterministic IDs.
        
        Args:
            dtmi: Digital Twin Model Identifier
            
        Returns:
            Fabric-compatible numeric string ID
        """
        if dtmi in self._dtmi_to_fabric_id:
            return self._dtmi_to_fabric_id[dtmi]
        
        # Remove dtmi: prefix and version for consistent hashing
        clean_dtmi = dtmi.replace("dtmi:", "").split(";")[0]
        
        # Create deterministic hash
        hash_bytes = hashlib.sha256(clean_dtmi.encode()).digest()
        hash_int = int.from_bytes(hash_bytes[:8], 'big')
        
        # Apply prefix and limit to reasonable range
        fabric_id = str(self.id_prefix + (hash_int % 1000000000000))
        
        self._dtmi_to_fabric_id[dtmi] = fabric_id
        return fabric_id
    
    def _create_property_id(self, base_id: str, property_name: str) -> str:
        """
        Create a unique property ID within an entity type.
        
        Args:
            base_id: The entity type's Fabric ID
            property_name: Name of the property
            
        Returns:
            Unique property ID string
        """
        # Hash property name to create deterministic sub-ID
        prop_hash = hashlib.md5(property_name.encode()).hexdigest()[:8]
        return f"{base_id}{int(prop_hash, 16) % 10000:04d}"
    
    def _convert_interface(self, interface: DTDLInterface) -> EntityType:
        """
        Convert a DTDL Interface to a Fabric EntityType.
        
        Args:
            interface: The DTDL interface to convert
            
        Returns:
            Fabric EntityType
        """
        fabric_id = self._get_or_create_fabric_id(interface.dtmi)
        
        # Determine parent ID - only if parent is in our interface set
        base_entity_type_id = None
        if interface.extends:
            # Use first parent for single inheritance
            parent_dtmi = interface.extends[0]
            # Only set parent if it's defined in our interface set
            if parent_dtmi in self._interface_map:
                base_entity_type_id = self._get_or_create_fabric_id(parent_dtmi)
            else:
                logger.warning(
                    f"Interface {interface.dtmi} extends external type {parent_dtmi}; "
                    f"parent reference will be removed (type becomes root entity)"
                )
            if len(interface.extends) > 1:
                logger.warning(
                    f"Interface {interface.dtmi} has multiple parents; "
                    f"using only first: {parent_dtmi}"
                )
        
        # Convert properties
        properties: List[EntityTypeProperty] = []
        timeseries_properties: List[EntityTypeProperty] = []
        
        display_name_property_id: Optional[str] = None
        
        # Process Properties
        for prop in interface.properties:
            entity_prop = self._convert_property(prop, fabric_id, interface)
            properties.append(entity_prop)
            
            # Use first string property as display name
            if display_name_property_id is None and entity_prop.valueType == "String":
                display_name_property_id = entity_prop.id
        
        # Process Telemetry as timeseries properties
        for telemetry in interface.telemetries:
            entity_prop = self._convert_telemetry(telemetry, fabric_id, interface)
            timeseries_properties.append(entity_prop)
        
        # Optionally process Commands
        if self.include_commands:
            for command in interface.commands:
                # Create a string property to represent the command
                cmd_prop = EntityTypeProperty(
                    id=self._create_property_id(fabric_id, f"cmd_{command.name}"),
                    name=f"command_{command.name}",
                    valueType="String",
                )
                properties.append(cmd_prop)
        
        # Optionally flatten Components
        if self.flatten_components:
            for component in interface.components:
                component_props = self._flatten_component(component, fabric_id)
                properties.extend(component_props)
        
        # Determine entity ID parts (use first BigInt property if available)
        entity_id_parts: List[str] = []
        for prop in properties:
            if prop.valueType == "BigInt":
                entity_id_parts.append(prop.id)
                break
        
        return EntityType(
            id=fabric_id,
            name=self._sanitize_name(interface.resolved_display_name),
            namespace=self.namespace,
            namespaceType="Custom",
            visibility="Visible",
            baseEntityTypeId=base_entity_type_id,
            entityIdParts=entity_id_parts,
            displayNamePropertyId=display_name_property_id,
            properties=properties,
            timeseriesProperties=timeseries_properties,
        )
    
    def _convert_property(
        self,
        prop: DTDLProperty,
        entity_id: str,
        interface: DTDLInterface
    ) -> EntityTypeProperty:
        """
        Convert a DTDL Property to a Fabric EntityTypeProperty.
        
        Args:
            prop: The DTDL property
            entity_id: Parent entity's Fabric ID
            interface: The interface containing this property (for conflict resolution)
            
        Returns:
            Fabric EntityTypeProperty
        """
        value_type = self._schema_to_fabric_type(prop.schema)
        
        # Resolve property name to handle conflicts with ancestors/siblings
        resolved_name = self._resolve_property_name(prop.name, value_type, interface)
        
        return EntityTypeProperty(
            id=self._create_property_id(entity_id, resolved_name),
            name=self._sanitize_name(resolved_name),
            valueType=value_type,
        )
    
    def _convert_telemetry(
        self,
        telemetry: DTDLTelemetry,
        entity_id: str,
        interface: DTDLInterface
    ) -> EntityTypeProperty:
        """
        Convert a DTDL Telemetry to a Fabric timeseries property.
        
        Args:
            telemetry: The DTDL telemetry element
            entity_id: Parent entity's Fabric ID
            interface: The interface containing this telemetry (for conflict resolution)
            
        Returns:
            Fabric EntityTypeProperty (for timeseriesProperties)
        """
        value_type = self._schema_to_fabric_type(telemetry.schema)
        
        # Resolve property name to handle conflicts with ancestors/siblings
        resolved_name = self._resolve_property_name(telemetry.name, value_type, interface)
        
        return EntityTypeProperty(
            id=self._create_property_id(entity_id, f"ts_{resolved_name}"),
            name=self._sanitize_name(resolved_name),
            valueType=value_type,
        )
    
    def _convert_relationship(
        self,
        rel: DTDLRelationship,
        source_interface: DTDLInterface
    ) -> Optional[RelationshipType]:
        """
        Convert a DTDL Relationship to a Fabric RelationshipType.
        
        Args:
            rel: The DTDL relationship
            source_interface: The interface containing the relationship
            
        Returns:
            Fabric RelationshipType, or None if target is not resolvable
        """
        source_id = self._get_or_create_fabric_id(source_interface.dtmi)
        
        # Determine target ID
        if rel.target:
            target_id = self._get_or_create_fabric_id(rel.target)
        else:
            # No specific target - skip or use generic
            logger.warning(
                f"Relationship {rel.name} has no target; skipping"
            )
            return None
        
        # Generate relationship ID
        rel_id = self._create_property_id(source_id, f"rel_{rel.name}")
        
        return RelationshipType(
            id=rel_id,
            name=self._sanitize_name(rel.name),
            source=RelationshipEnd(entityTypeId=source_id),
            target=RelationshipEnd(entityTypeId=target_id),
            namespace=self.namespace,
            namespaceType="Custom",
        )
    
    def _flatten_component(
        self,
        component: DTDLComponent,
        parent_entity_id: str
    ) -> List[EntityTypeProperty]:
        """
        Flatten a Component's properties into the parent entity.
        
        Args:
            component: The DTDL component
            parent_entity_id: Parent entity's Fabric ID
            
        Returns:
            List of properties with prefixed names
        """
        properties: List[EntityTypeProperty] = []
        
        # Look up the component's interface
        component_interface = self._interface_map.get(component.schema)
        if not component_interface:
            logger.warning(f"Component schema not found: {component.schema}")
            return properties
        
        # Prefix all properties with component name
        prefix = f"{component.name}_"
        
        for prop in component_interface.properties:
            prefixed_name = prefix + prop.name
            entity_prop = EntityTypeProperty(
                id=self._create_property_id(parent_entity_id, prefixed_name),
                name=self._sanitize_name(prefixed_name),
                valueType=self._schema_to_fabric_type(prop.schema),
            )
            properties.append(entity_prop)
        
        return properties
    
    def _schema_to_fabric_type(self, schema) -> str:
        """
        Convert a DTDL schema to Fabric value type.
        
        Args:
            schema: DTDL schema (string or complex type)
            
        Returns:
            Fabric value type string
        """
        if isinstance(schema, str):
            # Primitive type or DTMI reference
            return DTDL_TO_FABRIC_TYPE.get(schema, "String")
        
        # Complex types
        if isinstance(schema, DTDLEnum):
            # Store enum as the value schema type
            return DTDL_TO_FABRIC_TYPE.get(schema.value_schema, "String")
        
        if isinstance(schema, (DTDLObject, DTDLArray, DTDLMap)):
            # Complex types stored as JSON strings
            return "String"
        
        if isinstance(schema, DTDLScaledDecimal):
            # ScaledDecimal stored as JSON object string
            return "String"
        
        return "String"
    
    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name to meet Fabric requirements.
        
        Fabric names must be alphanumeric with underscores,
        start with a letter, and be <= 90 characters.
        
        Args:
            name: Original name
            
        Returns:
            Sanitized name
        """
        if not name:
            return "Entity"
        
        # Replace invalid characters with underscore
        sanitized = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
        
        # Ensure starts with letter
        if not sanitized[0].isalpha():
            sanitized = 'E_' + sanitized
        
        # Truncate to max length
        return sanitized[:90]
    
    def _topological_sort(
        self,
        interfaces: List[DTDLInterface]
    ) -> List[DTDLInterface]:
        """
        Sort interfaces so parents come before children.
        
        Uses Kahn's algorithm for topological sorting.
        
        Args:
            interfaces: List of interfaces to sort
            
        Returns:
            Sorted list with parents first
        """
        dtmi_to_interface = {iface.dtmi: iface for iface in interfaces}
        
        # Calculate in-degree (number of parents in the input set)
        in_degree: Dict[str, int] = {iface.dtmi: 0 for iface in interfaces}
        children: Dict[str, List[str]] = {iface.dtmi: [] for iface in interfaces}
        
        for interface in interfaces:
            for parent_dtmi in interface.extends:
                if parent_dtmi in dtmi_to_interface:
                    in_degree[interface.dtmi] += 1
                    children[parent_dtmi].append(interface.dtmi)
        
        # Start with root interfaces (no parents in input set)
        queue = [dtmi for dtmi, degree in in_degree.items() if degree == 0]
        sorted_list: List[DTDLInterface] = []
        
        while queue:
            current_dtmi = queue.pop(0)
            sorted_list.append(dtmi_to_interface[current_dtmi])
            
            for child_dtmi in children.get(current_dtmi, []):
                in_degree[child_dtmi] -= 1
                if in_degree[child_dtmi] == 0:
                    queue.append(child_dtmi)
        
        # Add any remaining (cycle or external parent)
        for interface in interfaces:
            if interface not in sorted_list:
                sorted_list.append(interface)
        
        return sorted_list
    
    def to_fabric_definition(
        self,
        result: ConversionResult,
        ontology_name: str = "DTDLOntology"
    ) -> Dict[str, Any]:
        """
        Create the Fabric API definition format from conversion result.
        
        Args:
            result: Conversion result with entity and relationship types
            ontology_name: Display name for the ontology
            
        Returns:
            Dictionary with "parts" array for Fabric API
        """
        import base64
        
        parts = []
        
        # .platform file
        platform_content = {
            "metadata": {
                "type": "Ontology",
                "displayName": ontology_name
            }
        }
        parts.append({
            "path": ".platform",
            "payload": base64.b64encode(
                json.dumps(platform_content, indent=2).encode()
            ).decode(),
            "payloadType": "InlineBase64"
        })
        
        # definition.json
        parts.append({
            "path": "definition.json",
            "payload": base64.b64encode(b"{}").decode(),
            "payloadType": "InlineBase64"
        })
        
        # Entity types
        for entity_type in result.entity_types:
            entity_content = entity_type.to_dict()
            parts.append({
                "path": f"EntityTypes/{entity_type.id}/definition.json",
                "payload": base64.b64encode(
                    json.dumps(entity_content, indent=2).encode()
                ).decode(),
                "payloadType": "InlineBase64"
            })
        
        # Relationship types
        for rel_type in result.relationship_types:
            rel_content = rel_type.to_dict()
            parts.append({
                "path": f"RelationshipTypes/{rel_type.id}/definition.json",
                "payload": base64.b64encode(
                    json.dumps(rel_content, indent=2).encode()
                ).decode(),
                "payloadType": "InlineBase64"
            })
        
        return {"parts": parts}
    
    def get_dtmi_mapping(self) -> Dict[str, str]:
        """
        Get the DTMI to Fabric ID mapping.
        
        Useful for debugging and reference tracking.
        
        Returns:
            Dictionary mapping DTMI strings to Fabric IDs
        """
        return dict(self._dtmi_to_fabric_id)
