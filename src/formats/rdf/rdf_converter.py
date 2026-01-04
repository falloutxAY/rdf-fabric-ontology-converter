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
    - converters.streaming_converter: Memory-efficient streaming conversion
    - core.validators: Input validation (InputValidator), definition validation
    
    The main class (RDFToFabricConverter) delegates to these focused components
    while maintaining backward compatibility.
    
    StreamingRDFConverter has been extracted to streaming_converter.py but is
    re-exported here for backward compatibility.
"""

import logging
from pathlib import Path
from typing import (
    Dict, List, Any, Optional, Tuple, Union, 
    Callable, Literal, cast
)
from dataclasses import dataclass

from rdflib import Graph, RDF, RDFS, OWL, URIRef

# Import refactored components
from .rdf_parser import MemoryManager, RDFGraphParser
from .property_extractor import (
    ClassExtractor,
    DataPropertyExtractor,
    ObjectPropertyExtractor,
    EntityIdentifierSetter,
)
from .type_mapper import TypeMapper, XSD_TO_FABRIC_TYPE
from .uri_utils import URIUtils
from .class_resolver import ClassResolver
from .fabric_serializer import FabricSerializer
from .streaming_converter import StreamingRDFConverter
from core.validators import (
    InputValidator,
    FabricLimitsValidator,
    EntityIdPartsInferrer,
    FabricDefinitionValidator,
    DefinitionValidationError,
)
from core.compliance import (
    RDFOWLComplianceValidator,
    FabricComplianceChecker,
    ConversionReportGenerator,
    ConversionReport,
)
from shared.models import (
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


# Re-export DefinitionValidationError and FabricDefinitionValidator for backward compatibility
# These have been moved to core.validators.definition
__all__ = [
    'RDFToFabricConverter',
    'StreamingRDFConverter',
    'FabricDefinitionValidator',
    'DefinitionValidationError',
    'parse_ttl_file',
    'parse_ttl_content',
    'parse_ttl_file_with_result',
    'parse_ttl_with_result',
    'parse_ttl_streaming',
    'convert_to_fabric_definition',
]


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
        return_result: bool = False,
        rdf_format: Optional[str] = None,
        source_path: Optional[Union[str, Path]] = None,
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
            ttl_content,
            force_large_file,
            rdf_format=rdf_format,
            source_path=source_path,
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
    
    def parse_ttl_with_compliance_report(
        self, 
        ttl_content: str, 
        force_large_file: bool = False,
        rdf_format: Optional[str] = None,
        source_path: Optional[Union[str, Path]] = None,
    ) -> Tuple[ConversionResult, Optional["ConversionReport"]]:
        """
        Parse RDF TTL content with a compliance report.
        
        This method performs the standard conversion and additionally generates
        a detailed compliance report showing:
        - RDF/OWL compliance issues
        - Fabric API limit compliance
        - Features that are preserved, limited, or lost in conversion
        
        Args:
            ttl_content: The TTL content as a string
            force_large_file: If True, skip memory safety checks for large files
        
        Returns:
            Tuple of (ConversionResult, ConversionReport or None)
            The report may be None if compliance module is not available
            
        Raises:
            ValueError: If TTL content is empty or has invalid syntax
            MemoryError: If insufficient memory is available to parse the file
        """
        # Delegate TTL parsing to RDFGraphParser
        graph, triple_count, content_size_mb = RDFGraphParser.parse_ttl_content(
            ttl_content,
            force_large_file,
            rdf_format=rdf_format,
            source_path=source_path,
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
        
        # Create conversion result
        result = ConversionResult(
            entity_types=entity_list,
            relationship_types=relationship_list,
            skipped_items=self.skipped_items.copy(),
            warnings=self.conversion_warnings.copy(),
            triple_count=triple_count
        )
        
        # Generate compliance report if module is available
        report = None
        if ConversionReportGenerator is not None:
            try:
                report = ConversionReportGenerator.generate_rdf_report(
                    graph=graph,
                    conversion_result=result
                )
                
                # Log conversion warnings
                for warning in report.warnings:
                    logger.warning(
                        f"Conversion warning [{warning.impact.value}]: "
                        f"{warning.feature} - {warning.message}"
                    )
                
                # Log summary
                logger.info(
                    f"Compliance report: {report.total_issues} issues, "
                    f"{len(report.warnings)} conversion warnings"
                )
            except Exception as e:
                logger.warning(f"Failed to generate compliance report: {e}")
        
        return result, report


# StreamingRDFConverter has been extracted to streaming_converter.py
# It is imported at the top of this module for backward compatibility


def parse_ttl_streaming(
    file_path: str,
    id_prefix: int = 1000000000000,
    batch_size: int = StreamingRDFConverter.DEFAULT_BATCH_SIZE,
    progress_callback: Optional[Callable[[int], None]] = None,
    cancellation_token: Optional[Any] = None,
    rdf_format: Optional[str] = None,
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
        cancellation_token=cancellation_token,
        rdf_format=rdf_format,
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
    skip_validation: bool = False,
    skip_fabric_limits: bool = False,
) -> Dict[str, Any]:
    """
    Convert parsed entity and relationship types to Fabric Ontology definition format.
    
    Args:
        entity_types: List of entity types
        relationship_types: List of relationship types
        ontology_name: Name for the ontology
        skip_validation: If True, skip definition validation (not recommended)
        skip_fabric_limits: If True, skip Fabric API limits validation
        
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
    
    # Validate Fabric API limits (unless explicitly skipped)
    if not skip_fabric_limits:
        fabric_validator = FabricLimitsValidator()
        limit_errors = fabric_validator.validate_all(entity_types, relationship_types)
        
        # Log limit validation issues
        for error in limit_errors:
            if error.level == "warning":
                logger.warning(f"Fabric limit warning: {error.message}")
            else:
                logger.error(f"Fabric limit error: {error.message}")
        
        # Fail on critical limit errors
        if fabric_validator.has_errors(limit_errors):
            critical_errors = fabric_validator.get_errors_only(limit_errors)
            error_msg = "Fabric API limit exceeded:\n" + "\n".join(
                f"  - {e.message}" for e in critical_errors
            )
            raise ValueError(error_msg)
        
        warnings = fabric_validator.get_warnings_only(limit_errors)
        if warnings:
            logger.info(f"Fabric limits check passed with {len(warnings)} warning(s)")
    
    # Delegate serialization to FabricSerializer
    return FabricSerializer.create_definition(entity_types, relationship_types, ontology_name)


# NOTE: InputValidator has been moved to core/validators.py
# It is imported at the top of this file for backward compatibility.
# Direct imports from this module (e.g., `from rdf_converter import InputValidator`)
# will continue to work.


def parse_ttl_file(
    file_path: str,
    id_prefix: int = 1000000000000,
    force_large_file: bool = False,
    rdf_format: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
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
    format_hint = rdf_format or RDFGraphParser.infer_format_from_path(validated_path)
    
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
    
    return parse_ttl_content(
        ttl_content,
        id_prefix,
        force_large_file=force_large_file,
        rdf_format=format_hint,
        source_path=str(validated_path),
    )


def parse_ttl_content(
    ttl_content: str,
    id_prefix: int = 1000000000000,
    force_large_file: bool = False,
    rdf_format: Optional[str] = None,
    source_path: Optional[Union[str, Path]] = None,
) -> Tuple[Dict[str, Any], str]:
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
    entity_types, relationship_types = converter.parse_ttl(
        ttl_content,
        force_large_file=force_large_file,
        rdf_format=rdf_format,
        source_path=source_path,
    )
    
    # Try to extract ontology name from the TTL
    graph = Graph()
    format_name = RDFGraphParser.resolve_format(rdf_format, source_path)
    graph.parse(data=ttl_content, format=format_name)
    
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
    force_large_file: bool = False,
    rdf_format: Optional[str] = None,
    source_path: Optional[Union[str, Path]] = None,
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
    result = converter.parse_ttl(
        ttl_content,
        force_large_file=force_large_file,
        return_result=True,
        rdf_format=rdf_format,
        source_path=source_path,
    )
    
    # Type assertion for mypy
    assert isinstance(result, ConversionResult), "Expected ConversionResult when return_result=True"
    
    # Try to extract ontology name from the TTL
    graph = Graph()
    format_name = RDFGraphParser.resolve_format(rdf_format, source_path)
    graph.parse(data=ttl_content, format=format_name)
    
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
    force_large_file: bool = False,
    rdf_format: Optional[str] = None,
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
    format_hint = rdf_format or RDFGraphParser.infer_format_from_path(validated_path)
    
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
    
    return parse_ttl_with_result(
        ttl_content,
        id_prefix,
        force_large_file=force_large_file,
        rdf_format=format_hint,
        source_path=str(validated_path),
    )
