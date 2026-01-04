"""
CDM Converter.

This module provides conversion functionality from CDM (Common Data Model) entities
and relationships to Microsoft Fabric Ontology format (EntityType and RelationshipType).

Conversion process:
1. Parse CDM manifest/entities
2. Convert entities to Fabric EntityTypes
3. Convert attributes to EntityTypeProperties
4. Convert CDM relationships to Fabric RelationshipTypes
5. Handle entity inheritance (flatten inherited attributes)

Usage:
    from formats.cdm.cdm_converter import CDMToFabricConverter
    
    converter = CDMToFabricConverter()
    
    # Convert from content string
    result = converter.convert(json_content)
    
    # Convert parsed manifest
    result = converter.convert_manifest(manifest)
    
    # Access converted types
    for entity_type in result.entity_types:
        print(entity_type.name)
"""

import logging
from typing import Any, Dict, List, Optional, Set

from shared.models.conversion import ConversionResult, SkippedItem
from shared.models.fabric_types import (
    EntityType,
    EntityTypeProperty,
    RelationshipEnd,
    RelationshipType,
)
from shared.utilities.id_generator import IDGenerator

from .cdm_models import CDMAttribute, CDMEntity, CDMManifest, CDMRelationship
from .cdm_parser import CDMParser
from .cdm_type_mapper import CDMTypeMapper, FabricValueType

logger = logging.getLogger(__name__)


class CDMToFabricConverter:
    """
    Convert CDM entities and relationships to Fabric Ontology format.
    
    Handles:
    - Entity to EntityType conversion
    - Attribute to EntityTypeProperty conversion
    - Relationship to RelationshipType conversion
    - Entity inheritance flattening
    - Type mapping (CDM to Fabric types)
    
    Example:
        >>> converter = CDMToFabricConverter()
        >>> result = converter.convert(cdm_content)
        >>> print(f"Converted {len(result.entity_types)} entities")
    """
    
    def __init__(
        self,
        namespace: str = "usertypes",
        namespace_type: str = "Custom",
        flatten_inheritance: bool = True
    ):
        """
        Initialize the converter.
        
        Args:
            namespace: Fabric namespace for converted types.
            namespace_type: Fabric namespace type.
            flatten_inheritance: Whether to flatten inherited attributes.
        """
        self.namespace = namespace
        self.namespace_type = namespace_type
        self.flatten_inheritance = flatten_inheritance
        
        self._parser = CDMParser()
        self._type_mapper = CDMTypeMapper()
        self._id_generator = IDGenerator()
        
        # Tracking
        self._entity_id_map: Dict[str, str] = {}  # entity name -> fabric id
        self._converted_entities: Dict[str, CDMEntity] = {}  # for inheritance lookup
    
    def convert(self, content: str, file_path: Optional[str] = None, **kwargs: Any) -> ConversionResult:
        """
        Convert CDM content to Fabric types.
        
        Args:
            content: JSON string containing CDM content.
            file_path: Optional path for context.
            **kwargs: Additional conversion options.
            
        Returns:
            ConversionResult with converted types and any issues.
        """
        try:
            manifest = self._parser.parse(content, file_path)
            return self.convert_manifest(manifest, **kwargs)
        except Exception as e:
            logger.error(f"CDM conversion failed: {e}")
            result = ConversionResult()
            result.skipped_items.append(SkippedItem(
                item_type="manifest",
                name=file_path or "unknown",
                reason=f"Parse error: {str(e)}",
                uri=file_path or ""
            ))
            return result
    
    def convert_file(self, file_path: str, **kwargs: Any) -> ConversionResult:
        """
        Convert a CDM file to Fabric types.
        
        Args:
            file_path: Path to CDM file.
            **kwargs: Additional conversion options.
            
        Returns:
            ConversionResult with converted types and any issues.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return self.convert(content, file_path, **kwargs)
    
    def convert_manifest(self, manifest: CDMManifest, **kwargs: Any) -> ConversionResult:
        """
        Convert a parsed CDM manifest to Fabric types.
        
        Args:
            manifest: Parsed CDMManifest.
            **kwargs: Additional conversion options.
            
        Returns:
            ConversionResult with converted types and any issues.
        """
        result = ConversionResult()
        
        # Reset tracking
        self._entity_id_map = {}
        self._converted_entities = {}
        
        # First pass: build entity map for inheritance and relationships
        for entity in manifest.entities:
            self._converted_entities[entity.name] = entity
        
        # Second pass: convert entities
        for entity in manifest.entities:
            try:
                entity_type = self._convert_entity(entity)
                if entity_type:
                    result.entity_types.append(entity_type)
            except Exception as e:
                logger.warning(f"Failed to convert entity '{entity.name}': {e}")
                result.skipped_items.append(SkippedItem(
                    item_type="entity",
                    name=entity.name,
                    reason=str(e),
                    uri=entity.source_path or entity.name
                ))
        
        # Third pass: convert relationships
        for relationship in manifest.relationships:
            try:
                rel_type = self._convert_relationship(relationship)
                if rel_type:
                    result.relationship_types.append(rel_type)
            except Exception as e:
                logger.warning(f"Failed to convert relationship: {e}")
                result.skipped_items.append(SkippedItem(
                    item_type="relationship",
                    name=relationship.relationship_name,
                    reason=str(e),
                    uri=f"{relationship.from_entity} -> {relationship.to_entity}"
                ))
        
        # Statistics
        result.interface_count = len(manifest.entities)
        
        return result
    
    def _convert_entity(self, entity: CDMEntity) -> Optional[EntityType]:
        """
        Convert a CDM entity to Fabric EntityType.
        
        Args:
            entity: CDMEntity to convert.
            
        Returns:
            Converted EntityType or None if skipped.
        """
        if not entity.name:
            return None
        
        # Generate ID
        entity_id = self._id_generator.next_id_for_namespace("entities")
        self._entity_id_map[entity.name] = entity_id
        
        # Collect attributes (including inherited if flattening)
        all_attributes = self._collect_attributes(entity)
        
        # Convert attributes to properties
        properties: List[EntityTypeProperty] = []
        entity_id_parts: List[str] = []
        display_name_property_id: Optional[str] = None
        
        for attr in all_attributes:
            prop = self._convert_attribute(attr)
            if prop:
                properties.append(prop)
                
                # Track primary key
                if attr.is_primary_key:
                    entity_id_parts.append(prop.id)
                
                # Track display name
                if attr.is_display_name and not display_name_property_id:
                    display_name_property_id = prop.id
        
        # Create EntityType
        entity_type = EntityType(
            id=entity_id,
            name=entity.name,
            namespace=self.namespace,
            namespaceType=self.namespace_type,
            properties=properties,
            entityIdParts=entity_id_parts,
            displayNamePropertyId=display_name_property_id
        )
        
        # Handle base entity reference (if not flattening)
        if entity.extends_entity and not self.flatten_inheritance:
            base_id = self._entity_id_map.get(entity.extends_entity)
            if base_id:
                entity_type.baseEntityTypeId = base_id
        
        return entity_type
    
    def _collect_attributes(self, entity: CDMEntity) -> List[CDMAttribute]:
        """
        Collect all attributes for an entity, including inherited ones.
        
        Args:
            entity: CDMEntity to collect attributes for.
            
        Returns:
            List of all attributes.
        """
        if not self.flatten_inheritance:
            return entity.attributes
        
        all_attributes: List[CDMAttribute] = []
        seen_names: Set[str] = set()
        
        # Collect inherited attributes first (if base entity is known)
        if entity.extends_entity:
            base_entity = self._converted_entities.get(entity.extends_entity)
            if base_entity:
                inherited = self._collect_attributes(base_entity)
                for attr in inherited:
                    if attr.name not in seen_names:
                        all_attributes.append(attr)
                        seen_names.add(attr.name)
        
        # Add entity's own attributes (may override inherited)
        for attr in entity.attributes:
            if attr.name in seen_names:
                # Override inherited attribute
                all_attributes = [a for a in all_attributes if a.name != attr.name]
            all_attributes.append(attr)
            seen_names.add(attr.name)
        
        return all_attributes
    
    def _convert_attribute(self, attribute: CDMAttribute) -> Optional[EntityTypeProperty]:
        """
        Convert a CDM attribute to Fabric EntityTypeProperty.
        
        Args:
            attribute: CDMAttribute to convert.
            
        Returns:
            Converted EntityTypeProperty or None if skipped.
        """
        if not attribute.name:
            return None
        
        # Skip entity reference types (these become relationships)
        if attribute.data_type.lower() in ('entity', 'entityreference'):
            logger.debug(f"Skipping entity reference attribute: {attribute.name}")
            return None
        
        # Map CDM type to Fabric type
        trait_refs = [t.trait_reference for t in attribute.applied_traits]
        type_result = self._type_mapper.map_type(attribute.data_type, trait_refs)
        
        if type_result.warning:
            logger.debug(f"Type mapping warning for {attribute.name}: {type_result.warning}")
        
        # Generate property ID
        prop_id = self._id_generator.next_id_for_namespace("properties")
        
        return EntityTypeProperty(
            id=prop_id,
            name=attribute.name,
            valueType=type_result.fabric_type.value
        )
    
    def _convert_relationship(self, relationship: CDMRelationship) -> Optional[RelationshipType]:
        """
        Convert a CDM relationship to Fabric RelationshipType.
        
        Args:
            relationship: CDMRelationship to convert.
            
        Returns:
            Converted RelationshipType or None if skipped.
        """
        # Get entity IDs
        from_entity_name = relationship.from_entity_name
        to_entity_name = relationship.to_entity_name
        
        from_entity_id = self._entity_id_map.get(from_entity_name)
        to_entity_id = self._entity_id_map.get(to_entity_name)
        
        if not from_entity_id or not to_entity_id:
            logger.warning(
                f"Relationship references unknown entities: "
                f"'{from_entity_name}' -> '{to_entity_name}'"
            )
            # Create placeholder IDs for entities not in manifest
            if not from_entity_id:
                from_entity_id = self._id_generator.next_id_for_namespace("entities")
                self._entity_id_map[from_entity_name] = from_entity_id
            if not to_entity_id:
                to_entity_id = self._id_generator.next_id_for_namespace("entities")
                self._entity_id_map[to_entity_name] = to_entity_id
        
        # Generate relationship ID
        rel_id = self._id_generator.next_id_for_namespace("relationships")
        
        # Get relationship name
        rel_name = relationship.relationship_name
        
        return RelationshipType(
            id=rel_id,
            name=rel_name,
            source=RelationshipEnd(entityTypeId=from_entity_id),
            target=RelationshipEnd(entityTypeId=to_entity_id),
            namespace=self.namespace,
            namespaceType=self.namespace_type
        )
    
    def get_entity_id_map(self) -> Dict[str, str]:
        """
        Get mapping of entity names to Fabric IDs.
        
        Returns:
            Dictionary mapping entity names to their generated Fabric IDs.
        """
        return self._entity_id_map.copy()
