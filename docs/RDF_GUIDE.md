# RDF/OWL to Fabric Ontology Guide

Convert RDF/OWL ontologies to Microsoft Fabric Ontology format.

## Supported Formats

| Extension | Format |
|-----------|--------|
| `.ttl` | Turtle |
| `.rdf`, `.owl` | RDF/XML |
| `.nt` | N-Triples |
| `.nq` | N-Quads |
| `.trig` | TriG |
| `.n3` | Notation3 |
| `.jsonld` | JSON-LD |

## Quick Start

```powershell
# Validate
python -m src.main validate --format rdf ontology.ttl --verbose

# Convert only
python -m src.main convert --format rdf ontology.ttl --output fabric.json

# Upload to Fabric
python -m src.main upload --format rdf ontology.ttl --ontology-name MyOntology

# Export back to TTL
python -m src.main export <ontology-id> --output exported.ttl
```

## Mapping Reference

### ✅ Fully Supported

| RDF/OWL Construct | Fabric Mapping |
|-------------------|----------------|
| `owl:Class`, `rdfs:Class` | EntityType |
| `owl:DatatypeProperty` | EntityTypeProperty |
| `owl:ObjectProperty` | RelationshipType |
| `rdfs:subClassOf` (simple) | baseEntityTypeId |
| `rdfs:domain` | Property assignment |
| `rdfs:range` (datatype) | Property valueType |
| `rdfs:range` (class) | Relationship target |
| `rdfs:label` | name, displayName |
| `rdfs:comment` | description |

### XSD Type Mapping

| XSD Type | Fabric Type |
|----------|-------------|
| `xsd:string` | String |
| `xsd:boolean` | Boolean |
| `xsd:integer`, `xsd:int`, `xsd:long` | BigInt |
| `xsd:decimal` | Decimal |
| `xsd:double`, `xsd:float` | Double |
| `xsd:dateTime`, `xsd:date`, `xsd:time` | DateTime |
| `xsd:anyURI` | String |
| Other types | String (with warning) |

### ⚠️ Limited Support

| Construct | Behavior |
|-----------|----------|
| Multiple inheritance | First parent only |
| `owl:unionOf` (classes) | Multiple relationships |
| `owl:intersectionOf` | Named classes extracted |
| Complex `rdfs:subClassOf` | Flattened to named class |

### ❌ Not Supported (Skipped)

- **Restrictions:** `owl:Restriction`, cardinality, `allValuesFrom`, `someValuesFrom`
- **Property characteristics:** `TransitiveProperty`, `SymmetricProperty`, `FunctionalProperty`
- **Class operations:** `disjointWith`, `complementOf`, `oneOf`
- **Other:** `owl:imports`, `owl:inverseOf`, property chains, SHACL shapes

## Example

**Input TTL:**
```turtle
@prefix : <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:Product a owl:Class ;
    rdfs:label "Product" ;
    rdfs:comment "A product" .

:hasName a owl:DatatypeProperty ;
    rdfs:domain :Product ;
    rdfs:range xsd:string .

:hasPrice a owl:DatatypeProperty ;
    rdfs:domain :Product ;
    rdfs:range xsd:decimal .
```

**Result:**
- EntityType: `Product`
- Property: `hasName` (String)
- Property: `hasPrice` (Decimal)

## Validation Checks

The validator checks:
- **Syntax:** Valid Turtle/RDF format
- **Prefixes:** All prefixes declared
- **Classes:** Warns about undeclared classes
- **Properties:** Checks domain/range declarations
- **Inheritance:** Detects circular subClassOf
- **Fabric limits:** Name length, property count

## Key Considerations

### Information Loss

- OWL restrictions and cardinality constraints are not preserved
- Property characteristics (transitive, symmetric) are not enforced
- External imports must be merged manually
- Reasoning/inference is not performed

### Fabric Limits

| Limit | Value |
|-------|-------|
| Entity name length | 256 chars |
| Properties per entity | 200 |
| Entity types | 500 |
| Definition size | 1 MB |

### Best Practices

1. **Validate first:** Always run `validate` before upload
2. **Keep it simple:** Avoid complex OWL constructs
3. **Declare everything:** Ensure all classes and properties are declared
4. **Use standard types:** Stick to common XSD datatypes
5. **Merge imports:** Combine ontologies before conversion

## See Also

- [CLI Commands](CLI_COMMANDS.md) - Command reference
- [DTDL Guide](DTDL_GUIDE.md) - DTDL conversion
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
