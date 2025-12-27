"""
RDF TTL to Fabric Ontology Converter

This module provides functionality to parse RDF TTL files and convert them
to Microsoft Fabric Ontology API format.
"""

import json
import base64
import hashlib
import logging
import os
import sys
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, URIRef, Literal, BNode
from tqdm import tqdm

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
        result = {
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

    def _resolve_class_targets(
        self, 
        graph: Graph, 
        node: Any, 
        visited: Optional[Set[Any]] = None,
        max_depth: int = 10
    ) -> List[str]:
        """Resolve domain/range targets to class URIs with cycle detection.

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
        # Initialize visited set on first call
        if visited is None:
            visited = set()
        
        targets: List[str] = []
        
        # Cycle detection - skip if we've seen this node
        if node in visited:
            logger.debug(f"Cycle detected in class resolution, skipping node: {node}")
            return targets
        
        # Depth limit check
        if max_depth <= 0:
            logger.warning(f"Maximum recursion depth reached in class resolution for node: {node}")
            return targets
        
        # Track this node as visited (only for BNodes which can cause cycles)
        if isinstance(node, BNode):
            visited = visited | {node}  # Create new set to avoid mutation
        
        if isinstance(node, URIRef):
            targets.append(str(node))
            
        elif isinstance(node, BNode):
            unresolved_count = 0
            
            # Handle owl:unionOf
            for union in graph.objects(node, OWL.unionOf):
                union_targets, unresolved = self._resolve_rdf_list(
                    graph, union, visited, max_depth - 1
                )
                targets.extend(union_targets)
                unresolved_count += unresolved
            
            # Handle owl:intersectionOf (extract classes from intersection)
            for intersection in graph.objects(node, OWL.intersectionOf):
                intersection_targets, unresolved = self._resolve_rdf_list(
                    graph, intersection, visited, max_depth - 1
                )
                targets.extend(intersection_targets)
                unresolved_count += unresolved
            
            # Handle owl:complementOf
            for complement in graph.objects(node, OWL.complementOf):
                complement_targets = self._resolve_class_targets(
                    graph, complement, visited, max_depth - 1
                )
                targets.extend(complement_targets)
                if not complement_targets and complement is not None:
                    unresolved_count += 1
            
            # Handle owl:oneOf (enumeration of individuals - extract class references)
            for oneof in graph.objects(node, OWL.oneOf):
                oneof_targets, unresolved = self._resolve_rdf_list(
                    graph, oneof, visited, max_depth - 1
                )
                targets.extend(oneof_targets)
                unresolved_count += unresolved
            
            # If no OWL constructs matched, check if it's a typed class
            if not targets:
                # Check if the blank node represents a class restriction or typed element
                for rdf_type in graph.objects(node, RDF.type):
                    if isinstance(rdf_type, URIRef):
                        type_str = str(rdf_type)
                        # Check for OWL restriction (common pattern)
                        if type_str in (str(OWL.Restriction), str(OWL.Class)):
                            # Try to get onProperty or other class indicators
                            for on_class in graph.objects(node, OWL.onClass):
                                on_class_targets = self._resolve_class_targets(
                                    graph, on_class, visited, max_depth - 1
                                )
                                targets.extend(on_class_targets)
                            # Also check someValuesFrom
                            for svf in graph.objects(node, OWL.someValuesFrom):
                                svf_targets = self._resolve_class_targets(
                                    graph, svf, visited, max_depth - 1
                                )
                                targets.extend(svf_targets)
            
            # Log if we had unresolved items and no valid targets
            if unresolved_count > 0:
                if targets:
                    logger.debug(
                        f"Resolved {len(targets)} class targets, "
                        f"skipped {unresolved_count} unsupported constructs"
                    )
                else:
                    logger.warning(
                        f"Blank node class expression contains {unresolved_count} "
                        f"unresolved items and no valid URI targets"
                    )
        
        elif node is not None:
            # Handle unexpected node types
            logger.debug(f"Unexpected node type in class resolution: {type(node).__name__}")
        
        return targets
    
    def _resolve_rdf_list(
        self, 
        graph: Graph, 
        list_node: Any,
        visited: Set[Any],
        max_depth: int
    ) -> Tuple[List[str], int]:
        """Resolve an RDF list (rdf:first/rdf:rest) to class URIs.
        
        Args:
            graph: The RDF graph to query
            list_node: The head of the RDF list
            visited: Set of already-visited nodes for cycle detection
            max_depth: Maximum recursion depth
            
        Returns:
            Tuple of (resolved_targets, unresolved_count)
        """
        targets: List[str] = []
        unresolved_count = 0
        
        current = list_node
        list_visited = set()  # Track visited list nodes to detect malformed lists
        
        while current and current != RDF.nil:
            # Detect cycles in the list itself
            if current in list_visited:
                logger.warning(f"Cycle detected in RDF list at node: {current}")
                break
            list_visited.add(current)
            
            first = next(graph.objects(current, RDF.first), None)
            
            if first is not None:
                if isinstance(first, URIRef):
                    targets.append(str(first))
                elif isinstance(first, BNode):
                    # Recursively resolve nested blank nodes
                    nested_targets = self._resolve_class_targets(
                        graph, first, visited, max_depth
                    )
                    if nested_targets:
                        targets.extend(nested_targets)
                    else:
                        # Could not resolve the nested blank node
                        unresolved_count += 1
                        logger.debug(
                            f"Unresolved nested blank node in list: {first}"
                        )
                else:
                    # Unexpected type (Literal, etc.)
                    logger.debug(
                        f"Non-URI, non-BNode in list: {first} (type: {type(first).__name__})"
                    )
                    unresolved_count += 1
            
            current = next(graph.objects(current, RDF.rest), None)
        
        return targets, unresolved_count
        
    def _generate_id(self) -> str:
        """Generate a unique ID for entities and properties."""
        self.id_counter += 1
        return str(self.id_prefix + self.id_counter)
    
    def _uri_to_name(self, uri: URIRef) -> str:
        """Extract a clean name from a URI."""
        if uri is None:
            logger.warning("Received None URI, using default name")
            return f'Unknown_{self.id_counter}'
        
        uri_str = str(uri).strip()
        
        if not uri_str:
            logger.warning("Empty URI string, using default name")
            return f'Unknown_{self.id_counter}'
        
        # Try to get the fragment
        if '#' in uri_str:
            name = uri_str.split('#')[-1]
        elif '/' in uri_str:
            name = uri_str.split('/')[-1]
        else:
            name = uri_str
        
        # Handle empty extraction
        if not name:
            logger.warning(f"Could not extract name from URI: {uri_str}")
            return f'Entity_{self.id_counter}'
        
        # Clean up the name to match Fabric requirements
        # Fabric requires identifiers to start with a letter and contain only letters, numbers, and underscores
        # Must match: ^[a-zA-Z][a-zA-Z0-9_]{0,127}$
        cleaned = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
        
        if not cleaned:
            logger.warning(f"URI produced empty cleaned name: {uri_str}")
            return f'Entity_{self.id_counter}'
        
        if not cleaned[0].isalpha():
            cleaned = 'E_' + cleaned
        
        return cleaned[:128]
    
    def _get_xsd_type(self, range_uri: Optional[URIRef]) -> str:
        """Map XSD type to Fabric value type."""
        if range_uri is None:
            return "String"
        range_str = str(range_uri)
        return XSD_TO_FABRIC_TYPE.get(range_str, "String")
    
    def _resolve_datatype_union(
        self, 
        graph: Graph, 
        union_node: BNode
    ) -> Tuple[str, str]:
        """
        Resolve datatype union to most restrictive compatible Fabric type.
        
        Analyzes a blank node representing a datatype union and selects
        the most restrictive type that can safely represent all union members.
        
        Type preference order (most to least restrictive):
        Boolean > BigInt > Double > DateTime > String
        
        Args:
            graph: The RDF graph to query
            union_node: Blank node containing the datatype union
            
        Returns:
            Tuple of (fabric_type: str, notes: str) where:
                - fabric_type: The resolved Fabric type ("String", "BigInt", etc.)
                - notes: Description of the resolution for logging
        """
        types_found: Set[str] = set()
        
        # Traverse union to find all XSD types
        for union in graph.objects(union_node, OWL.unionOf):
            # Use existing RDF list resolution
            targets, _ = self._resolve_rdf_list(graph, union, set(), max_depth=10)
            for target in targets:
                if target in XSD_TO_FABRIC_TYPE:
                    types_found.add(target)
                elif str(target).startswith(str(XSD)):
                    # Handle other XSD types not in our mapping
                    types_found.add(target)
        
        # Also check for direct type references (non-union case)
        if not types_found:
            for rdf_type in graph.objects(union_node, RDF.type):
                type_str = str(rdf_type)
                if type_str in XSD_TO_FABRIC_TYPE:
                    types_found.add(type_str)
        
        if not types_found:
            logger.warning(f"Could not resolve any XSD types in datatype union: {union_node}")
            return "String", "union: no types found, defaulted to String"
        
        # Determine most restrictive type using hierarchy
        # Order: Boolean (most specific) -> Integer types -> Float types -> DateTime -> String (most general)
        type_hierarchy = [
            ([str(XSD.boolean)], "Boolean"),
            ([str(XSD.integer), str(XSD.int), str(XSD.long), str(XSD.short), str(XSD.byte), 
              str(XSD.nonNegativeInteger), str(XSD.positiveInteger), str(XSD.unsignedInt),
              str(XSD.unsignedLong), str(XSD.unsignedShort), str(XSD.unsignedByte)], "BigInt"),
            ([str(XSD.double), str(XSD.float), str(XSD.decimal)], "Double"),
            ([str(XSD.dateTime), str(XSD.date), str(XSD.dateTimeStamp)], "DateTime"),
            ([str(XSD.string), str(XSD.anyURI), str(XSD.normalizedString), str(XSD.token),
              str(XSD.language), str(XSD.Name), str(XSD.NCName), str(XSD.NMTOKEN)], "String"),
        ]
        
        # Find the most restrictive type that covers all union members
        for xsd_types, fabric_type in type_hierarchy:
            if any(t in types_found for t in xsd_types):
                type_str = str(types_found) if len(types_found) > 1 else next(iter(types_found))
                logger.info(f"Resolved datatype union to {fabric_type} from types: {type_str}")
                return fabric_type, f"union: selected {fabric_type} from {type_str}"
        
        # Fallback to String for unknown XSD types
        logger.warning(f"Datatype union contains unsupported XSD types: {types_found}, defaulting to String")
        return "String", f"union: unsupported types {types_found}, defaulted to String"
    
    def parse_ttl(self, ttl_content: str, force_large_file: bool = False) -> Tuple[List[EntityType], List[RelationshipType]]:
        """
        Parse RDF TTL content and extract entity and relationship types.
        
        Args:
            ttl_content: The TTL content as a string
            force_large_file: If True, skip memory safety checks for large files
            
        Returns:
            Tuple of (entity_types, relationship_types)
            
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
        
        # Reset state
        self.entity_types = {}
        self.relationship_types = {}
        self.uri_to_id = {}
        self.property_to_domain = {}
        self.id_counter = 0
        
        # Step 1: Extract all classes (entity types)
        self._extract_classes(graph)
        
        # Step 2: Extract data properties and assign to entity types
        self._extract_data_properties(graph)
        
        # Step 3: Extract object properties (relationship types)
        self._extract_object_properties(graph)
        
        # Step 4: Set entity ID parts and display name properties
        self._set_entity_identifiers()
        
        logger.info(f"Parsed {len(self.entity_types)} entity types and {len(self.relationship_types)} relationship types")
        
        return list(self.entity_types.values()), list(self.relationship_types.values())
    
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
        object_properties = set()
        owl_object_props = set()
        rdf_props_with_entity_range = set()

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

        object_properties = owl_object_props | (rdf_props_with_entity_range - set(self.property_to_domain.keys()))

        logger.info(f"Found {len(object_properties)} object properties")
        
        # Build usage map for inference
        property_usage = {}  # prop_uri -> {subjects: set, objects: set}
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
                reason = "missing domain or range (no inference possible)"
                if self.loose_inference:
                    logger.warning(f"Loose inference not implemented for complex cases; {name}: {reason}")
                else:
                    logger.warning(f"Skipping object property {name}: {reason}")
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
                logger.warning(f"Skipping object property {name}: domain or range entity type not found")
    
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
    id_to_entity = {e.id: e for e in entity_types}
    
    # Build adjacency list (child -> parent)
    # and in-degree count (how many parents reference this as base)
    children = {e.id: [] for e in entity_types}  # parent_id -> list of child_ids
    
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
    
    parts = []
    
    # Add .platform file
    platform_content = {
        "metadata": {
            "type": "Ontology",
            "displayName": ontology_name
        }
    }
    parts.append({
        "path": ".platform",
        "payload": base64.b64encode(json.dumps(platform_content, indent=2).encode()).decode(),
        "payloadType": "InlineBase64"
    })
    
    # Add definition.json (empty for Fabric)
    parts.append({
        "path": "definition.json",
        "payload": base64.b64encode(b"{}").decode(),
        "payloadType": "InlineBase64"
    })
    
    # Sort entity types so parents come before children (required by Fabric)
    sorted_entity_types = _topological_sort_entities(entity_types)
    
    # Add entity type definitions
    for entity_type in sorted_entity_types:
        entity_content = entity_type.to_dict()
        parts.append({
            "path": f"EntityTypes/{entity_type.id}/definition.json",
            "payload": base64.b64encode(json.dumps(entity_content, indent=2).encode()).decode(),
            "payloadType": "InlineBase64"
        })
    
    # Add relationship type definitions
    for rel_type in relationship_types:
        rel_content = rel_type.to_dict()
        parts.append({
            "path": f"RelationshipTypes/{rel_type.id}/definition.json",
            "payload": base64.b64encode(json.dumps(rel_content, indent=2).encode()).decode(),
            "payloadType": "InlineBase64"
        })
    
    return {"parts": parts}


class InputValidator:
    """
    Centralized input validation for RDF converter public methods.
    
    Provides consistent validation with clear error messages for:
    - TTL content validation
    - File path validation  
    - Parameter type and value checking
    """
    
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
    def validate_file_path(path: Any) -> str:
        """
        Validate file path parameter.
        
        Args:
            path: Path to validate (should be non-empty string pointing to readable file)
            
        Returns:
            Validated path string
            
        Raises:
            TypeError: If path is not a string
            ValueError: If path is empty
            FileNotFoundError: If file doesn't exist
            PermissionError: If file is not readable
        """
        if not isinstance(path, str):
            raise TypeError(f"File path must be string, got {type(path).__name__}")
        
        if not path.strip():
            raise ValueError("File path cannot be empty")
        
        path = path.strip()
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        
        if not os.path.isfile(path):
            raise ValueError(f"Path is not a file: {path}")
        
        if not os.access(path, os.R_OK):
            raise PermissionError(f"File is not readable: {path}")
        
        return path
    
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
        ValueError: If the file content is invalid
        TypeError: If parameters have wrong type
    """
    # Validate inputs upfront
    file_path = InputValidator.validate_file_path(file_path)
    id_prefix = InputValidator.validate_id_prefix(id_prefix)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ttl_content = f.read()
    except UnicodeDecodeError as e:
        logger.error(f"Encoding error reading {file_path}: {e}")
        # Try with different encoding
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                ttl_content = f.read()
            logger.warning(f"Successfully read file with latin-1 encoding")
        except Exception as e2:
            raise ValueError(f"Unable to decode file {file_path}: {e2}")
    except PermissionError:
        logger.error(f"Permission denied reading {file_path}")
        raise PermissionError(f"Permission denied: {file_path}")
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
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
