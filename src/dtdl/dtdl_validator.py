"""
DTDL Validator

This module provides validation for DTDL documents and interfaces.
It checks for structural correctness, reference validity, and constraint violations.

Based on DTDL v4 specification:
https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v4/DTDL.v4.md
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from enum import Enum

from .dtdl_models import (
    DTDLInterface,
    DTDLProperty,
    DTDLTelemetry,
    DTDLRelationship,
    DTDLComponent,
    DTDLCommand,
    DTDLPrimitiveSchema,
    DTDLScaledDecimal,
)

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Severity level of validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class DTDLValidationError:
    """
    Represents a validation error or warning.
    
    Attributes:
        level: Severity (ERROR, WARNING, INFO)
        message: Description of the issue
        dtmi: DTMI of the affected element (if applicable)
        source_file: Source file (if applicable)
        field: Specific field with the issue (if applicable)
    """
    level: ValidationLevel
    message: str
    dtmi: Optional[str] = None
    source_file: Optional[str] = None
    field: Optional[str] = None
    
    def __str__(self) -> str:
        parts = [f"[{self.level.value.upper()}]"]
        if self.dtmi:
            parts.append(f"({self.dtmi})")
        parts.append(self.message)
        if self.field:
            parts.append(f"[field: {self.field}]")
        if self.source_file:
            parts.append(f"[file: {self.source_file}]")
        return " ".join(parts)


@dataclass
class ValidationResult:
    """Result of DTDL validation."""
    errors: List[DTDLValidationError] = field(default_factory=list)
    warnings: List[DTDLValidationError] = field(default_factory=list)
    info: List[DTDLValidationError] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0
    
    @property
    def all_issues(self) -> List[DTDLValidationError]:
        """Get all issues in priority order."""
        return self.errors + self.warnings + self.info
    
    def add(self, issue: DTDLValidationError) -> None:
        """Add a validation issue to the appropriate list."""
        if issue.level == ValidationLevel.ERROR:
            self.errors.append(issue)
        elif issue.level == ValidationLevel.WARNING:
            self.warnings.append(issue)
        else:
            self.info.append(issue)
    
    def get_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "Validation Summary:",
            f"  Errors: {len(self.errors)}",
            f"  Warnings: {len(self.warnings)}",
            f"  Info: {len(self.info)}",
        ]
        
        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors[:10]:
                lines.append(f"  - {err}")
            if len(self.errors) > 10:
                lines.append(f"  ... and {len(self.errors) - 10} more")
        
        if self.warnings:
            lines.append("\nWarnings:")
            for warn in self.warnings[:5]:
                lines.append(f"  - {warn}")
            if len(self.warnings) > 5:
                lines.append(f"  ... and {len(self.warnings) - 5} more")
        
        return "\n".join(lines)


class DTDLValidator:
    """
    Validates DTDL interfaces and documents.
    
    Performs checks for:
    - DTMI format validity
    - Required fields
    - Reference integrity (extends, targets, component schemas)
    - Constraint violations (name uniqueness, inheritance depth, etc.)
    - Schema validity
    
    Example usage:
        validator = DTDLValidator()
        result = validator.validate(interfaces)
        if result.is_valid:
            print("Validation passed!")
        else:
            for error in result.errors:
                print(error)
    """
    
    # DTMI format regex
    # Format: dtmi:<path>;<version> where path is segments separated by colons
    DTMI_PATTERN = re.compile(
        r'^dtmi:'  # Scheme
        r'[A-Za-z][A-Za-z0-9_]*'  # First path segment
        r'(:[A-Za-z_][A-Za-z0-9_]*)*'  # Additional path segments
        r'(;[1-9][0-9]{0,8}(\.[1-9][0-9]{0,5})?)?$'  # Optional version
    )
    
    # Property/content name pattern
    NAME_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9_]*[A-Za-z0-9]?$')
    
    # Limits from DTDL spec
    MAX_INTERFACE_DTMI_LENGTH = 128
    MAX_DTMI_LENGTH = 2048
    MAX_NAME_LENGTH = 512
    MAX_DESCRIPTION_LENGTH = 512
    MAX_COMMENT_LENGTH = 512
    MAX_EXTENDS_DEPTH = 12
    MAX_EXTENDS_HIERARCHY = 1024
    MAX_CONTENTS_COUNT = 100000
    MAX_COMPLEX_SCHEMA_DEPTH = 8
    
    # Valid primitive schemas
    PRIMITIVE_SCHEMAS = {s.value for s in DTDLPrimitiveSchema}
    
    def __init__(
        self,
        allow_external_references: bool = True,
        strict_mode: bool = False
    ):
        """
        Initialize the validator.
        
        Args:
            allow_external_references: If False, all referenced DTMIs must be defined
            strict_mode: If True, treat warnings as errors
        """
        self.allow_external_references = allow_external_references
        self.strict_mode = strict_mode
    
    def validate(self, interfaces: List[DTDLInterface]) -> ValidationResult:
        """
        Validate a list of DTDL interfaces.
        
        Args:
            interfaces: List of parsed interfaces to validate
            
        Returns:
            ValidationResult with all errors and warnings
        """
        result = ValidationResult()
        
        # Edge case: Empty input
        if not interfaces:
            result.add(DTDLValidationError(
                level=ValidationLevel.WARNING,
                message="No interfaces provided for validation",
            ))
            return result
        
        # Edge case: Large ontology warning
        if len(interfaces) > 500:
            result.add(DTDLValidationError(
                level=ValidationLevel.WARNING,
                message=f"Large ontology with {len(interfaces)} interfaces may take longer to process",
            ))
        
        # Build lookup tables
        interface_by_dtmi: Dict[str, DTDLInterface] = {}
        for interface in interfaces:
            if interface.dtmi in interface_by_dtmi:
                result.add(DTDLValidationError(
                    level=ValidationLevel.ERROR,
                    message=f"Duplicate DTMI: {interface.dtmi}",
                    dtmi=interface.dtmi,
                ))
            interface_by_dtmi[interface.dtmi] = interface
        
        # Validate each interface
        for interface in interfaces:
            self._validate_interface(interface, interface_by_dtmi, result)
        
        # Cross-interface validation
        self._validate_inheritance_graph(interfaces, interface_by_dtmi, result)
        
        # Edge case: Check for orphaned relationships (targets not in ontology)
        self._validate_relationship_targets(interfaces, interface_by_dtmi, result)
        
        # Edge case: Check for missing component schemas
        self._validate_component_schemas(interfaces, interface_by_dtmi, result)
        
        # Convert warnings to errors in strict mode
        if self.strict_mode:
            for warning in result.warnings:
                warning.level = ValidationLevel.ERROR
            result.errors.extend(result.warnings)
            result.warnings = []
        
        return result
    
    def _validate_interface(
        self,
        interface: DTDLInterface,
        all_interfaces: Dict[str, DTDLInterface],
        result: ValidationResult
    ) -> None:
        """Validate a single interface."""
        # Validate DTMI
        self._validate_dtmi(interface.dtmi, result, is_interface=True)
        
        # Validate @context
        if interface.context:
            if interface.context.dtdl_version not in [2, 3, 4]:
                result.add(DTDLValidationError(
                    level=ValidationLevel.ERROR,
                    message=f"Unsupported DTDL version: {interface.context.dtdl_version}",
                    dtmi=interface.dtmi,
                    field="@context",
                ))
        
        # Validate extends references
        for parent_dtmi in interface.extends:
            self._validate_dtmi(parent_dtmi, result)
            if parent_dtmi == interface.dtmi:
                result.add(DTDLValidationError(
                    level=ValidationLevel.ERROR,
                    message="Interface cannot extend itself",
                    dtmi=interface.dtmi,
                    field="extends",
                ))
            elif parent_dtmi not in all_interfaces:
                level = ValidationLevel.WARNING if self.allow_external_references else ValidationLevel.ERROR
                result.add(DTDLValidationError(
                    level=level,
                    message=f"Referenced parent interface not found: {parent_dtmi}",
                    dtmi=interface.dtmi,
                    field="extends",
                ))
        
        # Validate contents
        content_names: Set[str] = set()
        for content in interface.contents:
            self._validate_content(content, interface, all_interfaces, content_names, result)
        
        # Validate reusable schemas
        for schema in interface.schemas:
            self._validate_schema_definition(schema, interface.dtmi, result)
        
        # Validate string lengths
        if interface.display_name:
            dn = interface.display_name
            if isinstance(dn, str) and len(dn) > self.MAX_NAME_LENGTH:
                result.add(DTDLValidationError(
                    level=ValidationLevel.ERROR,
                    message=f"displayName exceeds {self.MAX_NAME_LENGTH} characters",
                    dtmi=interface.dtmi,
                    field="displayName",
                ))
        
        if interface.description:
            desc = interface.description
            if isinstance(desc, str) and len(desc) > self.MAX_DESCRIPTION_LENGTH:
                result.add(DTDLValidationError(
                    level=ValidationLevel.WARNING,
                    message=f"description exceeds {self.MAX_DESCRIPTION_LENGTH} characters",
                    dtmi=interface.dtmi,
                    field="description",
                ))
    
    def _validate_dtmi(
        self,
        dtmi: str,
        result: ValidationResult,
        is_interface: bool = False
    ) -> None:
        """Validate a DTMI format."""
        if not dtmi:
            result.add(DTDLValidationError(
                level=ValidationLevel.ERROR,
                message="DTMI is empty or None",
            ))
            return
        
        # Check length
        max_length = self.MAX_INTERFACE_DTMI_LENGTH if is_interface else self.MAX_DTMI_LENGTH
        if len(dtmi) > max_length:
            result.add(DTDLValidationError(
                level=ValidationLevel.ERROR,
                message=f"DTMI exceeds maximum length ({len(dtmi)} > {max_length})",
                dtmi=dtmi,
            ))
        
        # Check format
        if not self.DTMI_PATTERN.match(dtmi):
            result.add(DTDLValidationError(
                level=ValidationLevel.ERROR,
                message=f"Invalid DTMI format: {dtmi}",
                dtmi=dtmi,
            ))
        
        # Check for reserved prefixes
        if dtmi.startswith("dtmi:dtdl:") or dtmi.startswith("dtmi:standard:"):
            result.add(DTDLValidationError(
                level=ValidationLevel.WARNING,
                message=f"DTMI uses reserved prefix: {dtmi}",
                dtmi=dtmi,
            ))
    
    def _validate_content(
        self,
        content,
        interface: DTDLInterface,
        all_interfaces: Dict[str, DTDLInterface],
        used_names: Set[str],
        result: ValidationResult
    ) -> None:
        """Validate a content element (Property, Telemetry, etc.)."""
        # Get name attribute
        name = getattr(content, 'name', None)
        
        if name:
            # Check name uniqueness
            if name in used_names:
                result.add(DTDLValidationError(
                    level=ValidationLevel.ERROR,
                    message=f"Duplicate content name: {name}",
                    dtmi=interface.dtmi,
                    field="contents",
                ))
            used_names.add(name)
            
            # Validate name format
            if not self.NAME_PATTERN.match(name):
                result.add(DTDLValidationError(
                    level=ValidationLevel.ERROR,
                    message=f"Invalid content name format: {name}",
                    dtmi=interface.dtmi,
                    field=f"contents[{name}]",
                ))
            
            # Check name length
            if len(name) > self.MAX_NAME_LENGTH:
                result.add(DTDLValidationError(
                    level=ValidationLevel.ERROR,
                    message=f"Content name exceeds {self.MAX_NAME_LENGTH} characters: {name}",
                    dtmi=interface.dtmi,
                    field=f"contents[{name}]",
                ))
        
        # Validate @id if present
        dtmi = getattr(content, 'dtmi', None)
        if dtmi:
            self._validate_dtmi(dtmi, result)
        
        # Type-specific validation
        if isinstance(content, DTDLProperty):
            self._validate_schema(content.schema, interface.dtmi, result, f"Property[{name}].schema")
        
        elif isinstance(content, DTDLTelemetry):
            self._validate_schema(content.schema, interface.dtmi, result, f"Telemetry[{name}].schema")
        
        elif isinstance(content, DTDLRelationship):
            # Validate target reference
            if content.target:
                self._validate_dtmi(content.target, result)
                if not self.allow_external_references and content.target not in all_interfaces:
                    result.add(DTDLValidationError(
                        level=ValidationLevel.WARNING,
                        message=f"Relationship target not found: {content.target}",
                        dtmi=interface.dtmi,
                        field=f"Relationship[{name}].target",
                    ))
            
            # Validate multiplicity
            if content.max_multiplicity is not None and content.max_multiplicity < 1:
                result.add(DTDLValidationError(
                    level=ValidationLevel.ERROR,
                    message="maxMultiplicity must be >= 1",
                    dtmi=interface.dtmi,
                    field=f"Relationship[{name}].maxMultiplicity",
                ))
            
            # Validate relationship properties
            rel_prop_names: Set[str] = set()
            for prop in content.properties:
                if prop.name in rel_prop_names:
                    result.add(DTDLValidationError(
                        level=ValidationLevel.ERROR,
                        message=f"Duplicate property name in relationship: {prop.name}",
                        dtmi=interface.dtmi,
                        field=f"Relationship[{name}].properties",
                    ))
                rel_prop_names.add(prop.name)
        
        elif isinstance(content, DTDLComponent):
            # Validate component schema reference
            self._validate_dtmi(content.schema, result)
            if not self.allow_external_references and content.schema not in all_interfaces:
                result.add(DTDLValidationError(
                    level=ValidationLevel.ERROR,
                    message=f"Component schema not found: {content.schema}",
                    dtmi=interface.dtmi,
                    field=f"Component[{name}].schema",
                ))
        
        elif isinstance(content, DTDLCommand):
            # Validate request/response schemas
            if content.request:
                self._validate_schema(
                    content.request.schema,
                    interface.dtmi,
                    result,
                    f"Command[{name}].request.schema"
                )
            if content.response:
                self._validate_schema(
                    content.response.schema,
                    interface.dtmi,
                    result,
                    f"Command[{name}].response.schema"
                )
    
    def _validate_schema(
        self,
        schema,
        dtmi: str,
        result: ValidationResult,
        field: str
    ) -> None:
        """Validate a schema definition or reference."""
        if isinstance(schema, str):
            # Primitive type or DTMI reference
            if schema not in self.PRIMITIVE_SCHEMAS and not schema.startswith("dtmi:"):
                result.add(DTDLValidationError(
                    level=ValidationLevel.WARNING,
                    message=f"Unknown schema type: {schema}",
                    dtmi=dtmi,
                    field=field,
                ))
        elif isinstance(schema, DTDLScaledDecimal):
            # ScaledDecimal is a valid DTDL v4 schema type
            pass  # No additional validation needed
    
    def _validate_schema_definition(
        self,
        schema,
        interface_dtmi: str,
        result: ValidationResult
    ) -> None:
        """Validate a reusable schema definition."""
        # Schemas defined in Interface.schemas must have @id
        dtmi = getattr(schema, 'dtmi', None)
        if not dtmi:
            result.add(DTDLValidationError(
                level=ValidationLevel.ERROR,
                message="Schema in Interface.schemas must have @id",
                dtmi=interface_dtmi,
                field="schemas",
            ))
        else:
            self._validate_dtmi(dtmi, result)
    
    def _validate_inheritance_graph(
        self,
        interfaces: List[DTDLInterface],
        interface_by_dtmi: Dict[str, DTDLInterface],
        result: ValidationResult
    ) -> None:
        """
        Validate the inheritance graph for cycles and depth.
        
        DTDL allows max 12 levels of inheritance depth and max 1024 interfaces in hierarchy.
        """
        for interface in interfaces:
            # Check for cycles using DFS
            visited: Set[str] = set()
            path: List[str] = []
            
            def check_cycle(dtmi: str, depth: int) -> bool:
                if dtmi in path:
                    cycle = path[path.index(dtmi):] + [dtmi]
                    result.add(DTDLValidationError(
                        level=ValidationLevel.ERROR,
                        message=f"Inheritance cycle detected: {' -> '.join(cycle)}",
                        dtmi=interface.dtmi,
                        field="extends",
                    ))
                    return True
                
                if depth > self.MAX_EXTENDS_DEPTH:
                    result.add(DTDLValidationError(
                        level=ValidationLevel.ERROR,
                        message=f"Inheritance depth exceeds maximum ({self.MAX_EXTENDS_DEPTH})",
                        dtmi=interface.dtmi,
                        field="extends",
                    ))
                    return True
                
                if dtmi in visited:
                    return False
                
                visited.add(dtmi)
                path.append(dtmi)
                
                iface = interface_by_dtmi.get(dtmi)
                if iface:
                    for parent_dtmi in iface.extends:
                        if check_cycle(parent_dtmi, depth + 1):
                            return True
                
                path.pop()
                return False
            
            check_cycle(interface.dtmi, 0)
    
    def _validate_relationship_targets(
        self,
        interfaces: List[DTDLInterface],
        interface_by_dtmi: Dict[str, DTDLInterface],
        result: ValidationResult
    ) -> None:
        """
        Validate that relationship targets exist in the ontology.
        
        This is an edge case check that warns about relationships pointing
        to interfaces not included in the current ontology set.
        """
        external_targets: Dict[str, List[str]] = {}  # target_dtmi -> [source interfaces]
        
        for interface in interfaces:
            for rel in interface.relationships:
                if rel.target and rel.target not in interface_by_dtmi:
                    if rel.target not in external_targets:
                        external_targets[rel.target] = []
                    external_targets[rel.target].append(interface.dtmi)
        
        if external_targets and not self.allow_external_references:
            for target, sources in external_targets.items():
                result.add(DTDLValidationError(
                    level=ValidationLevel.WARNING,
                    message=f"Relationship target '{target}' not found in ontology. "
                           f"Referenced by: {', '.join(sources[:3])}"
                           + (f" and {len(sources)-3} more" if len(sources) > 3 else ""),
                    dtmi=target,
                ))
    
    def _validate_component_schemas(
        self,
        interfaces: List[DTDLInterface],
        interface_by_dtmi: Dict[str, DTDLInterface],
        result: ValidationResult
    ) -> None:
        """
        Validate that component schemas reference valid interfaces.
        
        This is an edge case check for components that reference schemas
        not included in the current ontology set.
        """
        missing_schemas: Dict[str, List[str]] = {}  # schema_dtmi -> [component names]
        
        for interface in interfaces:
            for component in interface.components:
                if component.schema not in interface_by_dtmi:
                    if component.schema not in missing_schemas:
                        missing_schemas[component.schema] = []
                    missing_schemas[component.schema].append(
                        f"{interface.name}.{component.name}"
                    )
        
        if missing_schemas and not self.allow_external_references:
            for schema, components in missing_schemas.items():
                result.add(DTDLValidationError(
                    level=ValidationLevel.WARNING,
                    message=f"Component schema '{schema}' not found in ontology. "
                           f"Used by: {', '.join(components[:3])}"
                           + (f" and {len(components)-3} more" if len(components) > 3 else ""),
                    dtmi=schema,
                ))
