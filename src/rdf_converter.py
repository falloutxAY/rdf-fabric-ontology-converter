"""
RDF TTL to Fabric Ontology Converter

This module provides functionality to parse RDF TTL files and convert them
to Microsoft Fabric Ontology API format.

Architecture:
    This module uses composition with extracted components for maintainability:
    - converters.rdf_parser: TTL parsing with memory management
    - converters.property_extractor: Class/property extraction
    - converters.type_mapper: XSD to Fabric type mapping
    - converters.uri_utils: URI parsing and name extraction
    - converters.class_resolver: OWL class expression resolution
    - converters.fabric_serializer: Fabric API JSON serialization
    - core.validators: Input validation (InputValidator)
    
    The main classes (RDFToFabricConverter, StreamingRDFConverter) delegate
    to these focused components while maintaining backward compatibility.
"""

import logging
from pathlib import Path
from typing import (
    Dict, List, Any, Optional, Tuple, Union, 
    Callable, Literal, cast
)
from dataclasses import dataclass

from rdflib import Graph, RDF, RDFS, OWL, URIRef

# Import refactored components - try relative first, then absolute for direct execution
try:
    from .converters.rdf_parser import MemoryManager, RDFGraphParser
    from .converters.property_extractor import (
        ClassExtractor,
        DataPropertyExtractor,
        ObjectPropertyExtractor,
        EntityIdentifierSetter,
    )
    from .converters.type_mapper import TypeMapper, XSD_TO_FABRIC_TYPE
    from .converters.uri_utils import URIUtils
    from .converters.class_resolver import ClassResolver
    from .converters.fabric_serializer import FabricSerializer
    from .core.validators import InputValidator
    from .models import (
        EntityType,
        EntityTypeProperty,
        RelationshipType,
        RelationshipEnd,
        ConversionResult,
        SkippedItem,
    )
except ImportError:
    from converters.rdf_parser import MemoryManager, RDFGraphParser
    from converters.property_extractor import (
        ClassExtractor,
        DataPropertyExtractor,
        ObjectPropertyExtractor,
        EntityIdentifierSetter,
    )
    from converters.type_mapper import TypeMapper, XSD_TO_FABRIC_TYPE
    from converters.uri_utils import URIUtils
    from converters.class_resolver import ClassResolver
    from converters.fabric_serializer import FabricSerializer
    from core.validators import InputValidator
    from models import (
        EntityType,
        EntityTypeProperty,
        RelationshipType,
        RelationshipEnd,
        ConversionResult,
        SkippedItem,
    )

# Type aliases for clarity
FabricType = str  # One of: "String", "Boolean", "DateTime", "BigInt", "Double", "Int", "Long", "Float", "Decimal"
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

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
    
    This class serves as a facade, delegating to extracted components:
    - RDFGraphParser: TTL parsing with memory management
    - ClassExtractor: OWL/RDFS class extraction
    - DataPropertyExtractor: Data property extraction
    - ObjectPropertyExtractor: Object property (relationship) extraction
    - EntityIdentifierSetter: ID and display name configuration
    
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
    
    def _resolve_class_targets(
        self, 
        graph: Graph, 
        node, 
        visited=None,
        max_depth: int = 10
    ) -> List[str]:
        """Resolve domain/range targets to class URIs with cycle detection.

        Delegates to ClassResolver for the actual resolution logic.
        Kept for backward compatibility with tests.
        """
        return ClassResolver.resolve_class_targets(graph, node, visited, max_depth)
    
    def _resolve_rdf_list(
        self, 
        graph: Graph, 
        list_node,
        visited,
        max_depth: int
    ) -> Tuple[List[str], int]:
        """Resolve an RDF list (rdf:first/rdf:rest) to class URIs.
        
        Delegates to ClassResolver for the actual resolution logic.
        Kept for backward compatibility with tests.
        """
        return ClassResolver.resolve_rdf_list(graph, list_node, visited, max_depth)
    
    def _resolve_datatype_union(
        self, 
        graph: Graph, 
        union_node
    ) -> Tuple[FabricType, str]:
        """Resolve datatype union to most restrictive compatible Fabric type.
        
        Delegates to TypeMapper for the actual implementation.
        Kept for backward compatibility.
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
        # Delegate TTL parsing to RDFGraphParser
        graph, triple_count, content_size_mb = RDFGraphParser.parse_ttl_content(
            ttl_content, force_large_file
        )
        
        # Reset state (includes skipped_items and conversion_warnings)
        self._reset_state()
        
        # Step 1: Extract all classes (entity types) using ClassExtractor
        self.entity_types, class_uri_to_id = ClassExtractor.extract_classes(
            graph, self._generate_id, self._uri_to_name
        )
        self.uri_to_id.update(class_uri_to_id)
        
        # Step 2: Extract data properties using DataPropertyExtractor
        self.property_to_domain, prop_uri_to_id = DataPropertyExtractor.extract_data_properties(
            graph, self.entity_types, self._generate_id, self._uri_to_name
        )
        self.uri_to_id.update(prop_uri_to_id)
        
        # Step 3: Extract object properties (relationships) using ObjectPropertyExtractor
        self.relationship_types, rel_uri_to_id = ObjectPropertyExtractor.extract_object_properties(
            graph, self.entity_types, self.property_to_domain,
            self._generate_id, self._uri_to_name, self._add_skipped_item
        )
        self.uri_to_id.update(rel_uri_to_id)
        
        # Step 4: Set entity ID parts and display name properties
        EntityIdentifierSetter.set_identifiers(self.entity_types)
        
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
        return URIUtils.uri_to_name(uri, self.id_counter)
    
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
        return TypeMapper.get_fabric_type(str(range_uri) if range_uri else None)
    
    def parse_ttl_streaming(
        self, 
        file_path: str,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancellation_token: Optional[Any] = None
    ) -> ConversionResult:
        """
        Parse large TTL file in streaming fashion.
        
        This method processes the file in phases:
        1. Phase 1: Quick scan to discover all classes
        2. Phase 2: Process properties in batches
        3. Phase 3: Process relationships
        4. Phase 4: Set entity identifiers
        
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
        
        # Parse the TTL file using RDFGraphParser
        graph, total_triples, _ = RDFGraphParser.parse_ttl_file(file_path)
        
        if progress_callback:
            progress_callback(0)
        
        # Phase 1: Extract classes using ClassExtractor
        logger.info("Phase 1: Discovering classes...")
        self.entity_types, class_uri_to_id = ClassExtractor.extract_classes(
            graph, self._generate_id, self._uri_to_name
        )
        self.uri_to_id.update(class_uri_to_id)
        self.classes_found = len(self.entity_types)
        logger.info(f"Phase 1 complete: Found {self.classes_found} classes")
        
        # Check for cancellation
        if cancellation_token and hasattr(cancellation_token, 'throw_if_cancelled'):
            cancellation_token.throw_if_cancelled()
        
        # Phase 2: Process properties using DataPropertyExtractor
        logger.info("Phase 2: Processing properties...")
        self.property_to_domain, prop_uri_to_id = DataPropertyExtractor.extract_data_properties(
            graph, self.entity_types, self._generate_id, self._uri_to_name
        )
        self.uri_to_id.update(prop_uri_to_id)
        self.properties_found = len(self.property_to_domain)
        logger.info(f"Phase 2 complete: Found {self.properties_found} data properties")
        
        # Check for cancellation
        if cancellation_token and hasattr(cancellation_token, 'throw_if_cancelled'):
            cancellation_token.throw_if_cancelled()
        
        # Phase 3: Process relationships using ObjectPropertyExtractor
        logger.info("Phase 3: Processing relationships...")
        self.relationship_types, rel_uri_to_id = ObjectPropertyExtractor.extract_object_properties(
            graph, self.entity_types, self.property_to_domain,
            self._generate_id, self._uri_to_name, self._add_skipped_item
        )
        self.uri_to_id.update(rel_uri_to_id)
        logger.info(f"Phase 3 complete: Found {len(self.relationship_types)} relationships")
        
        # Phase 4: Set entity identifiers using EntityIdentifierSetter
        logger.info("Phase 4: Setting entity identifiers...")
        EntityIdentifierSetter.set_identifiers(self.entity_types)
        
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


# NOTE: InputValidator has been moved to core/validators.py
# It is imported at the top of this file for backward compatibility.
# Direct imports from this module (e.g., `from rdf_converter import InputValidator`)
# will continue to work.


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
