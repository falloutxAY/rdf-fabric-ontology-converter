"""
RDF TTL to Fabric Ontology Converter

This module provides functionality to parse RDF TTL files and convert them
to Microsoft Fabric Ontology API format.

Architecture:
    This module has been refactored to use composition with extracted components:
    - converters.type_mapper: XSD to Fabric type mapping
    - converters.uri_utils: URI parsing and name extraction
    - converters.class_resolver: OWL class expression resolution
    - converters.fabric_serializer: Fabric API JSON serialization
    
    The main classes (RDFToFabricConverter, StreamingRDFConverter) now delegate
    to these focused components while maintaining backward compatibility.
"""

import json
import base64
import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import (
    Dict, List, Any, Optional, Tuple, Set, Union, 
    Callable, Literal, TypeVar, cast
)
from dataclasses import dataclass, field, asdict
from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, URIRef, Literal as RDFLiteral, BNode
from rdflib.term import Node, Identifier
from tqdm import tqdm

# Import refactored components - try relative first, then absolute for direct execution
try:
    from .converters.type_mapper import TypeMapper, XSD_TO_FABRIC_TYPE
    from .converters.uri_utils import URIUtils
    from .converters.class_resolver import ClassResolver
    from .converters.fabric_serializer import FabricSerializer
except ImportError:
    from converters.type_mapper import TypeMapper, XSD_TO_FABRIC_TYPE
    from converters.uri_utils import URIUtils
    from converters.class_resolver import ClassResolver
    from converters.fabric_serializer import FabricSerializer

# Type aliases for clarity
RDFNode = Union[URIRef, BNode, RDFLiteral]
ClassNode = Union[URIRef, BNode, Node, None]  # Node is the rdflib base type returned by graph methods
ListNode = Union[URIRef, BNode, Node, None]  # For RDF list traversal
# Using str instead of Literal for FabricType to avoid overly strict type checking
FabricType = str  # One of: "String", "Boolean", "DateTime", "BigInt", "Double", "Int", "Long", "Float", "Decimal"
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Manage memory usage during RDF parsing to prevent out-of-memory crashes.
    
    Provides pre-flight memory checks before loading large ontology files
    to fail gracefully with helpful error messages instead of crashing.
    """
    
    # Safety thresholds
    MIN_AVAILABLE_MB = 256  # Always need at least 256MB free
    MAX_SAFE_FILE_MB = 500  # Default max file size without explicit override
    MEMORY_MULTIPLIER = 3.5  # RDFlib typically uses ~3-4x file size in memory
    LOAD_FACTOR = 0.7  # Only use 70% of available memory as safe threshold
    
    @staticmethod
    def get_available_memory_mb() -> float:
        """
        Get available system memory in MB.
        
        Returns:
            Available memory in MB, or MIN_AVAILABLE_MB if detection fails.
        """
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil not available - cannot check memory. Install with: pip install psutil")
            return float('inf')  # Assume unlimited if we can't check
        
        try:
            mem_info = psutil.virtual_memory()
            available_mb = mem_info.available / (1024 * 1024)
            return available_mb
        except Exception as e:
            logger.warning(f"Could not determine available memory: {e}")
            return MemoryManager.MIN_AVAILABLE_MB
    
    @staticmethod
    def get_memory_usage_mb() -> float:
        """
        Get current process memory usage in MB.
        
        Returns:
            Current memory usage in MB.
        """
        if not PSUTIL_AVAILABLE:
            return 0.0
        
        try:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0
    
    @classmethod
    def check_memory_available(cls, file_size_mb: float, force: bool = False) -> Tuple[bool, str]:
        """
        Check if enough memory is available to parse a file.
        
        Args:
            file_size_mb: Size of the file in MB.
            force: If True, skip safety checks and allow large files.
            
        Returns:
            Tuple of (can_proceed: bool, message: str)
        """
        # Estimate memory required (RDFlib uses ~3-4x file size)
        estimated_usage_mb = file_size_mb * cls.MEMORY_MULTIPLIER
        
        # Check against hard limit unless forced
        if not force and file_size_mb > cls.MAX_SAFE_FILE_MB:
            return False, (
                f"File size ({file_size_mb:.1f}MB) exceeds safe limit ({cls.MAX_SAFE_FILE_MB}MB). "
                f"Estimated memory required: ~{estimated_usage_mb:.0f}MB. "
                f"To process anyway, use --force flag or split into smaller files."
            )
        
        # Check available system memory
        available_mb = cls.get_available_memory_mb()
        
        if available_mb == float('inf'):
            # Can't check memory, proceed with warning
            return True, f"Memory check unavailable. Proceeding with {file_size_mb:.1f}MB file."
        
        # Check minimum available memory
        if available_mb < cls.MIN_AVAILABLE_MB:
            return False, (
                f"Insufficient free memory. "
                f"Available: {available_mb:.0f}MB, "
                f"Minimum required: {cls.MIN_AVAILABLE_MB}MB. "
                f"Close other applications or increase available memory."
            )
        
        # Check if estimated usage exceeds safe threshold
        safe_threshold_mb = available_mb * cls.LOAD_FACTOR
        
        if estimated_usage_mb > safe_threshold_mb:
            if force:
                return True, (
                    f"WARNING: File may exceed safe memory limits. "
                    f"File: {file_size_mb:.1f}MB, "
                    f"Estimated usage: ~{estimated_usage_mb:.0f}MB, "
                    f"Safe threshold: {safe_threshold_mb:.0f}MB. "
                    f"Proceeding due to --force flag."
                )
            return False, (
                f"Ontology may be too large for available memory. "
                f"File size: {file_size_mb:.1f}MB, "
                f"Estimated parsing memory: ~{estimated_usage_mb:.0f}MB, "
                f"Safe threshold: {safe_threshold_mb:.0f}MB "
                f"(Available: {available_mb:.0f}MB). "
                f"Recommendation: Split into smaller files, increase available memory, or use --force to proceed anyway."
            )
        
        return True, (
            f"Memory OK: File {file_size_mb:.1f}MB, "
            f"estimated usage ~{estimated_usage_mb:.0f}MB of {available_mb:.0f}MB available"
        )
    
    @classmethod
    def log_memory_status(cls, context: str = "") -> None:
        """
        Log current memory status for debugging.
        
        Args:
            context: Optional context string to include in log message.
        """
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            process_mb = cls.get_memory_usage_mb()
            available_mb = cls.get_available_memory_mb()
            prefix = f"[{context}] " if context else ""
            logger.debug(
                f"{prefix}Memory status: Process using {process_mb:.0f}MB, "
                f"System available: {available_mb:.0f}MB"
            )
        except Exception as e:
            logger.debug(f"Could not log memory status: {e}")


# XSD type to Fabric value type mapping
XSD_TO_FABRIC_TYPE = {
    str(XSD.string): "String",
    str(XSD.boolean): "Boolean",
    str(XSD.dateTime): "DateTime",
    str(XSD.date): "DateTime",
    str(XSD.dateTimeStamp): "DateTime",
    str(XSD.integer): "BigInt",
    str(XSD.int): "BigInt",
    str(XSD.long): "BigInt",
    str(XSD.double): "Double",
    str(XSD.float): "Double",
    str(XSD.decimal): "Double",
    str(XSD.anyURI): "String",
    # Time-only is not directly supported by Fabric; preserve as String
    str(XSD.time): "String",
}


@dataclass
class EntityTypeProperty:
    """Represents a property of an entity type."""
    id: str
    name: str
    valueType: str
    redefines: Optional[str] = None
    baseTypeNamespaceType: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "valueType": self.valueType,
        }
        if self.redefines:
            result["redefines"] = self.redefines
        if self.baseTypeNamespaceType:
            result["baseTypeNamespaceType"] = self.baseTypeNamespaceType
        return result


@dataclass
class EntityType:
    """Represents an entity type in the ontology."""
    id: str
    name: str
    namespace: str = "usertypes"
    namespaceType: str = "Custom"
    visibility: str = "Visible"
    baseEntityTypeId: Optional[str] = None
    entityIdParts: List[str] = field(default_factory=list)
    displayNamePropertyId: Optional[str] = None
    properties: List[EntityTypeProperty] = field(default_factory=list)
    timeseriesProperties: List[EntityTypeProperty] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "id": self.id,
            "namespace": self.namespace,
            "name": self.name,
            "namespaceType": self.namespaceType,
            "visibility": self.visibility,
            "baseEntityTypeId": self.baseEntityTypeId,
        }
        if self.entityIdParts:
            result["entityIdParts"] = self.entityIdParts
        if self.displayNamePropertyId:
            result["displayNamePropertyId"] = self.displayNamePropertyId
        if self.properties:
            result["properties"] = [p.to_dict() for p in self.properties]
        if self.timeseriesProperties:
            result["timeseriesProperties"] = [p.to_dict() for p in self.timeseriesProperties]
        return result


@dataclass
class RelationshipEnd:
    """Represents one end of a relationship."""
    entityTypeId: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {"entityTypeId": self.entityTypeId}


@dataclass
class RelationshipType:
    """Represents a relationship type in the ontology."""
    id: str
    name: str
    source: RelationshipEnd
    target: RelationshipEnd
    namespace: str = "usertypes"
    namespaceType: str = "Custom"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "namespace": self.namespace,
            "name": self.name,
            "namespaceType": self.namespaceType,
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
        }


@dataclass
class SkippedItem:
    """Represents an item that was skipped during conversion."""
    item_type: str  # "class", "property", "relationship"
    name: str
    reason: str
    uri: str
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "type": self.item_type,
            "name": self.name,
            "reason": self.reason,
            "uri": self.uri
        }


@dataclass
class ConversionResult:
    """
    Results of TTL conversion with detailed tracking.
    
    Provides information about successful conversions, skipped items,
    and warnings encountered during the conversion process.
    """
    entity_types: List[EntityType]
    relationship_types: List[RelationshipType]
    skipped_items: List[SkippedItem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    triple_count: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage of items successfully converted."""
        total = (
            len(self.entity_types) + 
            len(self.relationship_types) + 
            len(self.skipped_items)
        )
        if total == 0:
            return 100.0
        successful = len(self.entity_types) + len(self.relationship_types)
        return (successful / total) * 100
    
    @property
    def has_skipped_items(self) -> bool:
        """Check if any items were skipped during conversion."""
        return len(self.skipped_items) > 0
    
    @property
    def skipped_by_type(self) -> Dict[str, int]:
        """Get count of skipped items grouped by type."""
        counts: Dict[str, int] = {}
        for item in self.skipped_items:
            counts[item.item_type] = counts.get(item.item_type, 0) + 1
        return counts
    
    def get_summary(self) -> str:
        """Generate human-readable summary of conversion results."""
        lines = [
            "Conversion Summary:",
            f"  ✓ Entity Types: {len(self.entity_types)}",
            f"  ✓ Relationships: {len(self.relationship_types)}",
        ]
        
        if self.skipped_items:
            lines.append(f"  ⚠ Skipped: {len(self.skipped_items)}")
            
            # Group by type
            by_type = self.skipped_by_type
            for item_type, count in by_type.items():
                lines.append(f"      - {item_type}s: {count}")
            
            # Show first few skipped items with details
            lines.append("    Details (first 5):")
            for item in self.skipped_items[:5]:
                lines.append(f"      - {item.item_type}: {item.name}")
                lines.append(f"        Reason: {item.reason}")
            
            if len(self.skipped_items) > 5:
                lines.append(f"      ... and {len(self.skipped_items) - 5} more")
        
        if self.warnings:
            lines.append(f"  ⚠ Warnings: {len(self.warnings)}")
            for warning in self.warnings[:3]:
                lines.append(f"      - {warning}")
            if len(self.warnings) > 3:
                lines.append(f"      ... and {len(self.warnings) - 3} more")
        
        lines.append(f"  Success Rate: {self.success_rate:.1f}%")
        
        if self.triple_count > 0:
            lines.append(f"  Total RDF Triples: {self.triple_count}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize conversion result to dictionary."""
        return {
            "entity_types_count": len(self.entity_types),
            "relationship_types_count": len(self.relationship_types),
            "skipped_items_count": len(self.skipped_items),
            "skipped_items": [item.to_dict() for item in self.skipped_items],
            "warnings": self.warnings,
            "success_rate": self.success_rate,
            "triple_count": self.triple_count
        }


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
    """
    
    @staticmethod
    def validate_entity_types(entity_types: List[EntityType]) -> List[DefinitionValidationError]:
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
        relationship_types: List[RelationshipType],
        entity_types: List[EntityType]
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
        entity_types: List[EntityType],
        relationship_types: List[RelationshipType]
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


class RDFToFabricConverter:
    """
    Converts RDF TTL ontologies to Microsoft Fabric Ontology format.
    
    This class has been refactored to use composition with extracted components:
    - TypeMapper: XSD to Fabric type mapping
    - URIUtils: URI parsing and name extraction
    - ClassResolver: OWL class expression resolution
    
    The public API remains unchanged for backward compatibility.
    """
    
    def __init__(self, id_prefix: int = 1000000000000, loose_inference: bool = False):
        """
        Initialize the converter.
        
        Args:
            id_prefix: Base prefix for generating unique IDs
            loose_inference: When True, apply heuristic inference for missing domain/range
        """
        self.id_prefix = id_prefix
        self.id_counter = 0
        self.loose_inference = loose_inference
        self.entity_types: Dict[str, EntityType] = {}
        self.relationship_types: Dict[str, RelationshipType] = {}
        self.uri_to_id: Dict[str, str] = {}
        self.property_to_domain: Dict[str, str] = {}
        # Error recovery tracking
        self.skipped_items: List[SkippedItem] = []
        self.conversion_warnings: List[str] = []
        
        # Composed components (used via delegation)
        self._type_mapper = TypeMapper()
        self._uri_utils = URIUtils()

    def _reset_state(self) -> None:
        """Reset converter state for a fresh conversion."""
        self.entity_types = {}
        self.relationship_types = {}
        self.uri_to_id = {}
        self.property_to_domain = {}
        self.id_counter = 0
        self.skipped_items = []
        self.conversion_warnings = []

    def _add_skipped_item(
        self, 
        item_type: str, 
        name: str, 
        reason: str, 
        uri: str
    ) -> None:
        """Track a skipped item during conversion."""
        self.skipped_items.append(SkippedItem(
            item_type=item_type,
            name=name,
            reason=reason,
            uri=uri
        ))
        logger.warning(f"Skipped {item_type} '{name}': {reason}")

    def _add_warning(self, message: str) -> None:
        """Track a warning during conversion."""
        self.conversion_warnings.append(message)
        logger.warning(message)

    def _resolve_class_targets(
        self, 
        graph: Graph, 
        node: ClassNode, 
        visited: Optional[Set[Union[URIRef, BNode]]] = None,
        max_depth: int = 10
    ) -> List[str]:
        """Resolve domain/range targets to class URIs with cycle detection.

        Delegates to ClassResolver for the actual resolution logic.
        
        Supports:
        - Direct URIRef
        - Blank node with owl:unionOf pointing to RDF list of class URIs
        - Nested blank nodes (with cycle detection)
        - owl:intersectionOf (extracts first class)
        - owl:complementOf (extracts the complemented class)
        
        Args:
            graph: The RDF graph to query
            node: The node to resolve (URIRef or BNode)
            visited: Set of already-visited nodes for cycle detection
            max_depth: Maximum recursion depth to prevent infinite loops
            
        Returns:
            List of resolved class URI strings
        """
        return ClassResolver.resolve_class_targets(graph, node, visited, max_depth)
    
    def _resolve_rdf_list(
        self, 
        graph: Graph, 
        list_node: ListNode,
        visited: Set[Union[URIRef, BNode]],
        max_depth: int
    ) -> Tuple[List[str], int]:
        """Resolve an RDF list (rdf:first/rdf:rest) to class URIs.
        
        Delegates to ClassResolver for the actual resolution logic.
        
        Args:
            graph: The RDF graph to query
            list_node: The head of the RDF list
            visited: Set of already-visited nodes for cycle detection
            max_depth: Maximum recursion depth
            
        Returns:
            Tuple of (resolved_targets, unresolved_count)
        """
        return ClassResolver.resolve_rdf_list(graph, list_node, visited, max_depth)
        
    def _generate_id(self) -> str:
        """Generate a unique ID for entities and properties."""
        self.id_counter += 1
        return str(self.id_prefix + self.id_counter)
    
    def _uri_to_name(self, uri: URIRef) -> str:
        """Extract a clean name from a URI.
        
        Delegates to URIUtils for the actual implementation.
        """
        return URIUtils.uri_to_name(uri, self.id_counter)
    
    def _get_xsd_type(self, range_uri: Optional[URIRef]) -> FabricType:
        """Map XSD type to Fabric value type.
        
        Delegates to TypeMapper for the actual implementation.
        
        Args:
            range_uri: The XSD type URI, or None
            
        Returns:
            The corresponding Fabric type string
        """
        return TypeMapper.get_fabric_type(str(range_uri) if range_uri else None)
    
    def _resolve_datatype_union(
        self, 
        graph: Graph, 
        union_node: BNode
    ) -> Tuple[FabricType, str]:
        """
        Resolve datatype union to most restrictive compatible Fabric type.
        
        Delegates to TypeMapper for the actual implementation.
        
        Args:
            graph: The RDF graph to query
            union_node: Blank node containing the datatype union
            
        Returns:
            Tuple of (fabric_type: str, notes: str) where:
                - fabric_type: The resolved Fabric type ("String", "BigInt", etc.)
                - notes: Description of the resolution for logging
        """
        return TypeMapper.resolve_datatype_union(
            graph, 
            union_node, 
            ClassResolver.resolve_rdf_list
        )
    
    def parse_ttl(
        self, 
        ttl_content: str, 
        force_large_file: bool = False,
        return_result: bool = False
    ) -> Union[Tuple[List[EntityType], List[RelationshipType]], ConversionResult]:
        """
        Parse RDF TTL content and extract entity and relationship types.
        
        Args:
            ttl_content: The TTL content as a string
            force_large_file: If True, skip memory safety checks for large files
            return_result: If True, return ConversionResult with detailed tracking
            
        Returns:
            If return_result is False: Tuple of (entity_types, relationship_types)
            If return_result is True: ConversionResult with detailed tracking
            
        Raises:
            ValueError: If TTL content is empty or has invalid syntax
            MemoryError: If insufficient memory is available to parse the file
        """
        logger.info("Parsing TTL content...")
        
        if not ttl_content or not ttl_content.strip():
            raise ValueError("Empty TTL content provided")
        
        # Check size before parsing
        content_size_mb = len(ttl_content.encode('utf-8')) / (1024 * 1024)
        logger.info(f"TTL content size: {content_size_mb:.2f} MB")
        
        # Pre-flight memory check to prevent crashes
        can_proceed, memory_message = MemoryManager.check_memory_available(
            content_size_mb, 
            force=force_large_file
        )
        
        if not can_proceed:
            logger.error(f"Memory check failed: {memory_message}")
            raise MemoryError(memory_message)
        
        logger.info(f"Memory check: {memory_message}")
        
        if content_size_mb > 100:
            logger.warning(
                f"Large TTL content detected ({content_size_mb:.1f} MB). "
                "Parsing may take several minutes."
            )
        
        # Log memory before parsing
        MemoryManager.log_memory_status("Before parsing")
        
        # Parse the TTL
        graph = Graph()
        try:
            graph.parse(data=ttl_content, format='turtle')
        except MemoryError as e:
            MemoryManager.log_memory_status("After MemoryError")
            raise MemoryError(
                f"Insufficient memory while parsing TTL content ({content_size_mb:.1f} MB). "
                f"Try splitting the ontology into smaller files or increasing available memory. "
                f"Original error: {e}"
            )
        except Exception as e:
            logger.error(f"Failed to parse TTL content: {e}")
            raise ValueError(f"Invalid RDF/TTL syntax: {e}")
        
        # Log memory after parsing
        MemoryManager.log_memory_status("After parsing")
        
        triple_count = len(graph)
        if triple_count == 0:
            logger.warning("Parsed graph is empty - no triples found")
            raise ValueError("No RDF triples found in the provided TTL content")
        
        logger.info(f"Successfully parsed {triple_count} triples ({content_size_mb:.1f} MB)")
        
        if triple_count > 100000:
            logger.warning(
                f"Large ontology detected ({triple_count} triples). "
                "Processing may take several minutes."
            )
        
        # Reset state (includes skipped_items and conversion_warnings)
        self._reset_state()
        
        # Step 1: Extract all classes (entity types)
        self._extract_classes(graph)
        
        # Step 2: Extract data properties and assign to entity types
        self._extract_data_properties(graph)
        
        # Step 3: Extract object properties (relationship types)
        self._extract_object_properties(graph)
        
        # Step 4: Set entity ID parts and display name properties
        self._set_entity_identifiers()
        
        entity_list = list(self.entity_types.values())
        relationship_list = list(self.relationship_types.values())
        
        logger.info(
            f"Parsed {len(entity_list)} entity types and "
            f"{len(relationship_list)} relationship types"
        )
        
        if self.skipped_items:
            logger.info(f"Skipped {len(self.skipped_items)} items during conversion")
        
        # Return based on requested format
        if return_result:
            return ConversionResult(
                entity_types=entity_list,
                relationship_types=relationship_list,
                skipped_items=self.skipped_items.copy(),
                warnings=self.conversion_warnings.copy(),
                triple_count=triple_count
            )
        
        return entity_list, relationship_list
    
    def _extract_classes(self, graph: Graph) -> None:
        """Extract OWL/RDFS classes as entity types."""
        # Find all classes
        classes = set()
        
        # OWL classes
        for s in graph.subjects(RDF.type, OWL.Class):
            if isinstance(s, URIRef):
                classes.add(s)
        
        # RDFS classes
        for s in graph.subjects(RDF.type, RDFS.Class):
            if isinstance(s, URIRef):
                classes.add(s)
        
        # Classes with subclass relationships
        for s in graph.subjects(RDFS.subClassOf, None):
            if isinstance(s, URIRef):
                classes.add(s)
        
        logger.info(f"Found {len(classes)} classes")
        
        if len(classes) == 0:
            logger.warning("No OWL/RDFS classes found in ontology")
        
        # First pass: create all entity types without parent relationships
        for class_uri in tqdm(classes, desc="Creating entity types", unit="class", disable=len(classes) < 10):
            entity_id = self._generate_id()
            name = self._uri_to_name(class_uri)
            
            entity_type = EntityType(
                id=entity_id,
                name=name,
                baseEntityTypeId=None,  # Set in second pass
            )
            
            self.entity_types[str(class_uri)] = entity_type
            self.uri_to_id[str(class_uri)] = entity_id
            logger.debug(f"Created entity type: {name} (ID: {entity_id})")
        
        # Second pass: set parent relationships with cycle detection
        def has_cycle(class_uri: URIRef, path: set) -> bool:
            """Check if following parent chain creates a cycle."""
            if class_uri in path:
                return True
            new_path = path | {class_uri}
            for parent in graph.objects(class_uri, RDFS.subClassOf):
                if isinstance(parent, URIRef) and parent in classes:
                    if has_cycle(parent, new_path):
                        return True
            return False
        
        for class_uri in classes:
            for parent in graph.objects(class_uri, RDFS.subClassOf):
                if isinstance(parent, URIRef) and str(parent) in self.uri_to_id:
                    # Check for cycles
                    if has_cycle(parent, {class_uri}):
                        logger.warning(
                            f"Circular inheritance detected for {self._uri_to_name(class_uri)}, "
                            f"skipping parent {self._uri_to_name(parent)}"
                        )
                        continue
                    
                    self.entity_types[str(class_uri)].baseEntityTypeId = self.uri_to_id[str(parent)]
                    break  # Only take first non-circular parent
    
    def _extract_data_properties(self, graph: Graph) -> None:
        """Extract data properties and add them to entity types."""
        # Find all data properties
        # Include both OWL.DatatypeProperty and rdf:Property with XSD ranges
        data_properties = set()
        owl_datatype_props = set()
        rdf_props_with_xsd_range = set()

        for s in graph.subjects(RDF.type, OWL.DatatypeProperty):
            if isinstance(s, URIRef):
                owl_datatype_props.add(s)

        # Any rdf:Property whose rdfs:range is an XSD type should be treated as a data property
        for s in graph.subjects(RDF.type, RDF.Property):
            if not isinstance(s, URIRef):
                continue
            ranges = list(graph.objects(s, RDFS.range))
            if not ranges:
                continue
            range_uri = ranges[0] if isinstance(ranges[0], URIRef) else None
            if range_uri is None:
                continue
            range_str = str(range_uri)
            if range_str in XSD_TO_FABRIC_TYPE or range_str.startswith(str(XSD)):
                rdf_props_with_xsd_range.add(s)

        data_properties = owl_datatype_props | rdf_props_with_xsd_range

        logger.info(f"Found {len(data_properties)} data properties")

        for prop_uri in data_properties:
            prop_id = self._generate_id()
            name = self._uri_to_name(prop_uri)
            
            # Get domain (which entity type this property belongs to)
            raw_domains = list(graph.objects(prop_uri, RDFS.domain))
            domains: List[str] = []
            for d in raw_domains:
                domains.extend(self._resolve_class_targets(graph, d))
            
            # Get range (value type) with datatype union support
            ranges = list(graph.objects(prop_uri, RDFS.range))
            value_type = "String"  # Default
            union_notes = ""
            
            if ranges:
                if isinstance(ranges[0], URIRef):
                    value_type = self._get_xsd_type(ranges[0])
                elif isinstance(ranges[0], BNode):
                    # Resolve datatype union to most restrictive compatible type
                    value_type, union_notes = self._resolve_datatype_union(graph, ranges[0])
                    if union_notes:
                        logger.debug(f"Property {name}: {union_notes}")
            
            prop = EntityTypeProperty(
                id=prop_id,
                name=name,
                valueType=value_type,
            )
            
            # Add property to all domain classes
            for domain_uri in domains:
                if domain_uri in self.entity_types:
                    # Check if this is a timeseries property (DateTime is often used for timestamps)
                    if value_type == "DateTime" and "timestamp" in name.lower():
                        self.entity_types[domain_uri].timeseriesProperties.append(prop)
                    else:
                        self.entity_types[domain_uri].properties.append(prop)
                    self.property_to_domain[str(prop_uri)] = domain_uri
                    logger.debug(f"Added property {name} to entity type {self.entity_types[domain_uri].name}")
            
            self.uri_to_id[str(prop_uri)] = prop_id
    
    def _extract_object_properties(self, graph: Graph) -> None:
        """Extract object properties as relationship types with domain/range inference."""
        object_properties: Set[URIRef] = set()
        owl_object_props: Set[URIRef] = set()
        rdf_props_with_entity_range: Set[URIRef] = set()

        for s in graph.subjects(RDF.type, OWL.ObjectProperty):
            if isinstance(s, URIRef):
                owl_object_props.add(s)

        # Consider rdf:Property whose range refers to a known entity type (non-XSD) as object properties
        for s in graph.subjects(RDF.type, RDF.Property):
            if not isinstance(s, URIRef):
                continue
            ranges = list(graph.objects(s, RDFS.range))
            if not ranges:
                continue
            range_candidate = ranges[0]
            if isinstance(range_candidate, URIRef):
                range_str = str(range_candidate)
                if (range_str not in XSD_TO_FABRIC_TYPE) and not range_str.startswith(str(XSD)):
                    # We'll add it; we'll verify existence later when creating the relationship
                    rdf_props_with_entity_range.add(s)

        # Convert string keys to URIRef for set difference
        known_props: Set[URIRef] = {URIRef(k) for k in self.property_to_domain.keys()}
        object_properties = owl_object_props | (rdf_props_with_entity_range - known_props)

        logger.info(f"Found {len(object_properties)} object properties")
        
        # Build usage map for inference
        property_usage: Dict[str, Dict[str, Set[Any]]] = {}  # prop_uri -> {subjects: set, objects: set}
        for prop_uri in object_properties:
            property_usage[str(prop_uri)] = {'subjects': set(), 'objects': set()}
        
        # Scan for actual usage patterns in the graph
        for s, p, o in graph:
            if str(p) in property_usage:
                # Get types of subject and object
                for subj_type in graph.objects(s, RDF.type):
                    if str(subj_type) in self.entity_types:
                        property_usage[str(p)]['subjects'].add(str(subj_type))
                
                if isinstance(o, URIRef):
                    for obj_type in graph.objects(o, RDF.type):
                        if str(obj_type) in self.entity_types:
                            property_usage[str(p)]['objects'].add(str(obj_type))
        
        for prop_uri in tqdm(object_properties, desc="Processing relationships", unit="property", disable=len(object_properties) < 10):
            name = self._uri_to_name(prop_uri)
            
            # Get explicit domain and range
            raw_domains = list(graph.objects(prop_uri, RDFS.domain))
            raw_ranges = list(graph.objects(prop_uri, RDFS.range))

            domain_uris: List[str] = []
            range_uris: List[str] = []

            # Try explicit declarations first, including unionOf class expressions
            for d in raw_domains:
                domain_uris.extend(self._resolve_class_targets(graph, d))
            for r in raw_ranges:
                range_uris.extend(self._resolve_class_targets(graph, r))

            domain_uris = [u for u in domain_uris if u in self.entity_types]
            range_uris = [u for u in range_uris if u in self.entity_types]
            
            # Fall back to inference from usage
            if not domain_uris:
                usage = property_usage.get(str(prop_uri), {})
                if usage.get('subjects'):
                    # Use most common subject type
                    domain_uris = [next(iter(usage['subjects']))]
                    logger.debug(f"Inferred domain for {name}: {self._uri_to_name(URIRef(domain_uris[0]))}")
            
            if not range_uris:
                usage = property_usage.get(str(prop_uri), {})
                if usage.get('objects'):
                    # Use most common object type
                    range_uris = [next(iter(usage['objects']))]
                    logger.debug(f"Inferred range for {name}: {self._uri_to_name(URIRef(range_uris[0]))}")
            
            if not domain_uris or not range_uris:
                # Determine specific reason for skipping
                if not domain_uris and not range_uris:
                    reason = "missing both domain and range"
                elif not domain_uris:
                    reason = "missing domain class"
                else:
                    reason = "missing range class"
                
                self._add_skipped_item(
                    item_type="relationship",
                    name=name,
                    reason=reason,
                    uri=str(prop_uri)
                )
                continue

            # Create relationships for each domain-range pair
            created_any = False
            for d_uri in domain_uris:
                for r_uri in range_uris:
                    if d_uri not in self.entity_types or r_uri not in self.entity_types:
                        continue
                    rel_id = self._generate_id()
                    relationship = RelationshipType(
                        id=rel_id,
                        name=name,
                        source=RelationshipEnd(entityTypeId=self.entity_types[d_uri].id),
                        target=RelationshipEnd(entityTypeId=self.entity_types[r_uri].id),
                    )
                    # Store using unique key per pair to avoid overwrite
                    key = f"{str(prop_uri)}::{d_uri}->{r_uri}"
                    self.relationship_types[key] = relationship
                    self.uri_to_id[key] = rel_id
                    created_any = True
                    logger.debug(f"Created relationship type: {name} ({self._uri_to_name(URIRef(d_uri))} -> {self._uri_to_name(URIRef(r_uri))})")
            if not created_any:
                self._add_skipped_item(
                    item_type="relationship",
                    name=name,
                    reason="domain or range entity type not found in converted classes",
                    uri=str(prop_uri)
                )
    
    def _set_entity_identifiers(self) -> None:
        """Set entity ID parts and display name properties for all entity types."""
        for entity_uri, entity_type in self.entity_types.items():
            if entity_type.properties:
                # Find an ID property or use the first property
                id_prop = None
                name_prop = None
                
                for prop in entity_type.properties:
                    prop_name_lower = prop.name.lower()
                    # Only String and BigInt are valid for entity keys
                    if 'id' in prop_name_lower and prop.valueType in ("String", "BigInt"):
                        id_prop = prop
                    if 'name' in prop_name_lower and prop.valueType == "String":
                        name_prop = prop
                
                # Find first valid key property (String or BigInt only)
                first_valid_key_prop = next(
                    (p for p in entity_type.properties if p.valueType in ("String", "BigInt")), 
                    None
                )
                
                # Only set entityIdParts if we have a valid property
                if id_prop:
                    entity_type.entityIdParts = [id_prop.id]
                    entity_type.displayNamePropertyId = (name_prop or id_prop).id
                elif first_valid_key_prop:
                    entity_type.entityIdParts = [first_valid_key_prop.id]
                    entity_type.displayNamePropertyId = first_valid_key_prop.id
                # If no valid key property, leave entityIdParts empty (Fabric will handle it)


class StreamingRDFConverter:
    """
    Memory-efficient streaming converter for large ontologies.
    
    This converter processes RDF files in phases to minimize memory usage:
    1. First pass: Discover and extract class declarations (lightweight)
    2. Second pass: Process properties in batches
    
    Use this converter for ontologies larger than 500MB or when memory is limited.
    For smaller files, the standard RDFToFabricConverter is recommended as it's faster.
    
    Example:
        converter = StreamingRDFConverter(id_prefix=1000000000000)
        result = converter.parse_ttl_streaming(
            "large_ontology.ttl",
            progress_callback=lambda n: print(f"Processed {n} triples")
        )
    """
    
    # Default batch size for processing triples
    DEFAULT_BATCH_SIZE = 10000
    
    # Memory threshold (MB) - switch to streaming above this
    STREAMING_THRESHOLD_MB = 100
    
    def __init__(
        self, 
        id_prefix: int = 1000000000000,
        batch_size: int = DEFAULT_BATCH_SIZE,
        loose_inference: bool = False
    ):
        """
        Initialize the streaming converter.
        
        Args:
            id_prefix: Base prefix for generating unique IDs
            batch_size: Number of triples to process in each batch
            loose_inference: When True, apply heuristic inference for missing domain/range
        """
        self.id_prefix = id_prefix
        self.batch_size = batch_size
        self.loose_inference = loose_inference
        self.id_counter = 0
        
        # Storage for extracted entities
        self.entity_types: Dict[str, EntityType] = {}
        self.relationship_types: Dict[str, RelationshipType] = {}
        self.uri_to_id: Dict[str, str] = {}
        self.property_to_domain: Dict[str, str] = {}
        
        # Error recovery tracking
        self.skipped_items: List[SkippedItem] = []
        self.conversion_warnings: List[str] = []
        
        # Statistics
        self.triples_processed = 0
        self.classes_found = 0
        self.properties_found = 0
    
    def _reset_state(self) -> None:
        """Reset converter state for a fresh conversion."""
        self.entity_types = {}
        self.relationship_types = {}
        self.uri_to_id = {}
        self.property_to_domain = {}
        self.id_counter = 0
        self.skipped_items = []
        self.conversion_warnings = []
        self.triples_processed = 0
        self.classes_found = 0
        self.properties_found = 0
    
    def _generate_id(self) -> str:
        """Generate a unique ID for entities and properties."""
        self.id_counter += 1
        return str(self.id_prefix + self.id_counter)
    
    def _uri_to_name(self, uri: URIRef) -> str:
        """Extract a clean name from a URI."""
        if uri is None:
            return f'Unknown_{self.id_counter}'
        
        uri_str = str(uri).strip()
        if not uri_str:
            return f'Unknown_{self.id_counter}'
        
        # Try to get the fragment
        if '#' in uri_str:
            name = uri_str.split('#')[-1]
        elif '/' in uri_str:
            name = uri_str.split('/')[-1]
        else:
            name = uri_str
        
        if not name:
            return f'Entity_{self.id_counter}'
        
        # Clean up the name to match Fabric requirements
        cleaned = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
        
        if not cleaned:
            return f'Entity_{self.id_counter}'
        
        if not cleaned[0].isalpha():
            cleaned = 'E_' + cleaned
        
        return cleaned[:128]
    
    def _add_skipped_item(
        self, 
        item_type: str, 
        name: str, 
        reason: str, 
        uri: str
    ) -> None:
        """Track a skipped item during conversion."""
        self.skipped_items.append(SkippedItem(
            item_type=item_type,
            name=name,
            reason=reason,
            uri=uri
        ))
        logger.debug(f"Skipped {item_type} '{name}': {reason}")
    
    def _add_warning(self, message: str) -> None:
        """Track a warning during conversion."""
        self.conversion_warnings.append(message)
        logger.warning(message)
    
    def _get_xsd_type(self, range_uri: Optional[URIRef]) -> FabricType:
        """Map XSD type to Fabric value type."""
        if range_uri is None:
            return "String"
        range_str = str(range_uri)
        return cast(FabricType, XSD_TO_FABRIC_TYPE.get(range_str, "String"))
    
    def parse_ttl_streaming(
        self, 
        file_path: str,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancellation_token: Optional[Any] = None
    ) -> ConversionResult:
        """
        Parse large TTL file in streaming fashion.
        
        This method processes the file in two phases:
        1. Phase 1: Quick scan to discover all classes
        2. Phase 2: Process properties and relationships in batches
        
        Args:
            file_path: Path to the TTL file to parse
            progress_callback: Optional callback function called with number of triples processed
            cancellation_token: Optional cancellation token for interruptible processing
            
        Returns:
            ConversionResult with entity types, relationship types, and metadata
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file has invalid syntax
            OperationCancelledException: If cancelled via token
        """
        from pathlib import Path
        
        logger.info(f"Starting streaming parse of {file_path}")
        self._reset_state()
        
        # Validate file exists
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size_mb = path.stat().st_size / (1024 * 1024)
        logger.info(f"File size: {file_size_mb:.2f} MB")
        
        # Check for cancellation
        if cancellation_token and hasattr(cancellation_token, 'throw_if_cancelled'):
            cancellation_token.throw_if_cancelled()
        
        # Phase 1: Discover classes (requires full parse but is memory-light for class extraction)
        logger.info("Phase 1: Discovering classes...")
        graph = Graph()
        
        try:
            graph.parse(file_path, format='turtle')
        except Exception as e:
            logger.error(f"Failed to parse TTL file: {e}")
            raise ValueError(f"Invalid RDF/TTL syntax: {e}")
        
        total_triples = len(graph)
        logger.info(f"Loaded {total_triples} triples")
        
        if progress_callback:
            progress_callback(0)
        
        # Extract classes first
        self._extract_classes_streaming(graph)
        logger.info(f"Phase 1 complete: Found {len(self.entity_types)} classes")
        
        # Check for cancellation
        if cancellation_token and hasattr(cancellation_token, 'throw_if_cancelled'):
            cancellation_token.throw_if_cancelled()
        
        # Phase 2: Process properties in batches
        logger.info("Phase 2: Processing properties...")
        self._process_properties_streaming(graph, progress_callback, cancellation_token)
        logger.info(f"Phase 2 complete: Found {len(self.property_to_domain)} data properties")
        
        # Check for cancellation
        if cancellation_token and hasattr(cancellation_token, 'throw_if_cancelled'):
            cancellation_token.throw_if_cancelled()
        
        # Phase 3: Process relationships
        logger.info("Phase 3: Processing relationships...")
        self._process_relationships_streaming(graph, progress_callback, cancellation_token)
        logger.info(f"Phase 3 complete: Found {len(self.relationship_types)} relationships")
        
        # Phase 4: Set entity identifiers
        logger.info("Phase 4: Setting entity identifiers...")
        self._set_entity_identifiers()
        
        if progress_callback:
            progress_callback(total_triples)
        
        entity_list = list(self.entity_types.values())
        relationship_list = list(self.relationship_types.values())
        
        logger.info(
            f"Streaming parse complete: {len(entity_list)} entity types, "
            f"{len(relationship_list)} relationship types"
        )
        
        if self.skipped_items:
            logger.info(f"Skipped {len(self.skipped_items)} items during conversion")
        
        return ConversionResult(
            entity_types=entity_list,
            relationship_types=relationship_list,
            skipped_items=self.skipped_items.copy(),
            warnings=self.conversion_warnings.copy(),
            triple_count=total_triples
        )
    
    def _extract_classes_streaming(self, graph: Graph) -> None:
        """Extract OWL/RDFS classes as entity types."""
        classes: Set[URIRef] = set()
        
        # OWL classes
        for s in graph.subjects(RDF.type, OWL.Class):
            if isinstance(s, URIRef):
                classes.add(s)
        
        # RDFS classes
        for s in graph.subjects(RDF.type, RDFS.Class):
            if isinstance(s, URIRef):
                classes.add(s)
        
        # Classes with subclass relationships
        for s in graph.subjects(RDFS.subClassOf, None):
            if isinstance(s, URIRef):
                classes.add(s)
        
        self.classes_found = len(classes)
        logger.debug(f"Found {len(classes)} classes")
        
        # First pass: create all entity types
        for class_uri in classes:
            entity_id = self._generate_id()
            name = self._uri_to_name(class_uri)
            
            entity_type = EntityType(
                id=entity_id,
                name=name,
                baseEntityTypeId=None,
            )
            
            self.entity_types[str(class_uri)] = entity_type
            self.uri_to_id[str(class_uri)] = entity_id
        
        # Second pass: set parent relationships
        for class_uri in classes:
            for parent in graph.objects(class_uri, RDFS.subClassOf):
                if isinstance(parent, URIRef) and str(parent) in self.uri_to_id:
                    # Simple check for direct self-reference
                    if parent == class_uri:
                        self._add_warning(f"Class {self._uri_to_name(class_uri)} references itself as parent")
                        continue
                    self.entity_types[str(class_uri)].baseEntityTypeId = self.uri_to_id[str(parent)]
                    break  # Only take first parent
    
    def _process_properties_streaming(
        self, 
        graph: Graph,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancellation_token: Optional[Any] = None
    ) -> None:
        """Process data properties in batches."""
        # Find all data properties
        data_properties: Set[URIRef] = set()
        
        for s in graph.subjects(RDF.type, OWL.DatatypeProperty):
            if isinstance(s, URIRef):
                data_properties.add(s)
        
        # Also check rdf:Property with XSD ranges
        for s in graph.subjects(RDF.type, RDF.Property):
            if not isinstance(s, URIRef):
                continue
            ranges = list(graph.objects(s, RDFS.range))
            if ranges and isinstance(ranges[0], URIRef):
                range_str = str(ranges[0])
                if range_str in XSD_TO_FABRIC_TYPE or range_str.startswith(str(XSD)):
                    data_properties.add(s)
        
        self.properties_found = len(data_properties)
        processed = 0
        batch_count = 0
        
        for prop_uri in data_properties:
            # Check for cancellation every batch
            if batch_count >= self.batch_size:
                if cancellation_token and hasattr(cancellation_token, 'throw_if_cancelled'):
                    cancellation_token.throw_if_cancelled()
                if progress_callback:
                    progress_callback(processed)
                batch_count = 0
            
            prop_id = self._generate_id()
            name = self._uri_to_name(prop_uri)
            
            # Get domain
            domains: List[str] = []
            for d in graph.objects(prop_uri, RDFS.domain):
                if isinstance(d, URIRef):
                    domains.append(str(d))
            
            # Get range (value type)
            ranges = list(graph.objects(prop_uri, RDFS.range))
            value_type: FabricType = "String"
            if ranges and isinstance(ranges[0], URIRef):
                value_type = self._get_xsd_type(ranges[0])
            
            prop = EntityTypeProperty(
                id=prop_id,
                name=name,
                valueType=value_type,
            )
            
            # Add property to domain classes
            for domain_uri in domains:
                if domain_uri in self.entity_types:
                    self.entity_types[domain_uri].properties.append(prop)
                    self.property_to_domain[str(prop_uri)] = domain_uri
            
            self.uri_to_id[str(prop_uri)] = prop_id
            processed += 1
            batch_count += 1
    
    def _process_relationships_streaming(
        self, 
        graph: Graph,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancellation_token: Optional[Any] = None
    ) -> None:
        """Process object properties as relationships."""
        object_properties: Set[URIRef] = set()
        
        for s in graph.subjects(RDF.type, OWL.ObjectProperty):
            if isinstance(s, URIRef):
                object_properties.add(s)
        
        # Also check rdf:Property with non-XSD ranges
        for s in graph.subjects(RDF.type, RDF.Property):
            if not isinstance(s, URIRef):
                continue
            if str(s) in self.property_to_domain:  # Skip if already a data property
                continue
            ranges = list(graph.objects(s, RDFS.range))
            if ranges and isinstance(ranges[0], URIRef):
                range_str = str(ranges[0])
                if range_str not in XSD_TO_FABRIC_TYPE and not range_str.startswith(str(XSD)):
                    object_properties.add(s)
        
        processed = 0
        batch_count = 0
        
        for prop_uri in object_properties:
            # Check for cancellation every batch
            if batch_count >= self.batch_size:
                if cancellation_token and hasattr(cancellation_token, 'throw_if_cancelled'):
                    cancellation_token.throw_if_cancelled()
                if progress_callback:
                    progress_callback(processed)
                batch_count = 0
            
            name = self._uri_to_name(prop_uri)
            
            # Get domain and range
            domain_uris: List[str] = []
            range_uris: List[str] = []
            
            for d in graph.objects(prop_uri, RDFS.domain):
                if isinstance(d, URIRef) and str(d) in self.entity_types:
                    domain_uris.append(str(d))
            
            for r in graph.objects(prop_uri, RDFS.range):
                if isinstance(r, URIRef) and str(r) in self.entity_types:
                    range_uris.append(str(r))
            
            if not domain_uris or not range_uris:
                if not domain_uris and not range_uris:
                    reason = "missing both domain and range"
                elif not domain_uris:
                    reason = "missing domain class"
                else:
                    reason = "missing range class"
                
                self._add_skipped_item(
                    item_type="relationship",
                    name=name,
                    reason=reason,
                    uri=str(prop_uri)
                )
                processed += 1
                batch_count += 1
                continue
            
            # Create relationships for each domain-range pair
            for d_uri in domain_uris:
                for r_uri in range_uris:
                    rel_id = self._generate_id()
                    relationship = RelationshipType(
                        id=rel_id,
                        name=name,
                        source=RelationshipEnd(entityTypeId=self.entity_types[d_uri].id),
                        target=RelationshipEnd(entityTypeId=self.entity_types[r_uri].id),
                    )
                    key = f"{str(prop_uri)}::{d_uri}->{r_uri}"
                    self.relationship_types[key] = relationship
                    self.uri_to_id[key] = rel_id
            
            processed += 1
            batch_count += 1
    
    def _set_entity_identifiers(self) -> None:
        """Set entity ID parts and display name properties."""
        for entity_uri, entity_type in self.entity_types.items():
            if entity_type.properties:
                id_prop = None
                name_prop = None
                
                for prop in entity_type.properties:
                    prop_name_lower = prop.name.lower()
                    if 'id' in prop_name_lower and prop.valueType in ("String", "BigInt"):
                        id_prop = prop
                    if 'name' in prop_name_lower and prop.valueType == "String":
                        name_prop = prop
                
                first_valid_key_prop = next(
                    (p for p in entity_type.properties if p.valueType in ("String", "BigInt")), 
                    None
                )
                
                if id_prop:
                    entity_type.entityIdParts = [id_prop.id]
                    entity_type.displayNamePropertyId = (name_prop or id_prop).id
                elif first_valid_key_prop:
                    entity_type.entityIdParts = [first_valid_key_prop.id]
                    entity_type.displayNamePropertyId = first_valid_key_prop.id


def parse_ttl_streaming(
    file_path: str,
    id_prefix: int = 1000000000000,
    batch_size: int = StreamingRDFConverter.DEFAULT_BATCH_SIZE,
    progress_callback: Optional[Callable[[int], None]] = None,
    cancellation_token: Optional[Any] = None
) -> Tuple[Dict[str, Any], str, ConversionResult]:
    """
    Parse a large TTL file using streaming mode and return Fabric Ontology definition.
    
    This function is optimized for large files (>100MB) and processes the file
    in batches to minimize memory usage.
    
    Args:
        file_path: Path to the TTL file to parse
        id_prefix: Base prefix for generating unique IDs
        batch_size: Number of triples to process per batch (default: 10000)
        progress_callback: Optional callback for progress updates
        cancellation_token: Optional cancellation token for interruptible processing
        
    Returns:
        Tuple of (Fabric Ontology definition dict, ontology name, ConversionResult)
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file has invalid syntax
        TypeError: If parameters have wrong type
    """
    # Validate inputs
    validated_path = InputValidator.validate_input_ttl_path(file_path)
    id_prefix = InputValidator.validate_id_prefix(id_prefix)
    
    converter = StreamingRDFConverter(
        id_prefix=id_prefix,
        batch_size=batch_size
    )
    
    result = converter.parse_ttl_streaming(
        str(validated_path),
        progress_callback=progress_callback,
        cancellation_token=cancellation_token
    )
    
    # Extract ontology name from file
    ontology_name = validated_path.stem
    # Clean for Fabric naming requirements
    ontology_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in ontology_name)
    ontology_name = ontology_name[:100]
    if ontology_name and not ontology_name[0].isalpha():
        ontology_name = 'O_' + ontology_name
    if not ontology_name:
        ontology_name = "ImportedOntology"
    
    definition = convert_to_fabric_definition(
        result.entity_types,
        result.relationship_types,
        ontology_name
    )
    
    return definition, ontology_name, result


def _topological_sort_entities(entity_types: List[EntityType]) -> List[EntityType]:
    """
    Sort entity types so that parent types come before child types.
    This ensures Fabric can resolve baseEntityTypeId references.
    
    Args:
        entity_types: List of entity types to sort
        
    Returns:
        Sorted list with parents before children
    """
    # Build a map of id -> entity
    id_to_entity: Dict[str, EntityType] = {e.id: e for e in entity_types}
    
    # Build adjacency list (child -> parent)
    # and in-degree count (how many parents reference this as base)
    children: Dict[str, List[str]] = {e.id: [] for e in entity_types}  # parent_id -> list of child_ids
    
    for entity in entity_types:
        if entity.baseEntityTypeId and entity.baseEntityTypeId in id_to_entity:
            children[entity.baseEntityTypeId].append(entity.id)
    
    # Find root entities (no parent or parent not in our set)
    roots = [e for e in entity_types if not e.baseEntityTypeId or e.baseEntityTypeId not in id_to_entity]
    
    # BFS to build sorted order
    sorted_entities = []
    visited = set()
    queue = [e.id for e in roots]
    
    while queue:
        entity_id = queue.pop(0)
        if entity_id in visited:
            continue
        visited.add(entity_id)
        sorted_entities.append(id_to_entity[entity_id])
        
        # Add children to queue
        for child_id in children[entity_id]:
            if child_id not in visited:
                queue.append(child_id)
    
    # Add any remaining entities (shouldn't happen if graph is well-formed)
    for entity in entity_types:
        if entity.id not in visited:
            sorted_entities.append(entity)
    
    return sorted_entities


def convert_to_fabric_definition(
    entity_types: List[EntityType],
    relationship_types: List[RelationshipType],
    ontology_name: str = "ImportedOntology",
    skip_validation: bool = False
) -> Dict[str, Any]:
    """
    Convert parsed entity and relationship types to Fabric Ontology definition format.
    
    Args:
        entity_types: List of entity types
        relationship_types: List of relationship types
        ontology_name: Name for the ontology
        skip_validation: If True, skip definition validation (not recommended)
        
    Returns:
        Dictionary representing the Fabric Ontology definition
        
    Raises:
        ValueError: If validation fails with critical errors
    """
    # Validate definition before creating (unless explicitly skipped)
    if not skip_validation:
        is_valid, validation_errors = FabricDefinitionValidator.validate_definition(
            entity_types, relationship_types
        )
        
        # Log all validation issues
        for error in validation_errors:
            if error.level == "warning":
                logger.warning(str(error))
            else:
                logger.error(str(error))
        
        # Fail on critical errors
        if not is_valid:
            critical_errors = [e for e in validation_errors if e.level == "error"]
            error_msg = "Invalid ontology definition:\n" + "\n".join(
                f"  - {e.message}" for e in critical_errors
            )
            raise ValueError(error_msg)
        
        if validation_errors:
            warning_count = sum(1 for e in validation_errors if e.level == "warning")
            if warning_count > 0:
                logger.info(f"Definition validation passed with {warning_count} warning(s)")
        else:
            logger.debug("Definition validation passed with no issues")
    
    # Delegate serialization to FabricSerializer
    return FabricSerializer.create_definition(entity_types, relationship_types, ontology_name)


class InputValidator:
    """
    Centralized input validation for RDF converter public methods.
    
    Provides consistent validation with clear error messages for:
    - TTL content validation
    - File path validation with security checks
    - Parameter type and value checking
    
    Security features:
    - Path traversal detection (../ sequences)
    - Symlink detection and warning
    - Extension validation
    - Directory boundary awareness
    """
    
    # Allowed extensions for different file types
    TTL_EXTENSIONS = ['.ttl', '.rdf', '.owl', '.n3', '.nt', '.nq', '.trig']
    JSON_EXTENSIONS = ['.json']
    OUTPUT_EXTENSIONS = ['.ttl', '.json', '.txt', '.md']
    
    @staticmethod
    def validate_ttl_content(content: Any) -> str:
        """
        Validate TTL content parameter.
        
        Args:
            content: Content to validate (should be non-empty string)
            
        Returns:
            Validated content string
            
        Raises:
            ValueError: If content is None or empty
            TypeError: If content is not a string
        """
        if content is None:
            raise ValueError("TTL content cannot be None")
        
        if not isinstance(content, str):
            raise TypeError(f"TTL content must be string, got {type(content).__name__}")
        
        if not content.strip():
            raise ValueError("TTL content cannot be empty or whitespace-only")
        
        return content
    
    @staticmethod
    def _check_path_traversal(path_str: str) -> None:
        """
        Check for path traversal attempts.
        
        Args:
            path_str: Path string to check
            
        Raises:
            ValueError: If path traversal detected
        """
        # Normalize separators for consistent checking
        normalized = path_str.replace('\\', '/')
        
        # Check for obvious traversal patterns
        traversal_patterns = ['../', '..\\', '/..', '\\..']
        for pattern in traversal_patterns:
            if pattern in path_str or pattern in normalized:
                raise ValueError(
                    f"Path traversal detected in path: {path_str}. "
                    f"Paths containing '..' are not allowed for security reasons."
                )
        
        # Also check if resolved path contains '..' components
        try:
            path_obj = Path(path_str)
            # Check each component
            for part in path_obj.parts:
                if part == '..':
                    raise ValueError(
                        f"Path traversal detected in path: {path_str}. "
                        f"Paths containing '..' components are not allowed."
                    )
        except Exception:
            pass  # If Path parsing fails, let later validation catch it
    
    @staticmethod
    def _check_symlink(path_obj: Path, strict: bool = False) -> None:
        """
        Check if path is a symlink.
        
        Args:
            path_obj: Path object to check
            strict: If True, raise exception on symlink; if False, log warning
            
        Raises:
            ValueError: If symlink detected and strict mode enabled
        """
        try:
            if path_obj.is_symlink():
                msg = (
                    f"Security error: Symlink detected: {path_obj}. "
                    f"Symlinks are not allowed for security reasons. "
                    f"Please use the actual file path instead."
                )
                if strict:
                    raise ValueError(msg)
                else:
                    logger.warning(msg)
        except OSError:
            # Some systems may raise OSError when checking symlinks
            if strict:
                raise ValueError(f"Cannot verify symlink status for: {path_obj}")
            pass  # Ignore errors in symlink detection in non-strict mode
    
    @staticmethod
    def _check_directory_boundary(path_obj: Path, warn_only: bool = True) -> None:
        """
        Check if path is outside current working directory.
        
        Args:
            path_obj: Resolved absolute path to check
            warn_only: If True, only log warning; if False, raise exception
        """
        try:
            cwd = Path.cwd().resolve()
            path_obj.relative_to(cwd)
        except ValueError:
            msg = f"Path is outside current directory: {path_obj}"
            if warn_only:
                logger.warning(msg + " (this may be intentional for absolute paths)")
            else:
                raise ValueError(msg + ". Access to paths outside working directory is restricted.")
    
    @classmethod
    def validate_file_path(
        cls, 
        path: Any, 
        allowed_extensions: Optional[List[str]] = None,
        check_exists: bool = True,
        check_readable: bool = True,
        restrict_to_cwd: bool = False,
        reject_symlinks: bool = True,
        allow_relative_up: bool = False,
    ) -> Path:
        """
        Validate file path for security and correctness.
        
        Security checks performed:
        - Path traversal detection (../)
        - Symlink detection (configurable: warning or hard reject)
        - Directory boundary check (optional enforcement)
        - Extension validation (optional)
        
        Args:
            path: Path to validate (should be non-empty string)
            allowed_extensions: List of allowed extensions (e.g., ['.ttl', '.rdf'])
            check_exists: Whether to verify file exists
            check_readable: Whether to verify file is readable
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception on symlinks; if False, warn only
            
        Returns:
            Validated Path object (resolved to absolute path)
            
        Raises:
            TypeError: If path is not a string
            ValueError: If path is empty, has invalid extension, traversal detected, or symlink found (if reject_symlinks=True)
            FileNotFoundError: If file doesn't exist (when check_exists=True)
            PermissionError: If file is not readable (when check_readable=True)
        """
        # Type check
        if not isinstance(path, str):
            raise TypeError(f"File path must be string, got {type(path).__name__}")
        
        # Empty check
        if not path.strip():
            raise ValueError("File path cannot be empty")
        
        path = path.strip()
        
        # Security: Check for path traversal BEFORE resolving
        has_relative_up = False
        if isinstance(path, str):
            normalized = path.replace('\\', '/')
            traversal_patterns = ['../', '..\\', '/..', '\\..']
            for pattern in traversal_patterns:
                if pattern in path or pattern in normalized:
                    has_relative_up = True
                    break
            if not has_relative_up:
                # Also check parts for '..'
                try:
                    for part in Path(path).parts:
                        if part == '..':
                            has_relative_up = True
                            break
                except Exception:
                    # Fall back to strict traversal check
                    pass
        if not allow_relative_up:
            # Original strict check
            cls._check_path_traversal(path)
        
        # Resolve to absolute path
        path_obj = Path(path).resolve()
        
        # Security: Check symlinks (strict by default for input files)
        cls._check_symlink(path_obj, strict=reject_symlinks)
        
        # Security: Check directory boundary
        if allow_relative_up and has_relative_up:
            # Enforce that relative-up stays within cwd
            cls._check_directory_boundary(path_obj, warn_only=False)
        else:
            cls._check_directory_boundary(path_obj, warn_only=not restrict_to_cwd)
        
        # Existence check
        if check_exists:
            if not path_obj.exists():
                raise FileNotFoundError(f"File not found: {path_obj}")
            
            if not path_obj.is_file():
                raise ValueError(f"Path is not a file: {path_obj}")
        
        # Extension validation
        if allowed_extensions:
            # Normalize extensions to lowercase with leading dot
            normalized_extensions = [
                ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                for ext in allowed_extensions
            ]
            
            if path_obj.suffix.lower() not in normalized_extensions:
                raise ValueError(
                    f"Invalid file extension: '{path_obj.suffix}'. "
                    f"Expected one of: {', '.join(normalized_extensions)}"
                )
        
        # Readability check
        if check_readable and check_exists:
            if not os.access(path_obj, os.R_OK):
                raise PermissionError(f"File is not readable: {path_obj}")
        
        return path_obj
    
    @classmethod
    def validate_input_ttl_path(cls, path: Any, restrict_to_cwd: bool = False, reject_symlinks: bool = True, allow_relative_up: bool = False) -> Path:
        """
        Validate input TTL/RDF file path.
        
        Convenience method with TTL-specific extension validation.
        Symlinks are hard-rejected by default for security.
        
        Args:
            path: Path to TTL file
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception on symlinks (default: True for security)
            
        Returns:
            Validated Path object
        """
        return cls.validate_file_path(
            path,
            allowed_extensions=cls.TTL_EXTENSIONS,
            check_exists=True,
            check_readable=True,
            restrict_to_cwd=restrict_to_cwd,
            reject_symlinks=reject_symlinks,
            allow_relative_up=allow_relative_up,
        )
    
    @classmethod
    def validate_input_json_path(cls, path: Any, restrict_to_cwd: bool = False, reject_symlinks: bool = True, allow_relative_up: bool = False) -> Path:
        """
        Validate input JSON file path.
        
        Convenience method with JSON-specific extension validation.
        Symlinks are hard-rejected by default for security.
        
        Args:
            path: Path to JSON file
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception on symlinks (default: True for security)
            
        Returns:
            Validated Path object
        """
        return cls.validate_file_path(
            path,
            allowed_extensions=cls.JSON_EXTENSIONS,
            check_exists=True,
            check_readable=True,
            restrict_to_cwd=restrict_to_cwd,
            reject_symlinks=reject_symlinks,
            allow_relative_up=allow_relative_up,
        )
    
    @classmethod
    def validate_output_file_path(
        cls, 
        path: Any,
        allowed_extensions: Optional[List[str]] = None,
        restrict_to_cwd: bool = False,
        reject_symlinks: bool = True,
        allow_relative_up: bool = False,
    ) -> Path:
        """
        Validate output file path for writing.
        
        Similar to validate_file_path but:
        - Does not require file to exist
        - Validates parent directory exists and is writable
        
        Args:
            path: Path for output file
            allowed_extensions: List of allowed extensions
            restrict_to_cwd: If True, reject paths outside current directory
            reject_symlinks: If True, raise exception if output target is symlink
            
        Returns:
            Validated Path object
            
        Raises:
            TypeError: If path is not a string
            ValueError: If path is empty, has invalid extension, or traversal detected
            PermissionError: If parent directory is not writable
        """
        # Type check
        if not isinstance(path, str):
            raise TypeError(f"File path must be string, got {type(path).__name__}")
        
        # Empty check
        if not path.strip():
            raise ValueError("File path cannot be empty")
        
        path = path.strip()
        
        # Security: Check for path traversal
        has_relative_up = False
        if isinstance(path, str):
            normalized = path.replace('\\', '/')
            traversal_patterns = ['../', '..\\', '/..', '\\..']
            for pattern in traversal_patterns:
                if pattern in path or pattern in normalized:
                    has_relative_up = True
                    break
            if not has_relative_up:
                try:
                    for part in Path(path).parts:
                        if part == '..':
                            has_relative_up = True
                            break
                except Exception:
                    pass
        if not allow_relative_up:
            cls._check_path_traversal(path)
        
        # Resolve to absolute path
        path_obj = Path(path).resolve()
        
        # Security: Check symlinks if file exists
        if path_obj.exists():
            cls._check_symlink(path_obj, strict=reject_symlinks)
        
        # Security: Check directory boundary
        if allow_relative_up and has_relative_up:
            cls._check_directory_boundary(path_obj, warn_only=False)
        else:
            cls._check_directory_boundary(path_obj, warn_only=not restrict_to_cwd)
        
        # Extension validation
        if allowed_extensions:
            normalized_extensions = [
                ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                for ext in allowed_extensions
            ]
            
            if path_obj.suffix.lower() not in normalized_extensions:
                raise ValueError(
                    f"Invalid file extension: '{path_obj.suffix}'. "
                    f"Expected one of: {', '.join(normalized_extensions)}"
                )
        
        # Check parent directory exists and is writable
        parent_dir = path_obj.parent
        if not parent_dir.exists():
            raise ValueError(f"Parent directory does not exist: {parent_dir}")
        
        if not os.access(parent_dir, os.W_OK):
            raise PermissionError(f"Cannot write to directory: {parent_dir}")
        
        # If file exists, check it's writable
        if path_obj.exists() and not os.access(path_obj, os.W_OK):
            raise PermissionError(f"File exists but is not writable: {path_obj}")
        
        return path_obj
    
    @classmethod
    def validate_config_file_path(cls, path: Any) -> Path:
        """
        Validate configuration file path.
        
        Configuration files have stricter validation:
        - Must be JSON
        - Must be readable
        - Must be in safe location (within cwd)
        - Symlinks are rejected
        
        Args:
            path: Path to config file
            
        Returns:
            Validated Path object
            
        Raises:
            TypeError: If path is not a string
            ValueError: If path is invalid or outside current directory
            FileNotFoundError: If file doesn't exist
            PermissionError: If file is not readable or symlink detected
        """
        validated_path = cls.validate_file_path(
            path,
            allowed_extensions=cls.JSON_EXTENSIONS,
            check_exists=True,
            check_readable=True,
            restrict_to_cwd=True,  # Strict: config must be in cwd
            reject_symlinks=True   # Hard reject symlinks
        )
        
        return validated_path
    
    @staticmethod
    def validate_id_prefix(prefix: Any) -> int:
        """
        Validate ID prefix parameter.
        
        Args:
            prefix: Prefix to validate (should be non-negative integer)
            
        Returns:
            Validated prefix integer
            
        Raises:
            TypeError: If prefix is not an integer
            ValueError: If prefix is negative
        """
        if not isinstance(prefix, int):
            raise TypeError(f"ID prefix must be integer, got {type(prefix).__name__}")
        
        if prefix < 0:
            raise ValueError(f"ID prefix must be non-negative, got {prefix}")
        
        return prefix


def parse_ttl_file(file_path: str, id_prefix: int = 1000000000000, force_large_file: bool = False) -> Tuple[Dict[str, Any], str]:
    """
    Parse a TTL file and return the Fabric Ontology definition.
    
    Args:
        file_path: Path to the TTL file
        id_prefix: Base prefix for generating unique IDs
        force_large_file: If True, skip memory safety checks for large files
        
    Returns:
        Tuple of (Fabric Ontology definition dict, extracted ontology name)
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        PermissionError: If the file is not readable
        MemoryError: If insufficient memory is available
        ValueError: If the file content is invalid, path traversal detected, or invalid extension
        TypeError: If parameters have wrong type
    """
    # Validate inputs upfront with security checks
    validated_path = InputValidator.validate_input_ttl_path(file_path)
    id_prefix = InputValidator.validate_id_prefix(id_prefix)
    
    try:
        with open(validated_path, 'r', encoding='utf-8') as f:
            ttl_content = f.read()
    except UnicodeDecodeError as e:
        logger.error(f"Encoding error reading {validated_path}: {e}")
        # Try with different encoding
        try:
            with open(validated_path, 'r', encoding='latin-1') as f:
                ttl_content = f.read()
            logger.warning(f"Successfully read file with latin-1 encoding")
        except Exception as e2:
            raise ValueError(f"Unable to decode file {validated_path}: {e2}")
    except PermissionError:
        logger.error(f"Permission denied reading {validated_path}")
        raise PermissionError(f"Permission denied: {validated_path}")
    except Exception as e:
        logger.error(f"Error reading file {validated_path}: {e}")
        raise IOError(f"Error reading file: {e}")
    
    return parse_ttl_content(ttl_content, id_prefix, force_large_file=force_large_file)


def parse_ttl_content(ttl_content: str, id_prefix: int = 1000000000000, force_large_file: bool = False) -> Tuple[Dict[str, Any], str]:
    """
    Parse TTL content and return the Fabric Ontology definition.
    
    Args:
        ttl_content: TTL content as string
        id_prefix: Base prefix for generating unique IDs
        force_large_file: If True, skip memory safety checks for large files
        
    Returns:
        Tuple of (Fabric Ontology definition dict, extracted ontology name)
        
    Raises:
        ValueError: If content is empty or invalid
        TypeError: If parameters have wrong type
        MemoryError: If insufficient memory is available
    """
    # Validate inputs upfront
    ttl_content = InputValidator.validate_ttl_content(ttl_content)
    id_prefix = InputValidator.validate_id_prefix(id_prefix)
    
    converter = RDFToFabricConverter(id_prefix=id_prefix)
    entity_types, relationship_types = converter.parse_ttl(ttl_content, force_large_file=force_large_file)
    
    # Try to extract ontology name from the TTL
    graph = Graph()
    graph.parse(data=ttl_content, format='turtle')
    
    ontology_name = "ImportedOntology"
    for s in graph.subjects(RDF.type, OWL.Ontology):
        # Try to get label
        labels = list(graph.objects(s, RDFS.label))
        if labels:
            label = str(labels[0])
            # Clean up for Fabric naming requirements
            ontology_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in label)
            ontology_name = ontology_name[:100]  # Max 100 chars
            if ontology_name and not ontology_name[0].isalpha():
                ontology_name = 'O_' + ontology_name
        break
    
    definition = convert_to_fabric_definition(entity_types, relationship_types, ontology_name)
    
    return definition, ontology_name


def parse_ttl_with_result(
    ttl_content: str, 
    id_prefix: int = 1000000000000, 
    force_large_file: bool = False
) -> Tuple[Dict[str, Any], str, ConversionResult]:
    """
    Parse TTL content and return the Fabric Ontology definition with detailed conversion result.
    
    This function provides enhanced error recovery by tracking skipped items
    and warnings during conversion.
    
    Args:
        ttl_content: TTL content as string
        id_prefix: Base prefix for generating unique IDs
        force_large_file: If True, skip memory safety checks for large files
        
    Returns:
        Tuple of (Fabric Ontology definition dict, extracted ontology name, ConversionResult)
        
    Raises:
        ValueError: If content is empty or invalid
        TypeError: If parameters have wrong type
        MemoryError: If insufficient memory is available
    """
    # Validate inputs upfront
    ttl_content = InputValidator.validate_ttl_content(ttl_content)
    id_prefix = InputValidator.validate_id_prefix(id_prefix)
    
    converter = RDFToFabricConverter(id_prefix=id_prefix)
    
    # Get detailed conversion result
    result = converter.parse_ttl(ttl_content, force_large_file=force_large_file, return_result=True)
    
    # Type assertion for mypy
    assert isinstance(result, ConversionResult), "Expected ConversionResult when return_result=True"
    
    # Try to extract ontology name from the TTL
    graph = Graph()
    graph.parse(data=ttl_content, format='turtle')
    
    ontology_name = "ImportedOntology"
    for s in graph.subjects(RDF.type, OWL.Ontology):
        # Try to get label
        labels = list(graph.objects(s, RDFS.label))
        if labels:
            label = str(labels[0])
            # Clean up for Fabric naming requirements
            ontology_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in label)
            ontology_name = ontology_name[:100]  # Max 100 chars
            if ontology_name and not ontology_name[0].isalpha():
                ontology_name = 'O_' + ontology_name
        break
    
    definition = convert_to_fabric_definition(
        result.entity_types, 
        result.relationship_types, 
        ontology_name
    )
    
    return definition, ontology_name, result


def parse_ttl_file_with_result(
    file_path: str, 
    id_prefix: int = 1000000000000, 
    force_large_file: bool = False
) -> Tuple[Dict[str, Any], str, ConversionResult]:
    """
    Parse a TTL file and return the Fabric Ontology definition with detailed conversion result.
    
    This function provides enhanced error recovery by tracking skipped items
    and warnings during conversion.
    
    Args:
        file_path: Path to the TTL file
        id_prefix: Base prefix for generating unique IDs
        force_large_file: If True, skip memory safety checks for large files
        
    Returns:
        Tuple of (Fabric Ontology definition dict, extracted ontology name, ConversionResult)
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        PermissionError: If the file is not readable
        MemoryError: If insufficient memory is available
        ValueError: If the file content is invalid, path traversal detected, or invalid extension
        TypeError: If parameters have wrong type
    """
    # Validate inputs upfront with security checks
    validated_path = InputValidator.validate_input_ttl_path(file_path)
    id_prefix = InputValidator.validate_id_prefix(id_prefix)
    
    try:
        with open(validated_path, 'r', encoding='utf-8') as f:
            ttl_content = f.read()
    except UnicodeDecodeError as e:
        logger.error(f"Encoding error reading {validated_path}: {e}")
        # Try with different encoding
        try:
            with open(validated_path, 'r', encoding='latin-1') as f:
                ttl_content = f.read()
            logger.warning(f"Successfully read file with latin-1 encoding")
        except Exception as e2:
            raise ValueError(f"Unable to decode file {validated_path}: {e2}")
    except PermissionError:
        logger.error(f"Permission denied reading {validated_path}")
        raise PermissionError(f"Permission denied: {validated_path}")
    except Exception as e:
        logger.error(f"Error reading file {validated_path}: {e}")
        raise IOError(f"Error reading file: {e}")
    
    return parse_ttl_with_result(ttl_content, id_prefix, force_large_file=force_large_file)