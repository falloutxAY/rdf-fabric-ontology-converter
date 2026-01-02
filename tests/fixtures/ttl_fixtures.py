"""
TTL/RDF test fixtures for the test suite.

Contains various RDF/TTL content samples for testing the converter,
validator, and related functionality.
"""

# =============================================================================
# Simple TTL Content
# =============================================================================

SIMPLE_TTL = """
@prefix : <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:Person a owl:Class ;
    rdfs:label "Person" ;
    rdfs:comment "A human being" .

:Organization a owl:Class ;
    rdfs:label "Organization" .

:name a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:string .

:age a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:integer .

:worksFor a owl:ObjectProperty ;
    rdfs:domain :Person ;
    rdfs:range :Organization .
"""

EMPTY_TTL = ""

MINIMAL_TTL = """
@prefix : <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:Person a owl:Class ;
    rdfs:label "Person" .

:name a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:range xsd:string .
"""


# =============================================================================
# Complex TTL Content
# =============================================================================

INHERITANCE_TTL = """
@prefix : <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:Animal a owl:Class .
:Mammal a owl:Class ;
    rdfs:subClassOf :Animal .
:Dog a owl:Class ;
    rdfs:subClassOf :Mammal .
"""

MULTIPLE_DOMAINS_TTL = """
@prefix : <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:Person a owl:Class .
:Organization a owl:Class .

:name a owl:DatatypeProperty ;
    rdfs:domain :Person ;
    rdfs:domain :Organization ;
    rdfs:range xsd:string .
"""

UNION_DOMAIN_TTL = """
@prefix : <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:Person a owl:Class .
:Organization a owl:Class .

:name a owl:DatatypeProperty ;
    rdfs:domain [
        a owl:Class ;
        owl:unionOf ( :Person :Organization )
    ] ;
    rdfs:range xsd:string .
"""


# =============================================================================
# Edge Case TTL Content
# =============================================================================

RESTRICTION_TTL = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <http://example.org/> .

ex:Person a owl:Class ;
    rdfs:subClassOf [
        a owl:Restriction ;
        owl:onProperty ex:age ;
        owl:minCardinality 1
    ] .

ex:age a owl:DatatypeProperty ;
    rdfs:domain ex:Person ;
    rdfs:range xsd:integer .
"""

FUNCTIONAL_PROPERTY_TTL = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <http://example.org/> .

ex:Person a owl:Class .

ex:ssn a owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain ex:Person ;
    rdfs:range xsd:string .
"""

EXTERNAL_IMPORT_TTL = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/> .

<http://example.org/ontology> a owl:Ontology ;
    owl:imports <http://xmlns.com/foaf/0.1/> .

ex:Person a owl:Class .
"""

MISSING_DOMAIN_TTL = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <http://example.org/> .

ex:Person a owl:Class .

ex:name a owl:DatatypeProperty ;
    rdfs:range xsd:string .
"""

MISSING_RANGE_TTL = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/> .

ex:Person a owl:Class .

ex:name a owl:DatatypeProperty ;
    rdfs:domain ex:Person .
"""


# =============================================================================
# Large/Stress Test TTL Content
# =============================================================================

LARGE_TTL_TEMPLATE = """
@prefix : <http://example.org/large/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

{classes}

{properties}

{relationships}
"""


def generate_large_ttl(
    num_classes: int = 100,
    properties_per_class: int = 5,
    relationships_per_class: int = 2
) -> str:
    """
    Generate a large TTL file for stress testing.
    
    Args:
        num_classes: Number of classes to generate
        properties_per_class: Number of datatype properties per class
        relationships_per_class: Number of object properties per class
        
    Returns:
        Generated TTL content string
    """
    classes = []
    properties = []
    relationships = []
    
    # Generate classes
    for i in range(num_classes):
        class_name = f"Class{i:04d}"
        classes.append(f":{class_name} a owl:Class .")
        
        # Generate properties for this class
        for j in range(properties_per_class):
            prop_name = f"{class_name}_prop{j}"
            properties.append(f"""
:{prop_name} a owl:DatatypeProperty ;
    rdfs:domain :{class_name} ;
    rdfs:range xsd:string .""")
        
        # Generate relationships for this class
        for k in range(relationships_per_class):
            rel_name = f"{class_name}_rel{k}"
            target_class = f"Class{(i + k + 1) % num_classes:04d}"
            relationships.append(f"""
:{rel_name} a owl:ObjectProperty ;
    rdfs:domain :{class_name} ;
    rdfs:range :{target_class} .""")
    
    return LARGE_TTL_TEMPLATE.format(
        classes="\n".join(classes),
        properties="\n".join(properties),
        relationships="\n".join(relationships)
    )
