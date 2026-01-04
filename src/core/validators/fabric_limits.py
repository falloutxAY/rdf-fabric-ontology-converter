"""
Fabric Limits Validation.

Validates ontology definitions against Microsoft Fabric API limits.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FabricLimitValidationError:
    """
    Represents a validation error or warning for Fabric API limits.
    
    Attributes:
        level: Severity level ("error" or "warning")
        message: Human-readable description of the issue
        entity_name: Name of the affected entity/property/relationship
        field: The specific field that violated the limit
        current_value: The current value that triggered the validation
        limit_value: The limit that was exceeded
    """
    level: str  # "error" or "warning"
    message: str
    entity_name: str = ""
    field: str = ""
    current_value: Optional[Any] = None
    limit_value: Optional[Any] = None


class FabricLimitsValidator:
    """
    Validates Fabric Ontology definitions against API limits and constraints.
    
    This validator checks:
    - Entity type name length limits
    - Property name length limits
    - Relationship type name length limits
    - Total definition size limits
    - Count limits (entity types, relationships, properties)
    - entityIdParts constraints
    
    Usage:
        from core.validators import FabricLimitsValidator
        from models import EntityType, RelationshipType
        
        validator = FabricLimitsValidator()
        
        # Validate entity types
        errors = validator.validate_entity_types(entity_types)
        
        # Validate relationships
        errors += validator.validate_relationship_types(relationships)
        
        # Validate definition size
        errors += validator.validate_definition_size(entity_types, relationships)
        
        # Check for errors
        for error in errors:
            if error.level == "error":
                print(f"ERROR: {error.message}")
            else:
                print(f"WARNING: {error.message}")
    """
    
    def __init__(
        self,
        max_entity_name_length: Optional[int] = None,
        max_property_name_length: Optional[int] = None,
        max_relationship_name_length: Optional[int] = None,
        max_definition_size_kb: Optional[int] = None,
        warn_definition_size_kb: Optional[int] = None,
        max_entity_types: Optional[int] = None,
        max_relationship_types: Optional[int] = None,
        max_properties_per_entity: Optional[int] = None,
        max_entity_id_parts: Optional[int] = None,
    ):
        """
        Initialize the validator with configurable limits.
        
        All parameters are optional; defaults from FabricLimits are used if not provided.
        
        Args:
            max_entity_name_length: Maximum characters for entity names
            max_property_name_length: Maximum characters for property names
            max_relationship_name_length: Maximum characters for relationship names
            max_definition_size_kb: Maximum total definition size in KB
            warn_definition_size_kb: Size threshold for warnings (before hitting max)
            max_entity_types: Maximum number of entity types
            max_relationship_types: Maximum number of relationship types
            max_properties_per_entity: Maximum properties per entity
            max_entity_id_parts: Maximum items in entityIdParts
        """
        # Import here to avoid circular imports
        try:
            from ...constants import FabricLimits
        except ImportError:
            try:
                from constants import FabricLimits
            except ImportError:
                # Fallback defaults
                class FabricLimits:
                    MAX_ENTITY_NAME_LENGTH = 256
                    MAX_PROPERTY_NAME_LENGTH = 256
                    MAX_RELATIONSHIP_NAME_LENGTH = 256
                    MAX_DEFINITION_SIZE_KB = 1024
                    WARN_DEFINITION_SIZE_KB = 800
                    MAX_ENTITY_TYPES = 1000
                    MAX_RELATIONSHIP_TYPES = 500
                    MAX_PROPERTIES_PER_ENTITY = 100
                    MAX_ENTITY_ID_PARTS = 10
        
        self.max_entity_name_length = max_entity_name_length or FabricLimits.MAX_ENTITY_NAME_LENGTH
        self.max_property_name_length = max_property_name_length or FabricLimits.MAX_PROPERTY_NAME_LENGTH
        self.max_relationship_name_length = max_relationship_name_length or FabricLimits.MAX_RELATIONSHIP_NAME_LENGTH
        self.max_definition_size_kb = max_definition_size_kb or FabricLimits.MAX_DEFINITION_SIZE_KB
        self.warn_definition_size_kb = warn_definition_size_kb or FabricLimits.WARN_DEFINITION_SIZE_KB
        self.max_entity_types = max_entity_types or FabricLimits.MAX_ENTITY_TYPES
        self.max_relationship_types = max_relationship_types or FabricLimits.MAX_RELATIONSHIP_TYPES
        self.max_properties_per_entity = max_properties_per_entity or FabricLimits.MAX_PROPERTIES_PER_ENTITY
        self.max_entity_id_parts = max_entity_id_parts or FabricLimits.MAX_ENTITY_ID_PARTS
        
        self._logger = logging.getLogger(__name__)
    
    def validate_entity_types(self, entity_types: List[Any]) -> List[FabricLimitValidationError]:
        """
        Validate entity types against Fabric limits.
        
        Checks:
        - Entity name length
        - Property name lengths
        - Property count per entity
        - entityIdParts count and validity
        
        Args:
            entity_types: List of EntityType objects
            
        Returns:
            List of validation errors and warnings
        """
        errors: List[FabricLimitValidationError] = []
        
        # Check total entity count
        if len(entity_types) > self.max_entity_types:
            errors.append(FabricLimitValidationError(
                level="error",
                message=f"Number of entity types ({len(entity_types)}) exceeds maximum ({self.max_entity_types})",
                field="entity_count",
                current_value=len(entity_types),
                limit_value=self.max_entity_types,
            ))
        elif len(entity_types) > self.max_entity_types * 0.9:
            errors.append(FabricLimitValidationError(
                level="warning",
                message=f"Number of entity types ({len(entity_types)}) is approaching maximum ({self.max_entity_types})",
                field="entity_count",
                current_value=len(entity_types),
                limit_value=self.max_entity_types,
            ))
        
        for entity in entity_types:
            entity_name = getattr(entity, 'name', str(entity))
            
            # Check entity name length
            if len(entity_name) > self.max_entity_name_length:
                errors.append(FabricLimitValidationError(
                    level="error",
                    message=f"Entity name '{entity_name[:50]}...' exceeds maximum length ({self.max_entity_name_length} characters)",
                    entity_name=entity_name,
                    field="name",
                    current_value=len(entity_name),
                    limit_value=self.max_entity_name_length,
                ))
            
            # Check properties
            properties = getattr(entity, 'properties', [])
            
            # Check property count
            if len(properties) > self.max_properties_per_entity:
                errors.append(FabricLimitValidationError(
                    level="error",
                    message=f"Entity '{entity_name}' has {len(properties)} properties, exceeding maximum ({self.max_properties_per_entity})",
                    entity_name=entity_name,
                    field="property_count",
                    current_value=len(properties),
                    limit_value=self.max_properties_per_entity,
                ))
            elif len(properties) > self.max_properties_per_entity * 0.9:
                errors.append(FabricLimitValidationError(
                    level="warning",
                    message=f"Entity '{entity_name}' has {len(properties)} properties, approaching maximum ({self.max_properties_per_entity})",
                    entity_name=entity_name,
                    field="property_count",
                    current_value=len(properties),
                    limit_value=self.max_properties_per_entity,
                ))
            
            # Check each property name length
            for prop in properties:
                prop_name = getattr(prop, 'name', str(prop))
                if len(prop_name) > self.max_property_name_length:
                    errors.append(FabricLimitValidationError(
                        level="error",
                        message=f"Property '{prop_name[:50]}...' in entity '{entity_name}' exceeds maximum length ({self.max_property_name_length} characters)",
                        entity_name=entity_name,
                        field="property_name",
                        current_value=len(prop_name),
                        limit_value=self.max_property_name_length,
                    ))
            
            # Check timeseries properties too
            ts_properties = getattr(entity, 'timeseriesProperties', [])
            for prop in ts_properties:
                prop_name = getattr(prop, 'name', str(prop))
                if len(prop_name) > self.max_property_name_length:
                    errors.append(FabricLimitValidationError(
                        level="error",
                        message=f"Timeseries property '{prop_name[:50]}...' in entity '{entity_name}' exceeds maximum length ({self.max_property_name_length} characters)",
                        entity_name=entity_name,
                        field="timeseries_property_name",
                        current_value=len(prop_name),
                        limit_value=self.max_property_name_length,
                    ))
            
            # Check entityIdParts count
            entity_id_parts = getattr(entity, 'entityIdParts', [])
            if len(entity_id_parts) > self.max_entity_id_parts:
                errors.append(FabricLimitValidationError(
                    level="error",
                    message=f"Entity '{entity_name}' has {len(entity_id_parts)} entityIdParts, exceeding maximum ({self.max_entity_id_parts})",
                    entity_name=entity_name,
                    field="entityIdParts",
                    current_value=len(entity_id_parts),
                    limit_value=self.max_entity_id_parts,
                ))
        
        return errors
    
    def validate_relationship_types(self, relationship_types: List[Any]) -> List[FabricLimitValidationError]:
        """
        Validate relationship types against Fabric limits.
        
        Checks:
        - Relationship name length
        - Total relationship count
        
        Args:
            relationship_types: List of RelationshipType objects
            
        Returns:
            List of validation errors and warnings
        """
        errors: List[FabricLimitValidationError] = []
        
        # Check total relationship count
        if len(relationship_types) > self.max_relationship_types:
            errors.append(FabricLimitValidationError(
                level="error",
                message=f"Number of relationship types ({len(relationship_types)}) exceeds maximum ({self.max_relationship_types})",
                field="relationship_count",
                current_value=len(relationship_types),
                limit_value=self.max_relationship_types,
            ))
        elif len(relationship_types) > self.max_relationship_types * 0.9:
            errors.append(FabricLimitValidationError(
                level="warning",
                message=f"Number of relationship types ({len(relationship_types)}) is approaching maximum ({self.max_relationship_types})",
                field="relationship_count",
                current_value=len(relationship_types),
                limit_value=self.max_relationship_types,
            ))
        
        for rel in relationship_types:
            rel_name = getattr(rel, 'name', str(rel))
            
            # Check relationship name length
            if len(rel_name) > self.max_relationship_name_length:
                errors.append(FabricLimitValidationError(
                    level="error",
                    message=f"Relationship name '{rel_name[:50]}...' exceeds maximum length ({self.max_relationship_name_length} characters)",
                    entity_name=rel_name,
                    field="name",
                    current_value=len(rel_name),
                    limit_value=self.max_relationship_name_length,
                ))
        
        return errors
    
    def validate_definition_size(
        self,
        entity_types: List[Any],
        relationship_types: List[Any],
    ) -> List[FabricLimitValidationError]:
        """
        Validate total definition size against Fabric limits.
        
        Estimates the JSON serialization size and warns if approaching limits.
        
        Args:
            entity_types: List of EntityType objects
            relationship_types: List of RelationshipType objects
            
        Returns:
            List of validation errors and warnings
        """
        errors: List[FabricLimitValidationError] = []
        
        # Calculate estimated size
        try:
            # Convert to dict for size estimation
            entities_data = []
            for entity in entity_types:
                if hasattr(entity, 'to_dict'):
                    entities_data.append(entity.to_dict())
                else:
                    entities_data.append({
                        'id': getattr(entity, 'id', ''),
                        'name': getattr(entity, 'name', ''),
                        'properties': [
                            {'id': p.id, 'name': p.name, 'valueType': p.valueType}
                            for p in getattr(entity, 'properties', [])
                        ],
                    })
            
            relationships_data = []
            for rel in relationship_types:
                if hasattr(rel, 'to_dict'):
                    relationships_data.append(rel.to_dict())
                else:
                    relationships_data.append({
                        'id': getattr(rel, 'id', ''),
                        'name': getattr(rel, 'name', ''),
                    })
            
            # Estimate size
            entities_json = json.dumps(entities_data)
            relationships_json = json.dumps(relationships_data)
            
            total_size_bytes = len(entities_json.encode('utf-8')) + len(relationships_json.encode('utf-8'))
            total_size_kb = total_size_bytes / 1024
            
            if total_size_kb > self.max_definition_size_kb:
                errors.append(FabricLimitValidationError(
                    level="error",
                    message=f"Total definition size ({total_size_kb:.1f} KB) exceeds maximum ({self.max_definition_size_kb} KB)",
                    field="definition_size",
                    current_value=round(total_size_kb, 1),
                    limit_value=self.max_definition_size_kb,
                ))
            elif total_size_kb > self.warn_definition_size_kb:
                errors.append(FabricLimitValidationError(
                    level="warning",
                    message=f"Total definition size ({total_size_kb:.1f} KB) is approaching maximum ({self.max_definition_size_kb} KB)",
                    field="definition_size",
                    current_value=round(total_size_kb, 1),
                    limit_value=self.max_definition_size_kb,
                ))
                
        except Exception as e:
            self._logger.warning(f"Could not estimate definition size: {e}")
        
        return errors
    
    def validate_all(
        self,
        entity_types: List[Any],
        relationship_types: List[Any],
    ) -> List[FabricLimitValidationError]:
        """
        Validate all Fabric limits.
        
        Convenience method that runs all validations.
        
        Args:
            entity_types: List of EntityType objects
            relationship_types: List of RelationshipType objects
            
        Returns:
            List of all validation errors and warnings
        """
        errors: List[FabricLimitValidationError] = []
        
        errors.extend(self.validate_entity_types(entity_types))
        errors.extend(self.validate_relationship_types(relationship_types))
        errors.extend(self.validate_definition_size(entity_types, relationship_types))
        
        return errors
    
    def get_errors_only(self, errors: List[FabricLimitValidationError]) -> List[FabricLimitValidationError]:
        """Filter to return only errors (not warnings)."""
        return [e for e in errors if e.level == "error"]
    
    def get_warnings_only(self, errors: List[FabricLimitValidationError]) -> List[FabricLimitValidationError]:
        """Filter to return only warnings (not errors)."""
        return [e for e in errors if e.level == "warning"]
    
    def has_errors(self, errors: List[FabricLimitValidationError]) -> bool:
        """Check if any errors exist (not just warnings)."""
        return any(e.level == "error" for e in errors)


class EntityIdPartsInferrer:
    """
    Infers and sets entityIdParts for entity types.
    
    entityIdParts defines which properties form the unique identity of an entity.
    This class provides intelligent inference based on:
    - Property name patterns (id, identifier, pk, etc.)
    - Property types (only String and BigInt are valid)
    - Configuration options
    
    Usage:
        from core.validators import EntityIdPartsInferrer
        
        inferrer = EntityIdPartsInferrer(strategy="auto")
        
        # Infer for a single entity
        inferrer.infer_entity_id_parts(entity)
        
        # Infer for all entities
        inferrer.infer_all(entity_types)
    """
    
    def __init__(
        self,
        strategy: Optional[str] = None,
        explicit_mappings: Optional[Dict[str, List[str]]] = None,
        custom_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize the inferrer with configuration.
        
        Args:
            strategy: Inference strategy - "auto", "first_valid", "explicit", or "none"
            explicit_mappings: Dict mapping entity names to property names for entityIdParts
            custom_patterns: Additional patterns to recognize as primary keys
        """
        # Import here to avoid circular imports
        try:
            from ...constants import EntityIdPartsConfig
        except ImportError:
            try:
                from constants import EntityIdPartsConfig
            except ImportError:
                # Fallback defaults
                class EntityIdPartsConfig:
                    DEFAULT_STRATEGY = "auto"
                    PRIMARY_KEY_PATTERNS = ["id", "identifier", "pk", "key", "uuid", "guid"]
                    VALID_TYPES = ["String", "BigInt"]
        
        self.strategy = strategy or EntityIdPartsConfig.DEFAULT_STRATEGY
        self.explicit_mappings = explicit_mappings or {}
        
        # Build pattern list
        self.patterns = list(EntityIdPartsConfig.PRIMARY_KEY_PATTERNS)
        if custom_patterns:
            self.patterns.extend(custom_patterns)
        
        self.valid_types = EntityIdPartsConfig.VALID_TYPES
        
        self._logger = logging.getLogger(__name__)
    
    def infer_entity_id_parts(self, entity: Any) -> List[str]:
        """
        Infer entityIdParts for a single entity.
        
        Args:
            entity: EntityType object
            
        Returns:
            List of property IDs to use as entityIdParts
        """
        entity_name = getattr(entity, 'name', '')
        properties = getattr(entity, 'properties', [])
        
        # Check explicit mapping first
        if entity_name in self.explicit_mappings:
            explicit_props = self.explicit_mappings[entity_name]
            return self._resolve_property_ids(properties, explicit_props)
        
        # Apply strategy
        if self.strategy == "none":
            return []
        
        if self.strategy == "explicit":
            # Only use explicit mappings, return empty if not mapped
            return []
        
        if self.strategy == "first_valid":
            return self._get_first_valid_property(properties)
        
        # Default: "auto" strategy
        return self._auto_infer(properties)
    
    def _auto_infer(self, properties: List[Any]) -> List[str]:
        """
        Automatically infer entityIdParts from properties.
        
        Priority:
        1. Property with name matching primary key patterns
        2. First valid (String/BigInt) property
        
        Args:
            properties: List of property objects
            
        Returns:
            List of property IDs
        """
        # First, look for properties matching primary key patterns
        for prop in properties:
            prop_name = getattr(prop, 'name', '').lower()
            prop_type = getattr(prop, 'valueType', '')
            prop_id = getattr(prop, 'id', '')
            
            if prop_type not in self.valid_types:
                continue
            
            # Check exact matches first
            if prop_name in [p.lower() for p in self.patterns]:
                return [prop_id]
            
            # Check contains patterns
            for pattern in self.patterns:
                if pattern.lower() in prop_name:
                    return [prop_id]
        
        # Fall back to first valid property
        return self._get_first_valid_property(properties)
    
    def _get_first_valid_property(self, properties: List[Any]) -> List[str]:
        """Get the first property with a valid type for entityIdParts."""
        for prop in properties:
            prop_type = getattr(prop, 'valueType', '')
            if prop_type in self.valid_types:
                return [getattr(prop, 'id', '')]
        return []
    
    def _resolve_property_ids(self, properties: List[Any], prop_names: List[str]) -> List[str]:
        """
        Resolve property names to property IDs.
        
        Args:
            properties: List of property objects
            prop_names: List of property names to find
            
        Returns:
            List of property IDs
        """
        prop_by_name = {
            getattr(p, 'name', '').lower(): getattr(p, 'id', '')
            for p in properties
        }
        
        result = []
        for name in prop_names:
            prop_id = prop_by_name.get(name.lower())
            if prop_id:
                result.append(prop_id)
            else:
                self._logger.warning(f"Property '{name}' not found for entityIdParts mapping")
        
        return result
    
    def infer_all(self, entity_types: List[Any], overwrite: bool = False) -> int:
        """
        Infer entityIdParts for all entity types.
        
        Args:
            entity_types: List of EntityType objects
            overwrite: If True, overwrite existing entityIdParts; if False, only set if empty
            
        Returns:
            Number of entities updated
        """
        updated = 0
        
        for entity in entity_types:
            current_parts = getattr(entity, 'entityIdParts', [])
            
            if current_parts and not overwrite:
                continue
            
            inferred_parts = self.infer_entity_id_parts(entity)
            
            if inferred_parts:
                entity.entityIdParts = inferred_parts
                updated += 1
                
                entity_name = getattr(entity, 'name', 'Unknown')
                self._logger.debug(f"Set entityIdParts for '{entity_name}': {inferred_parts}")
        
        return updated
    
    def set_display_name_property(self, entity: Any) -> Optional[str]:
        """
        Set displayNamePropertyId based on entityIdParts or first string property.
        
        Args:
            entity: EntityType object
            
        Returns:
            The property ID set, or None if not set
        """
        properties = getattr(entity, 'properties', [])
        entity_id_parts = getattr(entity, 'entityIdParts', [])
        
        # Use first entityIdPart if it's a String
        if entity_id_parts:
            for prop in properties:
                if getattr(prop, 'id', '') == entity_id_parts[0]:
                    if getattr(prop, 'valueType', '') == 'String':
                        entity.displayNamePropertyId = prop.id
                        return prop.id
        
        # Look for 'name' property
        for prop in properties:
            prop_name = getattr(prop, 'name', '').lower()
            if 'name' in prop_name and getattr(prop, 'valueType', '') == 'String':
                entity.displayNamePropertyId = prop.id
                return prop.id
        
        # Fall back to first String property
        for prop in properties:
            if getattr(prop, 'valueType', '') == 'String':
                entity.displayNamePropertyId = prop.id
                return prop.id
        
        return None
