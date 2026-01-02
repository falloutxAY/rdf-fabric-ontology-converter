# Ontology Conversion: Mapping Limitations & Compliance

This document details the mapping limitations when converting RDF/OWL and DTDL ontologies to Microsoft Fabric Ontology format, including compliance requirements and information loss during conversion.

## Table of Contents

- [Overview](#overview)
- [RDF/OWL to Fabric Conversion](#rdfowl-to-fabric-conversion)
  - [Supported Constructs](#rdf-supported-constructs)
  - [Partially Supported Constructs](#rdf-partially-supported-constructs)
  - [Unsupported Constructs](#rdf-unsupported-constructs)
- [DTDL to Fabric Conversion](#dtdl-to-fabric-conversion)
  - [Supported Features](#dtdl-supported-features)
  - [Partially Supported Features](#dtdl-partially-supported-features)
  - [Unsupported Features](#dtdl-unsupported-features)
  - [Version-Specific Limits](#dtdl-version-limits)
- [Fabric API Limits](#fabric-api-limits)
- [Pre-flight Validation](#pre-flight-validation)
- [Compliance Reports](#compliance-reports)
- [Best Practices](#best-practices)

---

## Overview

Ontology conversion involves mapping between different knowledge representation formats. RDF/OWL is highly expressive with inference-driven semantics, while DTDL is designed for digital twins, and Fabric Ontology targets business-friendly models for data products.

**Key principles:**
- Conversions are **not 1:1** — complex constructs are simplified or skipped
- Information may be **lost** or **transformed** during conversion
- The converter generates **warnings** for unsupported constructs
- Use **compliance reports** to understand conversion impact

---

## RDF/OWL to Fabric Conversion

### RDF Supported Constructs

| OWL/RDF Construct | Fabric Mapping | Support Level |
|-------------------|----------------|---------------|
| `owl:Class` | EntityType | ✅ Full |
| `rdfs:Class` | EntityType | ✅ Full |
| `rdfs:subClassOf` (simple) | baseEntityTypeId | ✅ Full |
| `owl:DatatypeProperty` | EntityTypeProperty | ✅ Full |
| `owl:ObjectProperty` | RelationshipType | ✅ Full |
| `rdfs:domain` | Property assignment to entity | ✅ Full |
| `rdfs:range` (datatype) | valueType | ✅ Full |
| `rdfs:range` (class) | Relationship target | ✅ Full |
| `rdfs:label` | name, displayName | ✅ Full |
| `rdfs:comment` | description (metadata) | ✅ Full |

### RDF Partially Supported Constructs

| OWL/RDF Construct | Fabric Mapping | Notes |
|-------------------|----------------|-------|
| `owl:unionOf` (classes) | Multiple relationships | Creates separate relationships for each member |
| `owl:unionOf` (datatypes) | Most restrictive type | Multiple types unified to single Fabric type |
| `owl:intersectionOf` | Class extraction | Extracts named classes, ignores complex restrictions |
| `rdfs:subClassOf` (complex) | Flattened | Restrictions and expressions simplified |
| `owl:equivalentClass` | Skipped | Entity ID mapping not preserved |
| `owl:sameAs` | Instance scope | Out of converter scope (instances) |

### RDF Unsupported Constructs

| OWL/RDF Construct | Impact | Recommendation |
|-------------------|--------|----------------|
| **owl:Restriction** | Cardinality/value constraints lost | Document constraints separately |
| **owl:allValuesFrom** | Universal restriction lost | Use explicit property typing |
| **owl:someValuesFrom** | Existential restriction lost | Use explicit property typing |
| **owl:hasValue** | Value restriction lost | Use explicit properties |
| **owl:minCardinality** | Cardinality constraint lost | Document in schema |
| **owl:maxCardinality** | Cardinality constraint lost | Document in schema |
| **owl:exactCardinality** | Cardinality constraint lost | Document in schema |
| **owl:TransitiveProperty** | Transitivity not enforced | Pre-compute transitive closure |
| **owl:SymmetricProperty** | Symmetry not enforced | Create inverse relationships |
| **owl:FunctionalProperty** | Uniqueness not enforced | Document in schema |
| **owl:InverseFunctionalProperty** | Uniqueness not enforced | Document in schema |
| **owl:ReflexiveProperty** | Reflexivity not enforced | Create self-referential data |
| **owl:IrreflexiveProperty** | Irreflexivity not enforced | Validate data separately |
| **owl:AsymmetricProperty** | Asymmetry not enforced | Validate data separately |
| **owl:disjointWith** | Disjointness not enforced | Validate data separately |
| **owl:complementOf** | Negation lost | Use explicit typing |
| **owl:oneOf** | Enumeration extracted | Class members as separate entities |
| **owl:propertyChainAxiom** | Property chains lost | Pre-compute derived relationships |
| **owl:inverseOf** | Inverse relationships not auto-created | Manually create inverse |
| **owl:imports** | External imports not resolved | Merge external ontologies first |
| **owl:AnnotationProperty** | Stored as metadata | Not available as entity properties |
| **owl:deprecated** | Metadata only | Not enforced |
| **owl:versionInfo** | Metadata only | Track separately |
| **rdf:List** | Flattened | List structure lost |
| **SHACL shapes** | Constraints lost | Document validation rules |

---

## DTDL to Fabric Conversion

### DTDL Supported Features

| DTDL Feature | Fabric Mapping | Support Level |
|--------------|----------------|---------------|
| Interface | EntityType | ✅ Full |
| Property | EntityTypeProperty | ✅ Full |
| Telemetry | timeseriesProperties | ✅ Full |
| Relationship | RelationshipType | ✅ Full |
| extends (single) | baseEntityTypeId | ✅ Full |
| Primitive schemas | valueType | ✅ Full |
| displayName | resolved to name | ✅ Full |
| description | metadata | ✅ Full |

### DTDL Partially Supported Features

| DTDL Feature | Fabric Mapping | Notes |
|--------------|----------------|-------|
| **extends (multiple)** | First parent only | Multiple inheritance → single inheritance |
| **Component** | Configurable (see below) | Three modes: SKIP, FLATTEN, SEPARATE |
| **Command** | Configurable (see below) | Three modes: SKIP, PROPERTY, ENTITY |
| **Enum** | String | Enum values lost, maps to String |
| **Object** | JSON String | Complex nested structure serialized |
| **Array** | JSON String | Array type information lost |
| **Map** | JSON String | Key-value structure serialized |
| **scaledDecimal** (v4) | Configurable (see below) | Three modes: JSON_STRING, STRUCTURED, CALCULATED |
| **Geospatial types** | JSON String | Coordinates preserved in JSON |
| **@id (DTMI)** | Hashed to numeric ID | Original DTMI preserved in mapping |

#### Component Handling Modes

Configure via `dtdl.component_mode` in config.json or `component_mode` parameter:

| Mode | Behavior | Use When |
|------|----------|----------|
| `skip` (default) | Components ignored | You don't need component data |
| `flatten` | Properties merged into parent entity with `{component}_` prefix | Simple component structures |
| `separate` | Component becomes separate EntityType with `has_{component}` relationship | Preserve component identity |

```python
from src.dtdl import DTDLToFabricConverter, ComponentMode

# Create separate entities for components
converter = DTDLToFabricConverter(component_mode=ComponentMode.SEPARATE)
result = converter.convert(interfaces)
# Creates: EntityType for each component's schema
# Creates: RelationshipType "has_{componentName}" linking parent to component
```

#### Command Handling Modes

Configure via `dtdl.command_mode` in config.json or `command_mode` parameter:

| Mode | Behavior | Use When |
|------|----------|----------|
| `skip` (default) | Commands ignored | Commands not needed in ontology |
| `property` | Creates `command_{name}` String property | Simple command tracking |
| `entity` | Creates `Command_{name}` EntityType with request/response properties | Full command modeling |

```python
from src.dtdl import DTDLToFabricConverter, CommandMode

# Create entity types for commands
converter = DTDLToFabricConverter(command_mode=CommandMode.ENTITY)
result = converter.convert(interfaces)
# Creates: EntityType "Command_{name}" with:
#   - commandName (String, identifier)
#   - requestSchema (String, JSON)
#   - responseSchema (String, JSON)
#   - request_{param} properties for each request parameter
#   - response_{param} properties for each response parameter
# Creates: RelationshipType "supports_{commandName}" linking interface to command
```

#### ScaledDecimal Handling Modes (DTDL v4)

Configure via `dtdl.scaled_decimal_mode` in config.json or `scaled_decimal_mode` parameter:

| Mode | Behavior | Use When |
|------|----------|----------|
| `json_string` (default) | Stored as JSON: `{"scale": 7, "value": "1234.56"}` | Preserve full precision |
| `structured` | Creates `{prop}_scale` (BigInt) and `{prop}_value` (String) properties | Queryable scale/value |
| `calculated` | Calculates `value × 10^scale` as Double | Direct numeric value needed |

```python
from src.dtdl import DTDLToFabricConverter, ScaledDecimalMode

# Store calculated values
converter = DTDLToFabricConverter(scaled_decimal_mode=ScaledDecimalMode.CALCULATED)
# Property becomes Double: 1234.56 × 10^7 = 12345600000.0

# Store structured values
converter = DTDLToFabricConverter(scaled_decimal_mode=ScaledDecimalMode.STRUCTURED)
# Creates:
#   - {property}_scale (BigInt): 7
#   - {property}_value (String): "1234.56"
```

### DTDL Unsupported Features

| DTDL Feature | Impact | Recommendation |
|--------------|--------|----------------|
| **request/response schemas** | Lost in SKIP/PROPERTY modes | Use `command_mode=entity` for full modeling |
| **writable** | Mutability lost | Document field behavior |
| **unit** | Metadata only | Track units in separate documentation |
| **semanticType** | Not preserved | Document semantic types separately |
| **minMultiplicity** | Cardinality lost | Validate in data layer |
| **maxMultiplicity** | Cardinality lost | Validate in data layer |
| **target (Relationship)** | External targets ignored | Ensure targets in same conversion set |
| **properties (on Relationship)** | Lost | Model as intermediate entity |

### DTDL Version Limits

The converter validates against DTDL specification limits per version:

| Limit | DTDL v2 | DTDL v3 | DTDL v4 |
|-------|---------|---------|---------|
| Max contents per interface | 300 | 100,000 | 100,000 |
| Max extends depth | 10 | 10 | 12 |
| Max complex schema depth | 5 | 5 | 8 |
| Max name length | 64 | 512 | 512 |
| Max description length | 512 | 512 | 512 |

---

## Fabric API Limits

The Fabric Ontology API enforces these limits:

| Limit | Value | Consequence |
|-------|-------|-------------|
| Max entity name length | 256 | Names truncated with warning |
| Max property name length | 256 | Names truncated with warning |
| Max relationship name length | 256 | Names truncated with warning |
| Max properties per entity | 200 | Excess properties skipped |
| Max entity types per ontology | 1000 | Large ontologies may need partitioning |
| Max relationship types per ontology | 1000 | Large ontologies may need partitioning |
| Max namespace length | 256 | Namespace truncated with warning |
| Max entity ID parts | 10 | Composite keys limited |
| ID format | Numeric string | Non-numeric IDs converted to hash |

---

## Pre-flight Validation

Validate files before import to identify compatibility issues:

```powershell
# Quick RDF validation
python src\main.py rdf-validate samples\rdf\sample_foaf_ontology.ttl --verbose

# Save detailed report
python src\main.py rdf-validate samples\rdf\sample_foaf_ontology.ttl --output report.json

# DTDL validation
python src\main.py dtdl-validate samples\dtdl\thermostat.json --version v3

# Upload with validation (automatic)
python src\main.py rdf-upload my_ontology.ttl --name "MyOntology"
# Creates import_log_<name>_<timestamp>.json in logs/ if issues detected

# Skip validation: --skip-validation or --force
```

---

## Compliance Reports

The converter generates detailed compliance reports showing:

1. **Source Compliance Issues**
   - DTDL specification violations
   - RDF/OWL syntax issues
   - Missing required elements

2. **Conversion Warnings**
   - Features that will be preserved
   - Features with limited support
   - Features that will be lost

3. **Fabric Compliance Issues**
   - API limit violations
   - Invalid configurations
   - Recommendations for fixes

### Programmatic Access

```python
from src.dtdl.dtdl_converter import DTDLToFabricConverter
from src.dtdl.dtdl_parser import DTDLParser

# Parse DTDL
parser = DTDLParser()
interfaces = parser.parse_file("samples/dtdl/thermostat.json")

# Convert with compliance report
converter = DTDLToFabricConverter()
result, report = converter.convert_with_compliance_report(interfaces, dtdl_version="v3")

# Access report data
if report:
    print(f"Total issues: {report.total_issues}")
    for warning in report.warnings:
        print(f"[{warning.impact.value}] {warning.feature}: {warning.message}")
```

```python
from src.rdf_converter import RDFToFabricConverter

# Convert RDF with compliance report
converter = RDFToFabricConverter()
with open("samples/rdf/sample_foaf_ontology.ttl") as f:
    result, report = converter.parse_ttl_with_compliance_report(f.read())

if report:
    print(f"Total issues: {report.total_issues}")
    for warning in report.warnings:
        print(f"[{warning.impact.value}] {warning.feature}: {warning.message}")
```

---

## Best Practices

### General

✅ **Validate before converting** — Use pre-flight validation to identify issues early  
✅ **Review compliance reports** — Understand what information will be lost  
✅ **Document lost semantics** — Keep a record of constraints and rules not preserved  
✅ **Test round-trips** — Use `export` and `compare` to verify conversions  
✅ **Enable debug logging** — Set `logging.level` to `DEBUG` in config.json  

### For RDF/OWL Sources

✅ **Provide explicit signatures** — Always declare `rdfs:domain` and `rdfs:range`  
✅ **Declare all referenced classes** — Don't rely on external ontologies unless merged  
✅ **Use supported XSD types** — string, boolean, integer, decimal, date, dateTime, anyURI  
✅ **Flatten restrictions** — Convert property restrictions to explicit typed properties  
✅ **Merge imports** — Combine external ontologies before conversion  

### For DTDL Sources

✅ **Use single inheritance** — Multi-extends will use only the first parent  
✅ **Simplify complex schemas** — Objects/Arrays serialize to JSON strings  
✅ **Include targets in conversion** — Ensure relationship targets are in the same set  
✅ **Use Components sparingly** — Or enable `flatten_components` option  
✅ **Check version limits** — Ensure interface sizes match DTDL version  

### For Fabric Targets

✅ **Keep names under limits** — Entity/property names under 256 characters  
✅ **Limit properties per entity** — Stay under 200 properties  
✅ **Partition large ontologies** — Split if over 1000 entities/relationships  
✅ **Use numeric ID patterns** — IDs must be numeric strings  

---

## Common Warnings & Fixes

| Warning | Fix |
|---------|-----|
| "Skipping property due to unresolved domain/range" | Add explicit `rdfs:domain`/`rdfs:range` and declare all referenced classes locally |
| "Unresolved class target" | Declare the class in your TTL or merge the external vocabulary |
| "Unknown XSD datatype, defaulting to String" | Use supported XSD types or accept String fallback |
| "Unsupported OWL construct" | Flatten restrictions to explicit properties with signatures |
| "Multiple inheritance not supported" | Refactor to single parent or accept first-parent-only behavior |
| "Complex schema serialized to JSON" | Accept JSON representation or simplify schema |
| "Entity name exceeds Fabric limit" | Shorten name or accept truncation |
| "Too many properties" | Split entity or remove less important properties |

---

## Additional Resources

- [RDFLib documentation](https://github.com/RDFLib/rdflib)
- [DTDL Specification v2](https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v2/DTDL.v2.md)
- [DTDL Specification v3](https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v3/DTDL.v3.md)
- [Microsoft Fabric documentation](https://learn.microsoft.com/fabric/)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
- [TESTING.md](TESTING.md) - Test suite

---

*Behavior may evolve as Fabric APIs and converter capabilities expand.*
