# RDF/OWL to Fabric Ontology Guide

This guide provides comprehensive information about importing **RDF/OWL ontologies** (Turtle/TTL format) into Microsoft Fabric Ontology.

## Table of Contents

- [What is RDF/OWL?](#what-is-rdfowl)
- [RDF Commands](#rdf-commands)
- [RDF to Fabric Mapping](#rdf-to-fabric-mapping)
- [What Gets Converted?](#what-gets-converted)
- [RDF Validation Checks](#rdf-validation-checks)
- [Examples](#examples)
- [Key Considerations](#key-considerations)

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

> **📘 For complete command reference, see [COMMANDS.md](COMMANDS.md#rdf-commands)**

This section shows the typical workflow for working with RDF/TTL ontologies.

### Quick Workflow

```powershell
# 1. Validate your TTL file
python src\main.py rdf-validate ontology.ttl --verbose

# 2. Convert to Fabric JSON (optional - for inspection)
python src\main.py rdf-convert ontology.ttl --output fabric_output.json

# 3. Upload to Fabric
python src\main.py rdf-upload ontology.ttl --name "MyOntology"

# 4. Export back to TTL (optional - for verification)
python src\main.py rdf-export <ontology-id> --output exported.ttl
```

### Available Commands

| Command | Purpose |
|---------|----------|
| `rdf-validate` | Validate TTL syntax and Fabric compatibility |
| `rdf-convert` | Convert TTL to Fabric JSON (no upload) |
| `rdf-upload` | Full pipeline: validate → convert → upload |
| `rdf-export` | Export Fabric ontology to TTL format |

### Common Options

- `--recursive` - Process directories recursively
- `--verbose` - Show detailed output
- `--output` - Specify output file path
- `--streaming` - Use memory-efficient mode for large files (>100MB)
- `--config` - Use custom configuration file

**See [COMMANDS.md](COMMANDS.md#rdf-commands) for:**
- Complete command syntax and all options
- Batch processing examples
- Streaming mode details
- Advanced configuration

## RDF to Fabric Mapping

> **📘 For complete mapping details, see [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md#rdf-supported-constructs)**

The converter maps RDF/OWL concepts to Fabric Ontology:

- **Classes** (`owl:Class`, `rdfs:Class`) → EntityType
- **Datatype Properties** (`owl:DatatypeProperty`) → EntityTypeProperty with XSD type mapping
- **Object Properties** (`owl:ObjectProperty`) → RelationshipType
- **Inheritance** (`rdfs:subClassOf`) → baseEntityTypeId (single parent only)
- **Labels & Comments** (`rdfs:label`, `rdfs:comment`) → displayName and description

**XSD Type Mapping:** Standard XSD types (string, boolean, integer, decimal, date, dateTime, etc.) are mapped to equivalent Fabric property types. Unsupported types default to String.

## What Gets Converted?

> **📘 For complete feature support matrix, see [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md#rdf-supported-constructs)**

### ✅ Fully Supported
- Classes, datatype properties, object properties
- Simple inheritance (single parent)
- Domain/range declarations
- Labels, comments, and standard XSD types

### ⚠️ Limited Support
- Multiple inheritance (first parent only)
- Complex class expressions (simplified)
- Property characteristics (metadata only)

### ❌ Not Supported
- OWL Restrictions (cardinality, value constraints)
- Property chains, inverse properties
- External imports (must merge first)
- Reasoning/inference

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

## Key Considerations

> **📘 For comprehensive limitations and workarounds, see [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md)**

### Information Loss During Conversion

RDF/OWL has rich semantics that may not fully translate to Fabric Ontology:

- **OWL Restrictions** (cardinality, value constraints) are not enforced
- **Property characteristics** (transitivity, symmetry) are metadata only
- **Multiple inheritance** is simplified to single parent
- **Complex expressions** are flattened to named classes
- **External imports** must be merged before conversion
- **Reasoning/inference** is not performed

### Before You Convert

1. **Validate first:** `python src\main.py rdf-validate your_file.ttl --verbose`
2. **Review the report:** Check for unsupported constructs
3. **Merge external ontologies:** Ensure all referenced classes are declared locally
4. **Document constraints:** Keep track of restrictions that won't be preserved

### Compliance Reports

Generate detailed reports showing what will be preserved, limited, or lost:

```python
from rdf import RDFToFabricConverter

converter = RDFToFabricConverter()
result, report = converter.parse_ttl_with_compliance_report(ttl_content)

if report:
    print(f"⚠️  Warnings: {len(report.warnings)}")
    for warning in report.warnings:
        print(f"[{warning.severity}] {warning.message}")
```

### See Also

- **[MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md)** - Complete technical reference for RDF/DTDL conversion constraints
- **[W3C RDF/OWL Specifications](https://www.w3.org/RDF/)** - Official standards documentation
- **[Fabric Ontology API](API.md)** - Microsoft Fabric API reference

## Related Resources

- [RDF 1.1 Turtle Specification](https://www.w3.org/TR/turtle/)
- [OWL 2 Web Ontology Language Primer](https://www.w3.org/TR/owl2-primer/)
- [RDFLib Python Library](https://github.com/RDFLib/rdflib)
- [Schema.org Vocabularies](https://schema.org/) - Example RDF vocabularies
- [DBpedia Ontology](https://www.dbpedia.org/resources/ontology/) - Large RDF ontology example
