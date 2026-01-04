"""
Constants for compliance validation.

This module contains version-specific limits, feature support tables,
and construct mappings used by the compliance validators.
"""

from .models import DTDLVersion


# =============================================================================
# DTDL Version-specific Limits
# =============================================================================

DTDL_LIMITS = {
    DTDLVersion.V2: {
        "max_contents": 300,
        "max_extends": 2,
        "max_extends_depth": 10,
        "max_complex_schema_depth": 5,
        "max_name_length": 64,
        "max_enum_values": 100,
        "max_object_fields": 30,
        "max_relationship_multiplicity": 500,
        "supports_array_in_property": False,
        "supports_semantic_types": True,
    },
    DTDLVersion.V3: {
        "max_contents": 100000,  # Total elements in hierarchy
        "max_extends": 1024,  # In hierarchy
        "max_extends_depth": 10,
        "max_complex_schema_depth": 5,
        "max_name_length": 512,
        "max_enum_values": None,  # No explicit limit
        "max_object_fields": None,  # No explicit limit
        "max_relationship_multiplicity": None,  # No explicit limit
        "supports_array_in_property": True,
        "supports_semantic_types": False,  # Moved to extension
    },
    DTDLVersion.V4: {
        "max_contents": 100000,
        "max_extends": 1024,
        "max_extends_depth": 12,
        "max_complex_schema_depth": 8,
        "max_name_length": 512,
        "max_enum_values": None,
        "max_object_fields": None,
        "max_relationship_multiplicity": None,
        "supports_array_in_property": True,
        "supports_semantic_types": False,
        "supports_self_referential_schemas": True,
        "supports_scaled_decimal": True,
        "supports_nullable_commands": True,
    },
}


# =============================================================================
# RDF/OWL Construct Support Status
# =============================================================================

OWL_CONSTRUCT_SUPPORT = {
    # Classes
    "owl:Class": {"support": "full", "fabric": True, "notes": "Maps to EntityType"},
    "rdfs:Class": {"support": "full", "fabric": True, "notes": "Maps to EntityType"},
    "rdfs:subClassOf": {"support": "full", "fabric": True, "notes": "Maps to baseEntityTypeId"},
    
    # Properties
    "owl:DatatypeProperty": {"support": "full", "fabric": True, "notes": "Maps to EntityTypeProperty"},
    "owl:ObjectProperty": {"support": "full", "fabric": True, "notes": "Maps to RelationshipType"},
    "rdfs:domain": {"support": "full", "fabric": True, "notes": "Required for property mapping"},
    "rdfs:range": {"support": "full", "fabric": True, "notes": "Required for property mapping"},
    
    # Restrictions (NOT SUPPORTED)
    "owl:Restriction": {"support": "none", "fabric": False, "notes": "Constraints not enforced in Fabric"},
    "owl:allValuesFrom": {"support": "none", "fabric": False, "notes": "Universal restriction not supported"},
    "owl:someValuesFrom": {"support": "none", "fabric": False, "notes": "Existential restriction not supported"},
    "owl:hasValue": {"support": "none", "fabric": False, "notes": "Value restriction not supported"},
    "owl:cardinality": {"support": "none", "fabric": False, "notes": "Cardinality constraints not supported"},
    "owl:minCardinality": {"support": "none", "fabric": False, "notes": "Min cardinality not supported"},
    "owl:maxCardinality": {"support": "none", "fabric": False, "notes": "Max cardinality not supported"},
    "owl:qualifiedCardinality": {"support": "none", "fabric": False, "notes": "Qualified cardinality not supported"},
    
    # Property characteristics (NOT PRESERVED)
    "owl:FunctionalProperty": {"support": "none", "fabric": False, "notes": "Functional constraint not enforced"},
    "owl:InverseFunctionalProperty": {"support": "none", "fabric": False, "notes": "Inverse functional not supported"},
    "owl:TransitiveProperty": {"support": "none", "fabric": False, "notes": "Transitivity not materialized"},
    "owl:SymmetricProperty": {"support": "none", "fabric": False, "notes": "Symmetry not materialized"},
    "owl:AsymmetricProperty": {"support": "none", "fabric": False, "notes": "Asymmetry not enforced"},
    "owl:ReflexiveProperty": {"support": "none", "fabric": False, "notes": "Reflexivity not enforced"},
    "owl:IrreflexiveProperty": {"support": "none", "fabric": False, "notes": "Irreflexivity not enforced"},
    "owl:inverseOf": {"support": "none", "fabric": False, "notes": "Inverse relationships not created"},
    "owl:propertyChainAxiom": {"support": "none", "fabric": False, "notes": "Property chains not materialized"},
    
    # Class expressions (PARTIAL SUPPORT)
    "owl:unionOf": {"support": "partial", "fabric": True, "notes": "Union expanded to multiple relationships"},
    "owl:intersectionOf": {"support": "partial", "fabric": True, "notes": "Intersection flattened"},
    "owl:complementOf": {"support": "none", "fabric": False, "notes": "Complement not representable"},
    "owl:oneOf": {"support": "partial", "fabric": True, "notes": "Enum values extracted if applicable"},
    
    # Class axioms (NOT SUPPORTED)
    "owl:equivalentClass": {"support": "none", "fabric": False, "notes": "Class equivalence not preserved"},
    "owl:disjointWith": {"support": "none", "fabric": False, "notes": "Disjointness not enforced"},
    "owl:disjointUnionOf": {"support": "none", "fabric": False, "notes": "Disjoint union not supported"},
    
    # Property axioms (NOT SUPPORTED)
    "owl:equivalentProperty": {"support": "none", "fabric": False, "notes": "Property equivalence not preserved"},
    "owl:propertyDisjointWith": {"support": "none", "fabric": False, "notes": "Property disjointness not supported"},
    
    # Imports and annotations
    "owl:imports": {"support": "none", "fabric": False, "notes": "Must merge external ontologies manually"},
    "owl:versionInfo": {"support": "metadata", "fabric": False, "notes": "Preserved in metadata only"},
    "rdfs:label": {"support": "metadata", "fabric": True, "notes": "Used for display name"},
    "rdfs:comment": {"support": "metadata", "fabric": False, "notes": "Not preserved in Fabric"},
    
    # Individuals (OUT OF SCOPE)
    "owl:NamedIndividual": {"support": "none", "fabric": False, "notes": "Instance data not converted"},
    "owl:sameAs": {"support": "none", "fabric": False, "notes": "Instance identity not supported"},
    "owl:differentFrom": {"support": "none", "fabric": False, "notes": "Instance differentiation not supported"},
}


# =============================================================================
# DTDL Feature Support Status
# =============================================================================

DTDL_FEATURE_SUPPORT = {
    # Fully Supported
    "Interface": {"support": "full", "fabric": True, "notes": "Maps to EntityType"},
    "Property": {"support": "full", "fabric": True, "notes": "Maps to EntityTypeProperty"},
    "Relationship": {"support": "full", "fabric": True, "notes": "Maps to RelationshipType"},
    "extends": {"support": "full", "fabric": True, "notes": "Maps to baseEntityTypeId (single inheritance only)"},
    
    # Partially Supported
    "Telemetry": {"support": "partial", "fabric": True, "notes": "Maps to timeseriesProperties; complex schemas flattened"},
    "Component": {"support": "partial", "fabric": True, "notes": "Flattened into parent; reference semantics lost"},
    "displayName": {"support": "partial", "fabric": True, "notes": "Single language only; localization lost"},
    "description": {"support": "none", "fabric": False, "notes": "Not preserved in Fabric"},
    "comment": {"support": "none", "fabric": False, "notes": "Not preserved in Fabric"},
    
    # Complex Schemas
    "Object": {"support": "partial", "fabric": True, "notes": "Flattened to JSON String; nested structure lost"},
    "Array": {"support": "partial", "fabric": True, "notes": "Converted to JSON String; type safety lost"},
    "Enum": {"support": "partial", "fabric": True, "notes": "Converted to String/BigInt; named values lost"},
    "Map": {"support": "partial", "fabric": True, "notes": "Converted to JSON String; key-value typing lost"},
    
    # Not Supported
    "Command": {"support": "none", "fabric": False, "notes": "Operations not representable in Fabric"},
    "writable": {"support": "none", "fabric": False, "notes": "Read/write semantics not preserved"},
    "unit": {"support": "none", "fabric": False, "notes": "Semantic units not preserved"},
    "semanticType": {"support": "none", "fabric": False, "notes": "Semantic annotations not preserved"},
    "minMultiplicity": {"support": "none", "fabric": False, "notes": "Cardinality not enforced"},
    "maxMultiplicity": {"support": "none", "fabric": False, "notes": "Cardinality not enforced"},
    
    # Geospatial
    "point": {"support": "partial", "fabric": True, "notes": "Stored as GeoJSON String"},
    "lineString": {"support": "partial", "fabric": True, "notes": "Stored as GeoJSON String"},
    "polygon": {"support": "partial", "fabric": True, "notes": "Stored as GeoJSON String"},
    
    # DTDL v4 specific
    "scaledDecimal": {"support": "partial", "fabric": True, "notes": "Stored as JSON String with scale/value"},
    "nullable": {"support": "none", "fabric": False, "notes": "Nullability not enforced"},
}
