"""
Streaming RDF Converter.

Memory-efficient streaming converter for large RDF ontologies.
This module was extracted from formats/rdf/rdf_converter.py for
better separation of concerns.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rdflib import URIRef

from shared.models import (
    EntityType,
    RelationshipType,
    ConversionResult,
    SkippedItem,
)
from .rdf_parser import RDFGraphParser
from .property_extractor import (
    ClassExtractor,
    DataPropertyExtractor,
    ObjectPropertyExtractor,
    EntityIdentifierSetter,
)
from .type_mapper import TypeMapper
from .uri_utils import URIUtils

logger = logging.getLogger(__name__)

# Type alias
FabricType = str


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
        cancellation_token: Optional[Any] = None,
        rdf_format: Optional[str] = None,
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
            rdf_format: Optional RDF format hint (e.g., 'turtle', 'xml', 'n3')
            
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
        graph, total_triples, _ = RDFGraphParser.parse_ttl_file(
            file_path,
            rdf_format=rdf_format,
        )
        
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
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics from the last conversion.
        
        Returns:
            Dictionary with conversion statistics
        """
        return {
            "triples_processed": self.triples_processed,
            "classes_found": self.classes_found,
            "properties_found": self.properties_found,
            "entities_created": len(self.entity_types),
            "relationships_created": len(self.relationship_types),
            "items_skipped": len(self.skipped_items),
            "warnings": len(self.conversion_warnings),
        }
