"""
Fabric Definition Validation.

Validates Fabric ontology definitions (entity types, relationships)
before upload to ensure references are valid and configuration is correct.

This module was extracted from formats/rdf/rdf_converter.py for better
separation of concerns and reusability across RDF/DTDL converters.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DefinitionValidationError:
    """Represents a validation error in the ontology definition."""
    level: str  # "error" or "warning"
    message: str
    entity_id: Optional[str] = None
    
    def __str__(self) -> str:
        suffix = f" (entity: {self.entity_id})" if self.entity_id else ""
        return f"[{self.level.upper()}] {self.message}{suffix}"


class FabricDefinitionValidator:
    """
    Validates Fabric ontology definitions before upload.
    
    Catches invalid references and configuration issues before
    sending to the Fabric API, providing clearer error messages.
    
    This validator checks structural integrity:
    - Parent entity references exist
    - No self-inheritance
    - displayNamePropertyId references valid property
    - entityIdParts reference valid properties
    - Relationship source/target entities exist
    
    Usage:
        from core.validators import FabricDefinitionValidator
        
        is_valid, errors = FabricDefinitionValidator.validate_definition(
            entity_types, relationship_types
        )
        
        if not is_valid:
            for error in errors:
                print(f"{error.level}: {error.message}")
    """
    
    @staticmethod
    def validate_entity_types(entity_types: List) -> List[DefinitionValidationError]:
        """
        Validate entity type definitions.
        
        Checks:
        - Parent entity references exist
        - No self-inheritance
        - displayNamePropertyId references valid property
        - displayNameProperty is String type
        - entityIdParts reference valid properties
        - entityIdParts are String or BigInt type
        
        Args:
            entity_types: List of entity types to validate
            
        Returns:
            List of validation errors (may include warnings)
        """
        errors: List[DefinitionValidationError] = []
        
        # Build ID set for validation
        id_set = {e.id for e in entity_types}
        prop_ids_by_entity = {
            e.id: {p.id for p in e.properties} 
            for e in entity_types
        }
        
        for entity in entity_types:
            # 1. Validate parent reference
            if entity.baseEntityTypeId:
                if entity.baseEntityTypeId not in id_set:
                    errors.append(DefinitionValidationError(
                        level="error",
                        message=(
                            f"Entity '{entity.name}' references non-existent parent "
                            f"'{entity.baseEntityTypeId}'"
                        ),
                        entity_id=entity.id
                    ))
                elif entity.baseEntityTypeId == entity.id:
                    # Self-reference
                    errors.append(DefinitionValidationError(
                        level="error",
                        message=f"Entity '{entity.name}' cannot inherit from itself",
                        entity_id=entity.id
                    ))
            
            # 2. Validate displayNamePropertyId exists
            if entity.displayNamePropertyId:
                prop_ids = prop_ids_by_entity.get(entity.id, set())
                if entity.displayNamePropertyId not in prop_ids:
                    errors.append(DefinitionValidationError(
                        level="error",
                        message=(
                            f"Entity '{entity.name}' displayNamePropertyId "
                            f"'{entity.displayNamePropertyId}' not found in properties"
                        ),
                        entity_id=entity.id
                    ))
                else:
                    # Validate it's a String property (Fabric requirement)
                    prop = next(
                        (p for p in entity.properties 
                         if p.id == entity.displayNamePropertyId),
                        None
                    )
                    if prop and prop.valueType != "String":
                        errors.append(DefinitionValidationError(
                            level="warning",
                            message=(
                                f"Entity '{entity.name}' displayNameProperty "
                                f"should be String type, got '{prop.valueType}'"
                            ),
                            entity_id=entity.id
                        ))
            
            # 3. Validate entityIdParts
            if entity.entityIdParts:
                prop_ids = prop_ids_by_entity.get(entity.id, set())
                for part_id in entity.entityIdParts:
                    if part_id not in prop_ids:
                        errors.append(DefinitionValidationError(
                            level="error",
                            message=(
                                f"Entity '{entity.name}' entityIdPart "
                                f"'{part_id}' not found in properties"
                            ),
                            entity_id=entity.id
                        ))
                    else:
                        # Validate type is String or BigInt (Fabric requirement)
                        prop = next(
                            (p for p in entity.properties if p.id == part_id),
                            None
                        )
                        if prop and prop.valueType not in ("String", "BigInt"):
                            errors.append(DefinitionValidationError(
                                level="warning",
                                message=(
                                    f"Entity '{entity.name}' entityIdPart '{part_id}' should be "
                                    f"String or BigInt, got '{prop.valueType}'"
                                ),
                                entity_id=entity.id
                            ))
        
        return errors
    
    @staticmethod
    def validate_relationships(
        relationship_types: List,
        entity_types: List
    ) -> List[DefinitionValidationError]:
        """
        Validate relationship definitions.
        
        Checks:
        - Source entity exists
        - Target entity exists
        - Warns on self-referential relationships
        
        Args:
            relationship_types: List of relationships to validate
            entity_types: List of entity types for reference checking
            
        Returns:
            List of validation errors (may include warnings)
        """
        errors: List[DefinitionValidationError] = []
        
        entity_ids = {e.id for e in entity_types}
        
        for rel in relationship_types:
            source_id = rel.source.entityTypeId
            target_id = rel.target.entityTypeId
            
            # Validate source exists
            if source_id not in entity_ids:
                errors.append(DefinitionValidationError(
                    level="error",
                    message=(
                        f"Relationship '{rel.name}' source '{source_id}' "
                        f"references non-existent entity type"
                    ),
                    entity_id=rel.id
                ))
            
            # Validate target exists
            if target_id not in entity_ids:
                errors.append(DefinitionValidationError(
                    level="error",
                    message=(
                        f"Relationship '{rel.name}' target '{target_id}' "
                        f"references non-existent entity type"
                    ),
                    entity_id=rel.id
                ))
            
            # Warn on self-relationships (unusual but allowed)
            if source_id == target_id and source_id in entity_ids:
                errors.append(DefinitionValidationError(
                    level="warning",
                    message=(
                        f"Relationship '{rel.name}' is self-referential "
                        f"(source and target are same entity)"
                    ),
                    entity_id=rel.id
                ))
        
        return errors
    
    @classmethod
    def validate_definition(
        cls,
        entity_types: List,
        relationship_types: List
    ) -> Tuple[bool, List[DefinitionValidationError]]:
        """
        Validate complete ontology definition.
        
        Args:
            entity_types: List of entity types
            relationship_types: List of relationship types
            
        Returns:
            Tuple of (is_valid: bool, errors: List[DefinitionValidationError])
            is_valid is True only if there are no "error" level issues
        """
        all_errors: List[DefinitionValidationError] = []
        
        # Run all validations
        all_errors.extend(cls.validate_entity_types(entity_types))
        all_errors.extend(cls.validate_relationships(relationship_types, entity_types))
        
        # Separate errors from warnings
        critical_errors = [e for e in all_errors if e.level == "error"]
        
        is_valid = len(critical_errors) == 0
        
        return is_valid, all_errors
