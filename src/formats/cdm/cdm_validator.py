"""
CDM Validator.

This module provides validation functionality for CDM (Common Data Model) content
to ensure compatibility with Microsoft Fabric Ontology conversion.

Validation includes:
- JSON syntax validation
- CDM structure validation (required fields, valid references)
- Data type compatibility checks
- Fabric naming convention validation
- Relationship reference validation

Usage:
    from formats.cdm.cdm_validator import CDMValidator
    
    validator = CDMValidator()
    
    # Validate content string
    result = validator.validate(json_content)
    
    # Validate parsed manifest
    result = validator.validate_manifest(manifest)
    
    if result.is_valid:
        print("Validation passed!")
    else:
        for issue in result.errors:
            print(f"Error: {issue.message}")
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

from shared.utilities.validation import (
    IssueCategory,
    Severity,
    ValidationIssue,
    ValidationResult,
)

from .cdm_models import CDMAttribute, CDMEntity, CDMManifest, CDMRelationship
from .cdm_parser import CDMParser
from .cdm_type_mapper import CDMTypeMapper

logger = logging.getLogger(__name__)


# =============================================================================
# Validation Constants
# =============================================================================

# Fabric naming constraints
FABRIC_MAX_NAME_LENGTH = 100
FABRIC_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

# Reserved names (Fabric/system reserved)
RESERVED_NAMES = {
    'id', 'type', 'namespace', 'version', 'created', 'modified',
    'entity', 'relationship', 'property', 'system', 'internal',
}

# Valid CDM schema versions
SUPPORTED_CDM_VERSIONS = {'1.0.0', '1.1.0', '1.2.0', '1.3.0', '1.4.0', '1.5.0'}

# Maximum hierarchy depth
MAX_INHERITANCE_DEPTH = 10


class CDMValidator:
    """
    Validate CDM content for Fabric Ontology compatibility.
    
    Performs comprehensive validation including:
    - JSON syntax and structure
    - Entity and attribute validation
    - Type compatibility
    - Reference resolution
    - Fabric naming rules
    
    Example:
        >>> validator = CDMValidator()
        >>> result = validator.validate(cdm_content)
        >>> if not result.is_valid:
        ...     for issue in result.errors:
        ...         print(f"Error: {issue.message}")
    """
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize the validator.
        
        Args:
            strict_mode: If True, treat warnings as errors.
        """
        self.strict_mode = strict_mode
        self._parser = CDMParser()
        self._type_mapper = CDMTypeMapper()
        self._entity_names: Set[str] = set()
    
    def validate(self, content: str, file_path: Optional[str] = None) -> ValidationResult:
        """
        Validate CDM content string.
        
        Args:
            content: JSON string containing CDM content.
            file_path: Optional path for error messages.
            
        Returns:
            ValidationResult with all validation issues.
        """
        result = ValidationResult(format_name="cdm", source_path=file_path)
        
        # Step 1: JSON syntax validation
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.SYNTAX_ERROR,
                message=f"Invalid JSON syntax: {e.msg}",
                location=f"Line {e.lineno}, Column {e.colno}",
                details=str(e)
            )
            return result
        
        # Step 2: Parse and validate structure
        try:
            manifest = self._parser.parse(content, file_path)
            self._validate_manifest(manifest, result)
        except Exception as e:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.INVALID_STRUCTURE,
                message=f"Failed to parse CDM content: {str(e)}",
                details=str(e)
            )
        
        return result
    
    def validate_file(self, file_path: str) -> ValidationResult:
        """
        Validate a CDM file.
        
        Args:
            file_path: Path to CDM file.
            
        Returns:
            ValidationResult with all validation issues.
        """
        result = ValidationResult(format_name="cdm", source_path=file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.validate(content, file_path)
        except FileNotFoundError:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.MISSING_REQUIRED,
                message=f"File not found: {file_path}"
            )
        except UnicodeDecodeError as e:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.ENCODING_ERROR,
                message=f"File encoding error: {e}"
            )
        except Exception as e:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.SYNTAX_ERROR,
                message=f"Error reading file: {str(e)}"
            )
        
        return result
    
    def validate_manifest(self, manifest: CDMManifest) -> ValidationResult:
        """
        Validate a parsed CDM manifest.
        
        Args:
            manifest: Parsed CDMManifest object.
            
        Returns:
            ValidationResult with all validation issues.
        """
        result = ValidationResult(format_name="cdm", source_path=manifest.source_path)
        self._validate_manifest(manifest, result)
        return result
    
    def _validate_manifest(self, manifest: CDMManifest, result: ValidationResult) -> None:
        """
        Internal manifest validation.
        
        Args:
            manifest: CDMManifest to validate.
            result: ValidationResult to add issues to.
        """
        self._entity_names = set()
        
        # Validate manifest name
        if not manifest.name:
            result.add_issue(
                severity=Severity.WARNING,
                category=IssueCategory.MISSING_REQUIRED,
                message="Manifest name is empty"
            )
        
        # Validate schema version
        if manifest.schema_version and manifest.schema_version not in SUPPORTED_CDM_VERSIONS:
            result.add_issue(
                severity=Severity.INFO,
                category=IssueCategory.UNSUPPORTED_CONSTRUCT,
                message=f"Unknown CDM schema version: {manifest.schema_version}",
                recommendation="Schema may contain unsupported features"
            )
        
        # Track statistics
        result.statistics["entity_count"] = len(manifest.entities)
        result.statistics["relationship_count"] = len(manifest.relationships)
        
        # Validate entities
        for entity in manifest.entities:
            self._validate_entity(entity, result)
        
        # Validate relationships
        for relationship in manifest.relationships:
            self._validate_relationship(relationship, result)
        
        # Check for empty manifest
        if not manifest.entities:
            result.add_issue(
                severity=Severity.WARNING,
                category=IssueCategory.MISSING_REQUIRED,
                message="Manifest contains no entities"
            )
    
    def _validate_entity(self, entity: CDMEntity, result: ValidationResult) -> None:
        """
        Validate a single entity.
        
        Args:
            entity: CDMEntity to validate.
            result: ValidationResult to add issues to.
        """
        location = f"Entity: {entity.name}"
        
        # Validate entity name
        if not entity.name:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.MISSING_REQUIRED,
                message="Entity missing required 'name' field",
                location=location
            )
            return
        
        # Check for duplicate entity names
        if entity.name in self._entity_names:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.NAME_CONFLICT,
                message=f"Duplicate entity name: '{entity.name}'",
                location=location
            )
        self._entity_names.add(entity.name)
        
        # Validate entity name format
        self._validate_name(entity.name, "Entity", result, location)
        
        # Validate inheritance
        if entity.extends_entity:
            self._validate_inheritance(entity, result)
        
        # Validate attributes
        attr_names: Set[str] = set()
        for attribute in entity.attributes:
            self._validate_attribute(attribute, entity.name, attr_names, result)
        
        # Check for entities without attributes
        if not entity.attributes:
            result.add_issue(
                severity=Severity.INFO,
                category=IssueCategory.MISSING_REQUIRED,
                message=f"Entity '{entity.name}' has no attributes",
                location=location,
                recommendation="Consider adding at least an identifier attribute"
            )
        
        # Check for missing primary key
        has_pk = any(attr.is_primary_key for attr in entity.attributes)
        if not has_pk and entity.attributes:
            result.add_issue(
                severity=Severity.INFO,
                category=IssueCategory.MISSING_REQUIRED,
                message=f"Entity '{entity.name}' has no primary key attribute",
                location=location,
                recommendation="Consider marking an attribute with 'identifiedBy' purpose"
            )
    
    def _validate_attribute(
        self, 
        attribute: CDMAttribute, 
        entity_name: str,
        seen_names: Set[str],
        result: ValidationResult
    ) -> None:
        """
        Validate a single attribute.
        
        Args:
            attribute: CDMAttribute to validate.
            entity_name: Parent entity name.
            seen_names: Set of already seen attribute names.
            result: ValidationResult to add issues to.
        """
        location = f"Entity: {entity_name}, Attribute: {attribute.name}"
        
        # Validate attribute name
        if not attribute.name:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.MISSING_REQUIRED,
                message="Attribute missing required 'name' field",
                location=f"Entity: {entity_name}"
            )
            return
        
        # Check for duplicate attribute names
        if attribute.name in seen_names:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.NAME_CONFLICT,
                message=f"Duplicate attribute name: '{attribute.name}'",
                location=location
            )
        seen_names.add(attribute.name)
        
        # Validate attribute name format
        self._validate_name(attribute.name, "Attribute", result, location)
        
        # Validate data type
        self._validate_data_type(attribute.data_type, result, location)
        
        # Validate maximum length
        if attribute.maximum_length is not None:
            if attribute.maximum_length <= 0:
                result.add_issue(
                    severity=Severity.WARNING,
                    category=IssueCategory.CONSTRAINT_VIOLATION,
                    message=f"Invalid maximum length: {attribute.maximum_length}",
                    location=location
                )
            elif attribute.maximum_length > 1073741824:  # 1GB
                result.add_issue(
                    severity=Severity.WARNING,
                    category=IssueCategory.CONSTRAINT_VIOLATION,
                    message=f"Very large maximum length: {attribute.maximum_length}",
                    location=location,
                    recommendation="Consider if this length is necessary"
                )
    
    def _validate_data_type(
        self, 
        data_type: str, 
        result: ValidationResult, 
        location: str
    ) -> None:
        """
        Validate a CDM data type.
        
        Args:
            data_type: CDM data type name.
            result: ValidationResult to add issues to.
            location: Location string for error messages.
        """
        if not data_type:
            result.add_issue(
                severity=Severity.WARNING,
                category=IssueCategory.MISSING_REQUIRED,
                message="Attribute missing data type, will default to String",
                location=location
            )
            return
        
        # Check if type is supported
        if not self._type_mapper.is_supported_type(data_type):
            # Check if it's an entity reference
            if data_type.lower() in ('entity', 'entityid', 'entityreference'):
                result.add_issue(
                    severity=Severity.INFO,
                    category=IssueCategory.CONVERSION_LIMITATION,
                    message=f"Entity reference type '{data_type}' will be converted to String",
                    location=location,
                    recommendation="Consider modeling as explicit relationship"
                )
            else:
                result.add_issue(
                    severity=Severity.WARNING,
                    category=IssueCategory.UNSUPPORTED_CONSTRUCT,
                    message=f"Unknown data type '{data_type}' will default to String",
                    location=location
                )
    
    def _validate_relationship(self, relationship: CDMRelationship, result: ValidationResult) -> None:
        """
        Validate a relationship.
        
        Args:
            relationship: CDMRelationship to validate.
            result: ValidationResult to add issues to.
        """
        location = f"Relationship: {relationship.relationship_name}"
        
        # Validate required fields
        if not relationship.from_entity:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.MISSING_REQUIRED,
                message="Relationship missing 'fromEntity'",
                location=location
            )
        
        if not relationship.to_entity:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.MISSING_REQUIRED,
                message="Relationship missing 'toEntity'",
                location=location
            )
        
        # Validate entity references
        from_entity_name = relationship.from_entity_name
        to_entity_name = relationship.to_entity_name
        
        if from_entity_name and from_entity_name not in self._entity_names:
            # This might be okay if entities are loaded from external files
            result.add_issue(
                severity=Severity.INFO,
                category=IssueCategory.INVALID_REFERENCE,
                message=f"Relationship references unknown source entity: '{from_entity_name}'",
                location=location,
                recommendation="Ensure entity is defined or loaded from referenced file"
            )
        
        if to_entity_name and to_entity_name not in self._entity_names:
            result.add_issue(
                severity=Severity.INFO,
                category=IssueCategory.INVALID_REFERENCE,
                message=f"Relationship references unknown target entity: '{to_entity_name}'",
                location=location,
                recommendation="Ensure entity is defined or loaded from referenced file"
            )
        
        # Validate relationship name format
        rel_name = relationship.relationship_name
        if rel_name:
            self._validate_name(rel_name, "Relationship", result, location)
    
    def _validate_inheritance(self, entity: CDMEntity, result: ValidationResult) -> None:
        """
        Validate entity inheritance.
        
        Args:
            entity: CDMEntity with extends_entity set.
            result: ValidationResult to add issues to.
        """
        location = f"Entity: {entity.name}"
        base_entity = entity.extends_entity
        
        if not base_entity:
            return
        
        # Check for self-reference
        if base_entity == entity.name:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.CIRCULAR_REFERENCE,
                message=f"Entity '{entity.name}' cannot extend itself",
                location=location
            )
            return
        
        # Info about base entity (can't fully validate without loading)
        result.add_issue(
            severity=Severity.INFO,
            category=IssueCategory.EXTERNAL_DEPENDENCY,
            message=f"Entity '{entity.name}' extends '{base_entity}'",
            location=location,
            details="Inherited attributes will be flattened during conversion"
        )
    
    def _validate_name(
        self, 
        name: str, 
        item_type: str, 
        result: ValidationResult,
        location: str
    ) -> None:
        """
        Validate a name against Fabric naming rules.
        
        Args:
            name: Name to validate.
            item_type: Type of item (Entity, Attribute, Relationship).
            result: ValidationResult to add issues to.
            location: Location string for error messages.
        """
        # Check length
        if len(name) > FABRIC_MAX_NAME_LENGTH:
            result.add_issue(
                severity=Severity.ERROR,
                category=IssueCategory.NAME_TOO_LONG,
                message=f"{item_type} name exceeds maximum length ({len(name)} > {FABRIC_MAX_NAME_LENGTH})",
                location=location,
                recommendation=f"Shorten name to {FABRIC_MAX_NAME_LENGTH} characters or less"
            )
        
        # Check pattern (Fabric allows more flexibility, but warn about special chars)
        if not name[0].isalpha() and name[0] != '_':
            result.add_issue(
                severity=Severity.WARNING,
                category=IssueCategory.INVALID_CHARACTER,
                message=f"{item_type} name '{name}' should start with letter or underscore",
                location=location
            )
        
        # Check for spaces
        if ' ' in name:
            result.add_issue(
                severity=Severity.WARNING,
                category=IssueCategory.INVALID_CHARACTER,
                message=f"{item_type} name '{name}' contains spaces",
                location=location,
                recommendation="Consider using underscores instead of spaces"
            )
        
        # Check reserved names (info only)
        if name.lower() in RESERVED_NAMES:
            result.add_issue(
                severity=Severity.INFO,
                category=IssueCategory.NAME_CONFLICT,
                message=f"{item_type} name '{name}' may conflict with reserved names",
                location=location
            )
