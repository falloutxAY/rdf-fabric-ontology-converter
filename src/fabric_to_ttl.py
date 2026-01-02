"""
Fabric Ontology to RDF TTL Exporter

This module provides functionality to convert Microsoft Fabric Ontology
definitions back to RDF TTL (Turtle) format.
"""

import json
import base64
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set, Literal

from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, URIRef, BNode
from rdflib.term import Literal as RDFLiteral

logger = logging.getLogger(__name__)

# Type alias for Fabric value types
FabricValueType = Literal["String", "Boolean", "DateTime", "BigInt", "Double", "Int", "Long", "Float", "Decimal"]

# Fabric type to XSD type mapping (reverse of XSD_TO_FABRIC_TYPE)
FABRIC_TO_XSD_TYPE: Dict[str, URIRef] = {
    "String": XSD.string,
    "Boolean": XSD.boolean,
    "DateTime": XSD.dateTime,
    "BigInt": XSD.integer,
    "Double": XSD.double,
    "Int": XSD.integer,
    "Long": XSD.long,
    "Float": XSD.float,
    "Decimal": XSD.decimal,
}


class FabricToTTLConverter:
    """
    Converts Microsoft Fabric Ontology definitions to RDF TTL format.
    """
    
    def __init__(self, base_namespace: str = "http://example.org/ontology#") -> None:
        """
        Initialize the converter.
        
        Args:
            base_namespace: Base namespace URI for the ontology
        """
        self.base_namespace: str = base_namespace
        self.graph: Graph = Graph()
        self.ns: Namespace = Namespace(base_namespace)
        self.entity_id_to_uri: Dict[str, URIRef] = {}
        self.entity_id_to_name: Dict[str, str] = {}
        
    def _setup_namespaces(self) -> None:
        """Setup common namespaces in the graph."""
        self.graph.bind("", self.ns)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("rdf", RDF)
        self.graph.bind("xsd", XSD)
        
    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use as a URI local name."""
        # Replace spaces and special chars with underscores
        sanitized = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
        # Ensure starts with letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = 'C_' + sanitized
        return sanitized or 'UnnamedClass'
    
    def _decode_payload(self, payload: str) -> Dict[str, Any]:
        """
        Decode base64 payload from Fabric definition part.
        
        Args:
            payload: Base64 encoded JSON string
            
        Returns:
            Decoded JSON as dictionary, or empty dict on failure
        """
        try:
            decoded = base64.b64decode(payload).decode('utf-8')
            return json.loads(decoded)
        except Exception as e:
            logger.warning(f"Failed to decode payload: {e}")
            return {}
    
    def _extract_definitions(self, fabric_definition: Dict[str, Any]) -> Tuple[List[Dict], List[Dict]]:
        """
        Extract entity types and relationship types from Fabric definition.
        
        Supports both formats:
        1. Fabric API format with base64 payloads: {"parts": [{"path": "EntityTypes/...", "payload": "..."}]}
        2. Simple format for testing: {"parts": [{"id": "...", "type": "EntityType", ...}]}
        
        Limitations:
        - Nested/complex payloads that fail base64 decoding are silently skipped (logged as warning)
        - In simple format, Property parts must appear after their parent EntityType part
        - No structural validation is performed on decoded payload content
        - Properties without a matching parent entity are silently dropped
        
        Args:
            fabric_definition: The Fabric ontology definition. Can be either:
                - Direct definition: {"parts": [...]}
                - Wrapped definition: {"definition": {"parts": [...]}}
            
        Returns:
            Tuple of (entity_types, relationship_types) where:
                - entity_types: List of decoded entity type definitions
                - relationship_types: List of decoded relationship type definitions
        """
        entity_types = []
        relationship_types = []
        
        # Handle both direct definition and wrapped definition
        parts = fabric_definition.get('parts', [])
        if not parts and 'definition' in fabric_definition:
            parts = fabric_definition['definition'].get('parts', [])
        
        for part in parts:
            # Check if this is Fabric API format (has path and payload)
            if 'path' in part and 'payload' in part:
                path = part.get('path', '')
                payload = part.get('payload', '')
                
                if not payload:
                    continue
                    
                decoded = self._decode_payload(payload)
                
                if 'EntityTypes/' in path:
                    entity_types.append(decoded)
                elif 'RelationshipTypes/' in path:
                    relationship_types.append(decoded)
            
            # Simple format for testing (direct object with type field)
            elif 'type' in part:
                part_type = part.get('type', '')
                if part_type == 'EntityType':
                    # Convert simple format to expected format
                    entity = {
                        'id': part.get('id', ''),
                        'name': part.get('displayName', part.get('name', part.get('id', ''))),
                        'baseEntityTypeId': part.get('baseEntityType'),
                        'properties': []
                    }
                    entity_types.append(entity)
                elif part_type == 'Property':
                    # Find the parent entity and add property to it
                    parent_id = part.get('parentEntity', '')
                    prop = {
                        'id': part.get('id', ''),
                        'name': part.get('displayName', part.get('name', '')),
                        'valueType': part.get('dataType', 'String')
                    }
                    # Add to existing entity if found
                    for entity in entity_types:
                        if entity.get('id') == parent_id or entity.get('name') == parent_id:
                            if 'properties' not in entity:
                                entity['properties'] = []
                            entity['properties'].append(prop)
                            break
                elif part_type == 'Relationship':
                    rel = {
                        'id': part.get('id', ''),
                        'name': part.get('displayName', part.get('name', '')),
                        'source': {'entityTypeId': part.get('fromEntity', '')},
                        'target': {'entityTypeId': part.get('toEntity', '')}
                    }
                    relationship_types.append(rel)
        
        return entity_types, relationship_types
    
    def _add_entity_type(self, entity: Dict[str, Any]) -> None:
        """
        Add an entity type to the RDF graph as an owl:Class.
        
        Args:
            entity: Entity type definition from Fabric
        """
        entity_id = entity.get('id', '')
        name = entity.get('name', f'Class_{entity_id}')
        
        # Create URI for this class
        sanitized_name = self._sanitize_name(name)
        class_uri = self.ns[sanitized_name]
        
        # Store mapping for later use
        self.entity_id_to_uri[entity_id] = class_uri
        self.entity_id_to_name[entity_id] = name
        
        # Add class declaration
        self.graph.add((class_uri, RDF.type, OWL.Class))
        self.graph.add((class_uri, RDFS.label, RDFLiteral(name)))
        
        # Handle inheritance (baseEntityTypeId)
        base_entity_id = entity.get('baseEntityTypeId')
        if base_entity_id and base_entity_id in self.entity_id_to_uri:
            parent_uri = self.entity_id_to_uri[base_entity_id]
            self.graph.add((class_uri, RDFS.subClassOf, parent_uri))
        
        # Add properties as owl:DatatypeProperty
        for prop in entity.get('properties', []):
            self._add_datatype_property(prop, class_uri, entity_id)
    
    def _add_datatype_property(self, prop: Dict[str, Any], domain_uri: URIRef, entity_id: str) -> None:
        """
        Add a datatype property to the RDF graph.
        
        Args:
            prop: Property definition from Fabric
            domain_uri: URI of the class this property belongs to
            entity_id: ID of the entity type
        """
        prop_name = prop.get('name', f'property_{prop.get("id", "")}')
        value_type = prop.get('valueType', 'String')
        
        # Create URI for property
        sanitized_name = self._sanitize_name(prop_name)
        prop_uri = self.ns[sanitized_name]
        
        # Add property declaration
        self.graph.add((prop_uri, RDF.type, OWL.DatatypeProperty))
        self.graph.add((prop_uri, RDFS.label, RDFLiteral(prop_name)))
        self.graph.add((prop_uri, RDFS.domain, domain_uri))
        
        # Map Fabric type to XSD type
        xsd_type = FABRIC_TO_XSD_TYPE.get(value_type, XSD.string)
        self.graph.add((prop_uri, RDFS.range, xsd_type))
    
    def _get_entity_uri(self, entity_ref: str) -> Optional[URIRef]:
        """
        Get entity URI by ID or name.
        
        Args:
            entity_ref: Entity ID or name
            
        Returns:
            URIRef if found, None otherwise
        """
        # Try by ID first
        if entity_ref in self.entity_id_to_uri:
            return self.entity_id_to_uri[entity_ref]
        
        # Try by name (reverse lookup)
        for entity_id, name in self.entity_id_to_name.items():
            if name == entity_ref:
                return self.entity_id_to_uri.get(entity_id)
        
        return None
    
    def _add_relationship_type(self, relationship: Dict[str, Any]) -> None:
        """
        Add a relationship type to the RDF graph as an owl:ObjectProperty.
        
        Args:
            relationship: Relationship type definition from Fabric
        """
        rel_id = relationship.get('id', '')
        name = relationship.get('name', f'relationship_{rel_id}')
        
        # Create URI for property
        sanitized_name = self._sanitize_name(name)
        prop_uri = self.ns[sanitized_name]
        
        # Add object property declaration
        self.graph.add((prop_uri, RDF.type, OWL.ObjectProperty))
        self.graph.add((prop_uri, RDFS.label, RDFLiteral(name)))
        
        # Add domain (source)
        source = relationship.get('source', {})
        source_entity_id = source.get('entityTypeId', '')
        domain_uri = self._get_entity_uri(source_entity_id)
        if domain_uri:
            self.graph.add((prop_uri, RDFS.domain, domain_uri))
        
        # Add range (target)
        target = relationship.get('target', {})
        target_entity_id = target.get('entityTypeId', '')
        range_uri = self._get_entity_uri(target_entity_id)
        if range_uri:
            self.graph.add((prop_uri, RDFS.range, range_uri))
    
    def convert(self, fabric_definition: Dict[str, Any]) -> str:
        """
        Convert a Fabric ontology definition to TTL format.
        
        Args:
            fabric_definition: The Fabric ontology definition (JSON)
            
        Returns:
            TTL string representation of the ontology
        """
        # Reset state
        self.graph = Graph()
        self.entity_id_to_uri = {}
        self.entity_id_to_name = {}
        
        # Setup namespaces
        self._setup_namespaces()
        
        # Get ontology name
        ontology_name = fabric_definition.get('displayName', 'ExportedOntology')
        
        # Add ontology declaration
        ontology_uri = self.ns[self._sanitize_name(ontology_name)]
        self.graph.add((ontology_uri, RDF.type, OWL.Ontology))
        self.graph.add((ontology_uri, RDFS.label, RDFLiteral(ontology_name)))
        
        # Extract entity types and relationships
        entity_types, relationship_types = self._extract_definitions(fabric_definition)
        
        logger.info(f"Converting {len(entity_types)} entity types and {len(relationship_types)} relationship types to TTL")
        
        # First pass: add all entity types (needed for inheritance resolution)
        for entity in entity_types:
            entity_id = entity.get('id', '')
            name = entity.get('name', f'Class_{entity_id}')
            sanitized_name = self._sanitize_name(name)
            self.entity_id_to_uri[entity_id] = self.ns[sanitized_name]
            self.entity_id_to_name[entity_id] = name
            # Also map by name for simple format lookups
            self.entity_id_to_uri[name] = self.ns[sanitized_name]
        
        # Second pass: add full entity type definitions
        for entity in entity_types:
            self._add_entity_type(entity)
        
        # Add relationship types
        for relationship in relationship_types:
            self._add_relationship_type(relationship)
        
        # Serialize to TTL
        ttl_output = self.graph.serialize(format='turtle')
        
        logger.info(f"Generated TTL with {len(self.graph)} triples")
        
        return ttl_output
    
    def convert_file(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Convert a Fabric definition JSON file to TTL.
        
        Args:
            input_path: Path to the Fabric definition JSON file
            output_path: Optional path to write the TTL output
            
        Returns:
            TTL string
            
        Raises:
            ValueError: If path traversal detected or invalid extension
            FileNotFoundError: If input file not found
            PermissionError: If file not readable/writable
        """
        # Import from core.validators (shared module)
        from core.validators import InputValidator
        
        # Validate input path with security checks
        validated_input_path = InputValidator.validate_file_path(
            input_path,
            allowed_extensions=['.json'],
            check_exists=True,
            check_readable=True
        )
        
        with open(validated_input_path, 'r', encoding='utf-8') as f:
            fabric_definition = json.load(f)
        
        ttl_output = self.convert(fabric_definition)
        
        if output_path:
            # Validate output path with security checks
            validated_output_path = InputValidator.validate_output_file_path(
                output_path,
                allowed_extensions=['.ttl', '.rdf', '.owl', '.n3']
            )
            
            with open(validated_output_path, 'w', encoding='utf-8') as f:
                f.write(ttl_output)
            logger.info(f"Saved TTL to {validated_output_path}")
        
        return ttl_output


def compare_ontologies(ttl1: str, ttl2: str) -> Dict[str, Any]:
    """
    Compare two TTL ontologies and return differences.
    
    This function compares the semantic content, not the exact string representation.
    It extracts classes, properties, and relationships and compares them.
    
    Args:
        ttl1: First TTL string (e.g., original)
        ttl2: Second TTL string (e.g., exported)
        
    Returns:
        Dict with comparison results including:
        - matches: bool indicating if ontologies are semantically equivalent
        - classes_match: bool
        - properties_match: bool
        - relationships_match: bool
        - original_classes: set of class names
        - exported_classes: set of class names
        - missing_classes: set of classes in original but not exported
        - extra_classes: set of classes in exported but not original
        - (similar for properties and relationships)
    """
    g1: Graph = Graph()
    g2: Graph = Graph()
    
    g1.parse(data=ttl1, format='turtle')
    g2.parse(data=ttl2, format='turtle')
    
    def extract_local_name(uri):
        """Extract local name from URI."""
        uri_str = str(uri)
        if '#' in uri_str:
            return uri_str.split('#')[-1]
        elif '/' in uri_str:
            return uri_str.split('/')[-1]
        return uri_str
    
    def get_classes(graph: Graph) -> Set[str]:
        """Extract class names from graph."""
        classes = set()
        for s, p, o in graph.triples((None, RDF.type, OWL.Class)):
            classes.add(extract_local_name(s))
        return classes
    
    def get_datatype_properties(graph: Graph) -> Set[str]:
        """Extract datatype property names from graph."""
        props = set()
        for s, p, o in graph.triples((None, RDF.type, OWL.DatatypeProperty)):
            props.add(extract_local_name(s))
        return props
    
    def get_object_properties(graph: Graph) -> Set[str]:
        """Extract object property names from graph."""
        props = set()
        for s, p, o in graph.triples((None, RDF.type, OWL.ObjectProperty)):
            props.add(extract_local_name(s))
        return props
    
    # Extract components from both graphs
    classes1 = get_classes(g1)
    classes2 = get_classes(g2)
    
    datatype_props1 = get_datatype_properties(g1)
    datatype_props2 = get_datatype_properties(g2)
    
    object_props1 = get_object_properties(g1)
    object_props2 = get_object_properties(g2)
    
    # Compare
    result = {
        # Overall match - using is_equivalent for test compatibility
        "is_equivalent": False,
        "matches": False,
        
        # Class comparison - using structured format for test compatibility
        "classes": {
            "count1": len(classes1),
            "count2": len(classes2),
            "only_in_first": list(classes1 - classes2),
            "only_in_second": list(classes2 - classes1),
            "match": classes1 == classes2,
        },
        "classes_match": classes1 == classes2,
        "original_classes": classes1,
        "exported_classes": classes2,
        "missing_classes": classes1 - classes2,
        "extra_classes": classes2 - classes1,
        "class_count_original": len(classes1),
        "class_count_exported": len(classes2),
        
        # Datatype property comparison
        "datatype_properties": {
            "count1": len(datatype_props1),
            "count2": len(datatype_props2),
            "only_in_first": list(datatype_props1 - datatype_props2),
            "only_in_second": list(datatype_props2 - datatype_props1),
            "match": datatype_props1 == datatype_props2,
        },
        "datatype_properties_match": datatype_props1 == datatype_props2,
        "original_datatype_properties": datatype_props1,
        "exported_datatype_properties": datatype_props2,
        "missing_datatype_properties": datatype_props1 - datatype_props2,
        "extra_datatype_properties": datatype_props2 - datatype_props1,
        "datatype_property_count_original": len(datatype_props1),
        "datatype_property_count_exported": len(datatype_props2),
        
        # Object property comparison
        "object_properties": {
            "count1": len(object_props1),
            "count2": len(object_props2),
            "only_in_first": list(object_props1 - object_props2),
            "only_in_second": list(object_props2 - object_props1),
            "match": object_props1 == object_props2,
        },
        "object_properties_match": object_props1 == object_props2,
        "original_object_properties": object_props1,
        "exported_object_properties": object_props2,
        "missing_object_properties": object_props1 - object_props2,
        "extra_object_properties": object_props2 - object_props1,
        "object_property_count_original": len(object_props1),
        "object_property_count_exported": len(object_props2),
        
        # Triple counts
        "triple_count_original": len(g1),
        "triple_count_exported": len(g2),
    }
    
    # Overall match if all components match
    result["matches"] = (
        result["classes_match"] and 
        result["datatype_properties_match"] and 
        result["object_properties_match"]
    )
    result["is_equivalent"] = result["matches"]
    
    return result


def round_trip_test(ttl_content: str, base_namespace: str = "http://example.org/ontology#") -> Dict[str, Any]:
    """
    Perform a round-trip test: TTL -> Fabric -> TTL and compare.
    
    Args:
        ttl_content: Original TTL content
        base_namespace: Namespace to use for export
        
    Returns:
        Comparison results from compare_ontologies()
    """
    from rdf_converter import parse_ttl_content
    
    try:
        # Step 1: Parse TTL to Fabric definition
        fabric_definition, ontology_name = parse_ttl_content(ttl_content)
        
        logger.info(f"Round-trip test: Parsed original TTL, generated {len(fabric_definition.get('parts', []))} parts")
        
        # Step 2: Convert Fabric definition back to TTL
        exporter = FabricToTTLConverter(base_namespace=base_namespace)
        exported_ttl = exporter.convert(fabric_definition)
        
        logger.info(f"Round-trip test: Exported back to TTL")
        
        # Step 3: Compare original and exported TTL
        comparison = compare_ontologies(ttl_content, exported_ttl)
        
        # Return structured result with success flag
        return {
            "success": True,
            "comparison": comparison,
            "exported_ttl": exported_ttl,
            "fabric_definition_parts": len(fabric_definition.get('parts', [])),
            "ontology_name": ontology_name,
        }
    except Exception as e:
        logger.error(f"Round-trip test failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "comparison": None,
        }


# Convenience function for CLI
def export_ontology_to_ttl(
    fabric_definition: Dict[str, Any],
    output_path: Optional[str] = None,
    base_namespace: str = "http://example.org/ontology#"
) -> str:
    """
    Export a Fabric ontology definition to TTL format.
    
    Args:
        fabric_definition: Fabric ontology definition (from API or file)
        output_path: Optional path to write the TTL file
        base_namespace: Base namespace for the ontology
        
    Returns:
        TTL string
        
    Raises:
        ValueError: If path traversal detected in output_path
        PermissionError: If output directory not writable
    """
    converter = FabricToTTLConverter(base_namespace=base_namespace)
    ttl_output = converter.convert(fabric_definition)
    
    if output_path:
        # Import from core.validators (shared module)
        from core.validators import InputValidator
        
        # Validate output path with security checks
        validated_output_path = InputValidator.validate_output_file_path(
            output_path,
            allowed_extensions=['.ttl', '.rdf', '.owl', '.n3']
        )
        
        with open(validated_output_path, 'w', encoding='utf-8') as f:
            f.write(ttl_output)
        logger.info(f"Exported ontology to {output_path}")
    
    return ttl_output
