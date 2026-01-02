# RDF/OWL to Fabric Ontology Guide

This guide provides comprehensive information about importing **RDF/OWL ontologies** (Turtle/TTL format) into Microsoft Fabric Ontology.

## Table of Contents

- [What is RDF/OWL?](#what-is-rdfowl)
- [RDF Commands](#rdf-commands)
- [RDF to Fabric Mapping](#rdf-to-fabric-mapping)
- [Supported RDF Features](#supported-rdf-features)
- [RDF Validation Checks](#rdf-validation-checks)
- [Examples](#examples)
- [Limitations](#limitations)

## What is RDF/OWL?

[RDF (Resource Description Framework)](https://www.w3.org/RDF/) and [OWL (Web Ontology Language)](https://www.w3.org/OWL/) are W3C standards for representing knowledge and ontologies. RDF provides the foundation for expressing graph-based data, while OWL adds rich semantics for defining classes, properties, and relationships.

**Key concepts:**
- **Classes** (`owl:Class`, `rdfs:Class`) - Types of resources
- **Properties** (`owl:DatatypeProperty`, `owl:ObjectProperty`) - Attributes and relationships
- **Inheritance** (`rdfs:subClassOf`) - Class hierarchies
- **Domains and Ranges** (`rdfs:domain`, `rdfs:range`) - Property constraints
- **Restrictions** (`owl:Restriction`) - Complex property constraints

RDF/OWL is widely used for semantic web applications, knowledge graphs, and data integration scenarios.

## RDF Commands

### Validate RDF/TTL

Validate RDF ontologies before conversion to catch syntax errors, missing declarations, and unsupported constructs.

```powershell
# Validate a single TTL file
python src\main.py rdf-validate path/to/ontology.ttl

# Validate a directory of TTL files recursively
python src\main.py rdf-validate path/to/ontologies/ --recursive --verbose

# Save validation report to JSON
python src\main.py rdf-validate path/to/ontology.ttl --output validation_report.json

# Validate and save auto-named report
python src\main.py rdf-validate path/to/ontology.ttl --save-report
```

**Validation checks performed:**
- RDF syntax validation (Turtle format)
- Prefix and namespace resolution
- Class and property declarations
- Domain/range consistency
- Unsupported OWL construct detection
- Fabric API compatibility checks
- Large ontology warnings (>1000 entities)

### Convert RDF/TTL (without upload)

Convert RDF to Fabric JSON format for inspection without uploading to Fabric.

```powershell
# Convert TTL to Fabric JSON format for inspection
python src\main.py rdf-convert path/to/ontology.ttl --output fabric_output.json

# With custom namespace
python src\main.py rdf-convert path/to/ontology.ttl --namespace myontology --output output.json

# Batch convert directory
python src\main.py rdf-convert path/to/ontologies/ --recursive --output converted/
```

### Import RDF/TTL to Fabric

Full pipeline: validate → convert → upload to Microsoft Fabric Ontology.

```powershell
# Full import: validate → convert → upload
python src\main.py rdf-upload path/to/ontology.ttl --name "MyOntology"

# Dry run: validate and convert without uploading
python src\main.py rdf-upload path/to/ontology.ttl --dry-run --output preview.json

# With custom namespace
python src\main.py rdf-upload path/to/ontology.ttl --namespace myontology --name "MyOntology"

# Batch upload directory
python src\main.py rdf-upload path/to/ontologies/ --recursive --name "MultiOntology"

# Update existing ontology
python src\main.py rdf-upload path/to/ontology.ttl --name "MyOntology" --update

# Skip validation (not recommended)
python src\main.py rdf-upload path/to/ontology.ttl --skip-validation --name "RiskyOntology"

# Streaming mode for large files (memory-efficient)
python src\main.py rdf-upload large_ontology.ttl --streaming --name "LargeOntology"
```

### Export Fabric to TTL

Export existing Fabric ontology back to RDF/TTL format for sharing or round-trip validation.

```powershell
# Export ontology to TTL
python src\main.py fabric-to-ttl --name "MyOntology" --output exported.ttl

# Export with custom base URI
python src\main.py fabric-to-ttl --name "MyOntology" --base-uri "http://example.com/ontology#" --output exported.ttl
```

## RDF to Fabric Mapping

The converter maps RDF/OWL concepts to Microsoft Fabric Ontology equivalents:

| RDF/OWL Concept | Fabric Ontology Equivalent | Notes |
|-----------------|----------------------------|-------|
| `owl:Class` / `rdfs:Class` | EntityType | Direct mapping with name and description |
| `owl:DatatypeProperty` | Property (static) | XSD datatypes mapped to Fabric types |
| `owl:ObjectProperty` | RelationshipType | With target entity type constraints |
| `rdfs:subClassOf` | BaseEntityTypeId | Simple inheritance only |
| `rdfs:domain` | Property assignment | Determines which entity owns the property |
| `rdfs:range` (datatype) | Property valueType | XSD types → Fabric types |
| `rdfs:range` (class) | Relationship target | Target entity type for relationships |
| `rdfs:label` | DisplayName | Preferred label used as display name |
| `rdfs:comment` | Description | Documentation text preserved |
| `owl:Ontology` | Ontology metadata | Version and import information |

### Type Mapping

XSD datatypes are mapped to Fabric property types as follows:

| XSD Datatype | Fabric Property Type | Notes |
|-------------|---------------------|-------|
| `xsd:string` | String | Unicode text |
| `xsd:boolean` | Boolean | true/false |
| `xsd:integer` | Integer | 32-bit signed integer |
| `xsd:int` | Integer | Alias for integer |
| `xsd:long` | Long | 64-bit signed integer |
| `xsd:decimal` | Decimal | High-precision decimal |
| `xsd:double` | Double | 64-bit floating point |
| `xsd:float` | Float | 32-bit floating point |
| `xsd:date` | Date | ISO 8601 date format |
| `xsd:dateTime` | DateTime | ISO 8601 datetime format |
| `xsd:time` | Time | ISO 8601 time format |
| `xsd:duration` | Duration | ISO 8601 duration format |
| `xsd:anyURI` | String | URI as string |
| **Unsupported** | String (default) | Unknown types mapped to String |

## Supported RDF Features

### Fully Supported

- ✅ **Classes** (`owl:Class`, `rdfs:Class`)
- ✅ **Datatype Properties** (`owl:DatatypeProperty`)
- ✅ **Object Properties** (`owl:ObjectProperty`)
- ✅ **Simple inheritance** (`rdfs:subClassOf` with single parent)
- ✅ **Domain/range declarations** (`rdfs:domain`, `rdfs:range`)
- ✅ **Labels and comments** (`rdfs:label`, `rdfs:comment`)
- ✅ **XSD primitive types** (string, boolean, integer, decimal, date, etc.)
- ✅ **Namespace prefixes** (standard RDF prefix handling)

### Limited Support

- ⚠️ **Multiple inheritance** - Only first parent in subClassOf chain is used
- ⚠️ **Complex subClassOf expressions** - Restrictions flattened to simple inheritance
- ⚠️ **Union/intersection of classes** - Extracted members as separate entities
- ⚠️ **Property characteristics** (Functional, Transitive, etc.) - Metadata only, not enforced
- ⚠️ **Annotation properties** - Stored as metadata, not as entity properties

### Not Supported

- ❌ **OWL Restrictions** (`owl:Restriction`, cardinality, value constraints) - Ignored
- ❌ **Property chains** (`owl:propertyChainAxiom`) - Not converted
- ❌ **Inverse properties** (`owl:inverseOf`) - Manual creation needed
- ❌ **Class equivalence** (`owl:equivalentClass`) - Skipped
- ❌ **External imports** (`owl:imports`) - Must be merged before conversion
- ❌ **Complex class expressions** (negation, complement) - Simplified
- ❌ **Reasoning/inference** - Explicit triples only

## RDF Validation Checks

The `rdf-validate` command performs comprehensive checks:

### Syntax Validation
- **TTL format** - Validates Turtle syntax
- **Prefix declarations** - Ensures all prefixes are declared
- **URI resolution** - Checks for malformed URIs
- **Triple structure** - Validates subject-predicate-object patterns

### Semantic Validation
- **Class declarations** - Warns about undeclared classes used in domain/range
- **Property signatures** - Checks for missing domain/range declarations
- **Type consistency** - Validates range values match declared types
- **Inheritance cycles** - Detects circular subClassOf chains

### Fabric Compatibility
- **Entity name length** - Warns if names exceed 256 characters
- **Property count** - Alerts when entities have >200 properties
- **Large ontologies** - Warns when >1000 entity types detected
- **Unsupported constructs** - Lists OWL features that will be skipped

## Examples

### Example 1: Simple Product Ontology

**Input TTL** (samples/rdf/sample_supply_chain_ontology.ttl):
```turtle
@prefix : <http://example.com/supply#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:Product a owl:Class ;
    rdfs:label "Product" ;
    rdfs:comment "A product in the supply chain" .

:hasName a owl:DatatypeProperty ;
    rdfs:label "has name" ;
    rdfs:domain :Product ;
    rdfs:range xsd:string .

:hasPrice a owl:DatatypeProperty ;
    rdfs:label "has price" ;
    rdfs:domain :Product ;
    rdfs:range xsd:decimal .
```

**Conversion:**
```powershell
python src\main.py rdf-upload samples/rdf/sample_supply_chain_ontology.ttl --name "SupplyChain"
```

**Result:**
- EntityType: `Product` with description
- Property: `hasName` (String)
- Property: `hasPrice` (Decimal)

### Example 2: IoT Device Ontology with Relationships

**Input TTL** (samples/rdf/sample_iot_ontology.ttl):
```turtle
@prefix : <http://example.com/iot#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:Device a owl:Class ;
    rdfs:label "Device" ;
    rdfs:comment "An IoT device" .

:Sensor a owl:Class ;
    rdfs:label "Sensor" ;
    rdfs:subClassOf :Device ;
    rdfs:comment "A sensor device" .

:locatedIn a owl:ObjectProperty ;
    rdfs:label "located in" ;
    rdfs:domain :Device ;
    rdfs:range :Location .

:Location a owl:Class ;
    rdfs:label "Location" ;
    rdfs:comment "A physical location" .
```

**Result:**
- EntityType: `Device` with description
- EntityType: `Sensor` extending `Device`
- EntityType: `Location` with description
- RelationshipType: `locatedIn` from `Device` to `Location`

### Example 3: FOAF Ontology

The Friend of a Friend (FOAF) ontology has been successfully tested:

```powershell
# Import the FOAF ontology
python src\main.py rdf-upload samples/rdf/sample_foaf_ontology.ttl --name "FOAF"
```

This demonstrates conversion of a standard semantic web vocabulary with:
- Person, Agent, Document classes
- Social relationships (knows, friend)
- Properties for names, emails, homepages
- Complex class hierarchies

## Limitations

> **📘 For comprehensive limitations, see [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md)**  
> This section provides a quick overview of the most important limitations.

### Key Information Loss

When converting RDF/OWL to Fabric Ontology, **semantic information may be lost or simplified**:

| RDF/OWL Feature | Impact |
|-----------------|--------|
| **OWL Restrictions** | Cardinality and value constraints not enforced |
| **Property characteristics** | Transitivity, symmetry, functionality not enforced |
| **Multiple inheritance** | Only first parent in subClassOf chain used |
| **Complex class expressions** | Simplified to named classes only |
| **External imports** | Not automatically resolved |
| **Reasoning/inference** | Not performed - only explicit triples converted |

**See [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md) for:**
- Complete list of 25+ unsupported OWL constructs
- Detailed workarounds and recommendations
- Fabric API limits and compliance requirements
- Best practices for RDF sources

### Validation & Compliance Reports

Use the compliance report feature to understand what will be preserved, limited, or lost:

```python
from rdf import RDFToFabricConverter

converter = RDFToFabricConverter()
result, report = converter.parse_ttl_with_compliance_report(ttl_content)

if report:
    print(f"✅ Classes found: {report.summary['declared_classes']}")
    print(f"✅ Properties found: {report.summary['declared_properties']}")
    print(f"⚠️  Warnings: {len(report.warnings)}")
    
    for warning in report.warnings:
        print(f"[{warning.severity}] {warning.message}")
```

### See Also

- **[Mapping Limitations](MAPPING_LIMITATIONS.md)** - Full list of RDF/DTDL → Fabric conversion constraints
- **[W3C RDF Specification](https://www.w3.org/RDF/)** - Official RDF documentation
- **[W3C OWL Specification](https://www.w3.org/OWL/)** - Official OWL documentation
- **[Fabric Ontology API](API.md)** - Microsoft Fabric Ontology REST API reference

## Related Resources

- [RDF 1.1 Turtle Specification](https://www.w3.org/TR/turtle/)
- [OWL 2 Web Ontology Language Primer](https://www.w3.org/TR/owl2-primer/)
- [RDFLib Python Library](https://github.com/RDFLib/rdflib)
- [Schema.org Vocabularies](https://schema.org/) - Example RDF vocabularies
- [DBpedia Ontology](https://www.dbpedia.org/resources/ontology/) - Large RDF ontology example
