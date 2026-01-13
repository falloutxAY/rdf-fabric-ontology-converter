"""
Property and Relationship Extractor Module

This module handles extraction of classes, data properties, and object properties
from src.rdf graphs. Extracted from rdf_converter.py for better maintainability.

Components:
- ClassExtractor: Extracts OWL/RDFS classes as entity types
- DataPropertyExtractor: Extracts data properties and assigns to entity types
- ObjectPropertyExtractor: Extracts object properties as relationship types
"""

import logging
from typing import Dict, List, Set, Optional, Tuple, Any, Callable

from rdflib import Graph, RDF, RDFS, OWL, URIRef, BNode
from rdflib.term import Node
from tqdm import tqdm

# Import from sibling modules
from .type_mapper import TypeMapper, XSD_TO_FABRIC_TYPE
from .uri_utils import URIUtils
from .class_resolver import ClassResolver

# Import models
from src.shared.models import (
    EntityType,
    EntityTypeProperty,
    RelationshipType,
    RelationshipEnd,
    SkippedItem,
)

logger = logging.getLogger(__name__)


class ClassExtractor:
    """
    Extracts OWL/RDFS classes as entity types from an RDF graph.
    
    Handles:
    - owl:Class declarations
    - rdfs:Class declarations
    - Classes with rdfs:subClassOf relationships
    - Parent-child inheritance with cycle detection
    """
    
    @staticmethod
    def extract_classes(
        graph: Graph,
        id_generator: Callable[[], str],
        uri_to_name: Callable[[URIRef], str]
    ) -> Tuple[Dict[str, EntityType], Dict[str, str]]:
        """
        Extract all OWL/RDFS classes as entity types.
        
        Args:
            graph: The RDF graph to extract from
            id_generator: Function to generate unique IDs
            uri_to_name: Function to convert URIs to names
            
        Returns:
            Tuple of (entity_types dict keyed by URI, uri_to_id mapping)
        """
        entity_types: Dict[str, EntityType] = {}
        uri_to_id: Dict[str, str] = {}
        
        # Find all classes
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
        
        logger.info(f"Found {len(classes)} classes")
        
        if len(classes) == 0:
            logger.warning("No OWL/RDFS classes found in ontology")
        
        # First pass: create all entity types without parent relationships
        for class_uri in tqdm(classes, desc="Creating entity types", unit="class", disable=len(classes) < 10):
            entity_id = id_generator()
            name = uri_to_name(class_uri)
            
            entity_type = EntityType(
                id=entity_id,
                name=name,
                baseEntityTypeId=None,  # Set in second pass
            )
            
            entity_types[str(class_uri)] = entity_type
            uri_to_id[str(class_uri)] = entity_id
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
                if isinstance(parent, URIRef) and str(parent) in uri_to_id:
                    # Check for cycles
                    if has_cycle(parent, {class_uri}):
                        logger.warning(
                            f"Circular inheritance detected for {uri_to_name(class_uri)}, "
                            f"skipping parent {uri_to_name(parent)}"
                        )
                        continue
                    
                    entity_types[str(class_uri)].baseEntityTypeId = uri_to_id[str(parent)]
                    break  # Only take first non-circular parent
        
        return entity_types, uri_to_id


class DataPropertyExtractor:
    """
    Extracts data properties and assigns them to entity types.
    
    Handles:
    - owl:DatatypeProperty declarations
    - rdf:Property with XSD ranges
    - Properties with rdfs:domain and rdfs:range
    - Datatype union resolution
    """
    
    @staticmethod
    def extract_data_properties(
        graph: Graph,
        entity_types: Dict[str, EntityType],
        id_generator: Callable[[], str],
        uri_to_name: Callable[[URIRef], str],
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Extract data properties and add them to entity types.
        
        Args:
            graph: The RDF graph to extract from
            entity_types: Dictionary of entity types keyed by URI
            id_generator: Function to generate unique IDs
            uri_to_name: Function to convert URIs to names
            
        Returns:
            Tuple of (property_to_domain mapping, uri_to_id mapping for properties)
        """
        property_to_domain: Dict[str, str] = {}
        uri_to_id: Dict[str, str] = {}
        
        # Find all data properties
        # Include both OWL.DatatypeProperty and rdf:Property with XSD ranges
        data_properties: Set[URIRef] = set()
        owl_datatype_props: Set[URIRef] = set()
        rdf_props_with_xsd_range: Set[URIRef] = set()

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
            from rdflib import XSD
            if range_str in XSD_TO_FABRIC_TYPE or range_str.startswith(str(XSD)):
                rdf_props_with_xsd_range.add(s)

        data_properties = owl_datatype_props | rdf_props_with_xsd_range

        logger.info(f"Found {len(data_properties)} data properties")

        for prop_uri in data_properties:
            prop_id = id_generator()
            name = uri_to_name(prop_uri)
            
            # Get domain (which entity type this property belongs to)
            raw_domains = list(graph.objects(prop_uri, RDFS.domain))
            domains: List[str] = []
            for d in raw_domains:
                domains.extend(ClassResolver.resolve_class_targets(graph, d))
            
            # Get range (value type) with datatype union support
            ranges = list(graph.objects(prop_uri, RDFS.range))
            value_type = "String"  # Default
            union_notes = ""
            
            if ranges:
                if isinstance(ranges[0], URIRef):
                    value_type = TypeMapper.get_fabric_type(str(ranges[0]))
                elif isinstance(ranges[0], BNode):
                    # Resolve datatype union to most restrictive compatible type
                    value_type, union_notes = TypeMapper.resolve_datatype_union(
                        graph, ranges[0], ClassResolver.resolve_rdf_list
                    )
                    if union_notes:
                        logger.debug(f"Property {name}: {union_notes}")
            
            # Check rdfs:comment for "(timeseries)" annotation
            is_timeseries = False
            comments = list(graph.objects(prop_uri, RDFS.comment))
            if comments:
                comment_text = str(comments[0]).lower()
                if "(timeseries)" in comment_text:
                    is_timeseries = True
                    logger.debug(f"Property {name} marked as timeseries from rdfs:comment")
            
            prop = EntityTypeProperty(
                id=prop_id,
                name=name,
                valueType=value_type,
                is_timeseries=is_timeseries,
            )
            
            # Add property to all domain classes
            for domain_uri in domains:
                if domain_uri in entity_types:
                    # Use is_timeseries flag from rdfs:comment annotation
                    if is_timeseries:
                        entity_types[domain_uri].timeseriesProperties.append(prop)
                    else:
                        entity_types[domain_uri].properties.append(prop)
                    property_to_domain[str(prop_uri)] = domain_uri
                    logger.debug(f"Added {'timeseries ' if is_timeseries else ''}property {name} to entity type {entity_types[domain_uri].name}")
            
            uri_to_id[str(prop_uri)] = prop_id
        
        return property_to_domain, uri_to_id


class ObjectPropertyExtractor:
    """
    Extracts object properties as relationship types.
    
    Handles:
    - owl:ObjectProperty declarations
    - rdf:Property with non-XSD ranges (entity references)
    - Domain and range inference from usage patterns
    - Multiple domain-range pairs creating multiple relationships
    """
    
    @staticmethod
    def extract_object_properties(
        graph: Graph,
        entity_types: Dict[str, EntityType],
        property_to_domain: Dict[str, str],
        id_generator: Callable[[], str],
        uri_to_name: Callable[[URIRef], str],
        skip_callback: Optional[Callable[[str, str, str, str], None]] = None
    ) -> Tuple[Dict[str, RelationshipType], Dict[str, str]]:
        """
        Extract object properties as relationship types.
        
        Args:
            graph: The RDF graph to extract from
            entity_types: Dictionary of entity types keyed by URI
            property_to_domain: Mapping of property URIs to domain URIs (to exclude data properties)
            id_generator: Function to generate unique IDs
            uri_to_name: Function to convert URIs to names
            skip_callback: Optional callback for skipped items (item_type, name, reason, uri)
            
        Returns:
            Tuple of (relationship_types dict keyed by unique key, uri_to_id mapping)
        """
        from rdflib import XSD
        
        relationship_types: Dict[str, RelationshipType] = {}
        uri_to_id: Dict[str, str] = {}
        
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
        known_props: Set[URIRef] = {URIRef(k) for k in property_to_domain.keys()}
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
                    if str(subj_type) in entity_types:
                        property_usage[str(p)]['subjects'].add(str(subj_type))
                
                if isinstance(o, URIRef):
                    for obj_type in graph.objects(o, RDF.type):
                        if str(obj_type) in entity_types:
                            property_usage[str(p)]['objects'].add(str(obj_type))
        
        for prop_uri in tqdm(object_properties, desc="Processing relationships", unit="property", disable=len(object_properties) < 10):
            name = uri_to_name(prop_uri)
            
            # Get explicit domain and range
            raw_domains = list(graph.objects(prop_uri, RDFS.domain))
            raw_ranges = list(graph.objects(prop_uri, RDFS.range))

            domain_uris: List[str] = []
            range_uris: List[str] = []

            # Try explicit declarations first, including unionOf class expressions
            for d in raw_domains:
                domain_uris.extend(ClassResolver.resolve_class_targets(graph, d))
            for r in raw_ranges:
                range_uris.extend(ClassResolver.resolve_class_targets(graph, r))

            domain_uris = [u for u in domain_uris if u in entity_types]
            range_uris = [u for u in range_uris if u in entity_types]
            
            # Fall back to inference from usage
            if not domain_uris:
                usage = property_usage.get(str(prop_uri), {})
                if usage.get('subjects'):
                    # Use most common subject type
                    domain_uris = [next(iter(usage['subjects']))]
                    logger.debug(f"Inferred domain for {name}: {uri_to_name(URIRef(domain_uris[0]))}")
            
            if not range_uris:
                usage = property_usage.get(str(prop_uri), {})
                if usage.get('objects'):
                    # Use most common object type
                    range_uris = [next(iter(usage['objects']))]
                    logger.debug(f"Inferred range for {name}: {uri_to_name(URIRef(range_uris[0]))}")
            
            if not domain_uris or not range_uris:
                # Determine specific reason for skipping
                if not domain_uris and not range_uris:
                    reason = "missing both domain and range"
                elif not domain_uris:
                    reason = "missing domain class"
                else:
                    reason = "missing range class"
                
                if skip_callback:
                    skip_callback("relationship", name, reason, str(prop_uri))
                else:
                    logger.warning(f"Skipped relationship '{name}': {reason}")
                continue

            # Create relationships for each domain-range pair
            created_any = False
            for d_uri in domain_uris:
                for r_uri in range_uris:
                    if d_uri not in entity_types or r_uri not in entity_types:
                        continue
                    rel_id = id_generator()
                    relationship = RelationshipType(
                        id=rel_id,
                        name=name,
                        source=RelationshipEnd(entityTypeId=entity_types[d_uri].id),
                        target=RelationshipEnd(entityTypeId=entity_types[r_uri].id),
                    )
                    # Store using unique key per pair to avoid overwrite
                    key = f"{str(prop_uri)}::{d_uri}->{r_uri}"
                    relationship_types[key] = relationship
                    uri_to_id[key] = rel_id
                    created_any = True
                    logger.debug(f"Created relationship type: {name} ({uri_to_name(URIRef(d_uri))} -> {uri_to_name(URIRef(r_uri))})")
            
            if not created_any:
                if skip_callback:
                    skip_callback(
                        "relationship", name,
                        "domain or range entity type not found in converted classes",
                        str(prop_uri)
                    )
        
        return relationship_types, uri_to_id


class EntityIdentifierSetter:
    """
    Sets entity ID parts and display name properties for entity types.
    
    Fabric requirements:
    - entityIdParts must reference String or BigInt properties
    - displayNamePropertyId should reference a String property
    """
    
    @staticmethod
    def set_identifiers(entity_types: Dict[str, EntityType]) -> None:
        """
        Set entity ID parts and display name properties for all entity types.
        
        Args:
            entity_types: Dictionary of entity types keyed by URI (modified in place)
        """
        for entity_uri, entity_type in entity_types.items():
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
