# DTDL to Fabric Ontology Guide

This guide provides comprehensive information about importing **Digital Twins Definition Language (DTDL)** models from Azure IoT/Digital Twins into Microsoft Fabric Ontology.

## Table of Contents

- [What is DTDL?](#what-is-dtdl)
- [DTDL Commands](#dtdl-commands)
- [DTDL to Fabric Mapping](#dtdl-to-fabric-mapping)
- [Supported DTDL Features](#supported-dtdl-features)
- [DTDL Validation Checks](#dtdl-validation-checks)
- [Examples](#examples)
- [Limitations](#limitations)

## What is DTDL?

[DTDL](https://learn.microsoft.com/azure/digital-twins/concepts-models) is a JSON-LD based modeling language used by Azure Digital Twins and Azure IoT. It defines:

- **Interfaces** - Digital twin types with properties, telemetry, relationships, and commands
- **Properties** - Static attributes of a twin
- **Telemetry** - Time-series sensor data  
- **Relationships** - Connections between twins
- **Components** - Reusable interface compositions

DTDL supports semantic modeling, inheritance, and type composition to create rich digital twin representations of physical environments, IoT devices, and business processes.

## DTDL Commands

### Validate DTDL

Validate DTDL models before conversion to catch schema errors, inheritance cycles, and missing references.

```powershell
# Validate a single DTDL file
python src\main.py dtdl-validate path/to/model.json

# Validate a directory of DTDL files recursively
python src\main.py dtdl-validate path/to/dtdl/ --recursive --verbose

# Save validation report to JSON
python src\main.py dtdl-validate path/to/dtdl/ --recursive --output validation_report.json
```

**Validation checks performed:**
- DTMI format validation
- JSON-LD context verification
- Schema type checking
- Inheritance cycle detection
- Relationship target validation
- Component schema validation
- Large ontology warnings (>200 interfaces)

### Convert DTDL (without upload)

Convert DTDL to Fabric JSON format for inspection without uploading to Fabric.

```powershell
# Convert DTDL to Fabric JSON format for inspection
python src\main.py dtdl-convert path/to/dtdl/ --recursive --output fabric_output.json

# With custom namespace
python src\main.py dtdl-convert path/to/dtdl/ --namespace customtypes --output output.json

# Flatten component properties into parent entities
python src\main.py dtdl-convert path/to/dtdl/ --flatten-components --output flattened.json
```

### Import DTDL to Fabric

Full pipeline: validate → convert → upload to Microsoft Fabric Ontology.

```powershell
# Full import: validate → convert → upload
python src\main.py dtdl-upload path/to/dtdl/ --recursive --ontology-name "MyDTDLOntology"

# Dry run: validate and convert without uploading
python src\main.py dtdl-upload path/to/dtdl/ --recursive --dry-run --output preview.json

# With custom namespace
python src\main.py dtdl-upload path/to/dtdl/ --namespace customtypes --ontology-name "CustomOntology"

# Flatten component properties into parent entities
python src\main.py dtdl-upload path/to/dtdl/ --flatten-components --ontology-name "FlatOntology"

# Skip validation (not recommended)
python src\main.py dtdl-upload path/to/dtdl/ --skip-validation --ontology-name "RiskyOntology"
```

## DTDL to Fabric Mapping

The converter maps DTDL concepts to Microsoft Fabric Ontology equivalents:

| DTDL Concept | Fabric Ontology Equivalent | Notes |
|--------------|---------------------------|-------|
| Interface | EntityType | Direct mapping with display name and description |
| Property | Property (static) | Primitive and complex types supported |
| Telemetry | TimeseriesProperty | Mapped to time-series for sensor data |
| Relationship | RelationshipType | With target entity type constraints |
| Component | Nested properties | Flattened when `--flatten-components` used |
| Inheritance (extends) | BaseEntityTypeId | Single inheritance only (first parent) |
| Enum | String with allowed values | Enum values preserved as constraints |
| @id (DTMI) | Used to generate EntityTypeId | Hashed to stable numeric ID |
| displayName | DisplayName | Localized names preserved |
| description | Description | Documentation preserved |

### Type Mapping

DTDL schema types are mapped to Fabric property types as follows:

| DTDL Schema Type | Fabric Property Type | Notes |
|-----------------|---------------------|-------|
| boolean | Boolean | Direct mapping |
| date | Date | ISO 8601 date format |
| dateTime | DateTime | ISO 8601 datetime format |
| double | Double | 64-bit floating point |
| duration | Duration | ISO 8601 duration format |
| float | Float | 32-bit floating point |
| integer | Integer | 32-bit signed integer |
| long | Long | 64-bit signed integer |
| string | String | Unicode text |
| time | Time | ISO 8601 time format |
| **DTDL v4 Types:** | | |
| byte | Integer | 8-bit signed, mapped to Integer |
| short | Integer | 16-bit signed, mapped to Integer |
| decimal | Decimal | High-precision decimal |
| uuid | String | UUID as string |
| unsignedByte | Integer | Mapped to Integer (no unsigned in Fabric) |
| unsignedShort | Integer | Mapped to Integer |
| unsignedInteger | Long | Mapped to Long to preserve range |
| unsignedLong | Long | Mapped to Long (may overflow for large values) |
| bytes | String | Base64-encoded binary data as string |
| **Complex Types:** | | |
| Enum | String | Enum values stored as allowed string values |
| Object | String | Serialized to JSON string |
| Array | String | Serialized to JSON string |
| Map | String | Serialized to JSON string |
| **Geospatial (v4):** | | |
| point, lineString, polygon, etc. | String | Serialized to GeoJSON string |

## Supported DTDL Features

### Fully Supported

- ✅ **DTDL v2, v3, and v4** contexts
- ✅ **Properties** with primitive and complex types
- ✅ **Telemetry** (mapped to timeseries properties)
- ✅ **Relationships** with target constraints
- ✅ **Interface inheritance** (extends) - first parent only
- ✅ **Components** (with flatten option)
- ✅ **Semantic types** (@type annotations)
- ✅ **Display names and descriptions** (with localization)
- ✅ **Enum schemas** (as string constraints)
- ✅ **DTDL v4 new primitive types**: `byte`, `bytes`, `decimal`, `short`, `uuid`
- ✅ **DTDL v4 unsigned types**: `unsignedByte`, `unsignedShort`, `unsignedInteger`, `unsignedLong`
- ✅ **DTDL v4 geospatial schemas**: `point`, `lineString`, `polygon`, `multiPoint`, `multiLineString`, `multiPolygon`

### Limited Support

- ⚠️ **Multiple inheritance** - Only first parent in `extends` array is used
- ⚠️ **Complex schemas** (Object, Array, Map) - Serialized to JSON strings (no native structure)
- ⚠️ **Components** - Flattened to properties unless `--flatten-components` is used
- ⚠️ **Relationship properties** - Not preserved (Fabric Ontology relationships don't support properties)

### Not Supported

- ❌ **Commands** - Skipped by default (can be included with `--include-commands` flag, mapped to properties)
- ❌ **CommandPayload** - Not converted
- ❌ **@context extensions** - Custom contexts ignored
- ❌ **Semantic type inference** - Only basic type mapping, no semantic reasoning

## DTDL Validation Checks

The `dtdl-validate` command performs comprehensive checks:

### Schema Validation
- **DTMI format** - Validates Digital Twin Model Identifier syntax
- **JSON-LD context** - Checks for valid DTDL v2/v3/v4 context URLs
- **Schema types** - Verifies all schema types are valid DTDL types
- **Required fields** - Ensures @id, @type, and required properties are present

### Semantic Validation
- **Inheritance cycles** - Detects circular `extends` chains
- **Relationship targets** - Warns about relationships pointing to undefined interfaces
- **Component schemas** - Warns about components referencing missing schemas
- **DTMI uniqueness** - Checks for duplicate @id values

### Best Practices
- **Large ontology warnings** - Alerts when >200 interfaces may cause performance issues
- **Deep inheritance** - Warns about inheritance chains >5 levels (DTDL allows up to 12 in v4)
- **Complex schemas** - Warns about deeply nested Object/Array schemas

## Examples

### Example 1: Simple Thermostat

**Input DTDL** (samples/dtdl/thermostat.json):
```json
{
  "@context": "dtmi:dtdl:context;3",
  "@id": "dtmi:com:example:Thermostat;1",
  "@type": "Interface",
  "displayName": "Thermostat",
  "description": "A smart thermostat device",
  "contents": [
    {
      "@type": "Property",
      "name": "targetTemperature",
      "schema": "double",
      "writable": true
    },
    {
      "@type": "Telemetry",
      "name": "temperature",
      "schema": "double"
    }
  ]
}
```

**Conversion:**
```powershell
python src\main.py dtdl-upload samples/dtdl/thermostat.json --ontology-name "ThermostatOntology"
```

**Result:**
- EntityType: `Thermostat` with description
- Property: `targetTemperature` (Double, writable)
- TimeseriesProperty: `temperature` (Double)

### Example 2: Factory with Inheritance

**Input DTDL**:
```json
{
  "@context": "dtmi:dtdl:context;3",
  "@id": "dtmi:com:factory:Equipment;1",
  "@type": "Interface",
  "displayName": "Equipment",
  "contents": [
    {
      "@type": "Property",
      "name": "manufacturer",
      "schema": "string"
    }
  ]
}
```

```json
{
  "@context": "dtmi:dtdl:context;3",
  "@id": "dtmi:com:factory:Machine;1",
  "@type": "Interface",
  "displayName": "Machine",
  "extends": "dtmi:com:factory:Equipment;1",
  "contents": [
    {
      "@type": "Telemetry",
      "name": "rpm",
      "schema": "double"
    }
  ]
}
```

**Result:**
- EntityType: `Equipment` with property `manufacturer`
- EntityType: `Machine` extending `Equipment` with timeseries property `rpm`

### Example 3: RealEstateCore DTDL

The RealEstateCore DTDL ontology (~269 interfaces) has been successfully tested:

```powershell
# Import the full RealEstateCore DTDL ontology
python src\main.py dtdl-upload path/to/RealEstateCore/ --recursive --ontology-name "RealEstateCore"
```

This demonstrates the tool's capability to handle large, complex DTDL ontologies with:
- Extensive inheritance hierarchies
- Complex relationship networks
- Components and semantic types
- Hundreds of interfaces

## Limitations

> **📘 For comprehensive limitations, see [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md)**  
> This section provides a quick overview of the most important limitations.

### Key Information Loss

When converting DTDL to Fabric Ontology, **some information may be lost or transformed**:

| DTDL Feature | Impact |
|--------------|--------|
| **Commands** | Not converted by default (configurable) |
| **Complex schemas** (Object, Array, Map) | Serialized to JSON strings |
| **Multiple inheritance** | Only first parent in extends array used |
| **Relationship properties** | Not preserved in Fabric |
| **Components** | Configurable handling (skip/flatten/separate) |
| **Cardinality constraints** | minMultiplicity/maxMultiplicity not enforced |

**See [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md) for:**
- Complete feature support matrix (supported/partial/unsupported)
- Component, Command, and ScaledDecimal configuration modes
- DTDL version-specific limits (v2/v3/v4)
- Fabric API limits and compliance requirements
- Best practices for DTDL sources

### Validation & Compliance Reports

Use the compliance report feature to understand exactly what will be preserved, limited, or lost:

```python
from dtdl import DTDLToFabricConverter

converter = DTDLToFabricConverter()
result, report = converter.convert_with_compliance_report(interfaces)

if report:
    print(f"✅ Supported features: {len(report.supported_features)}")
    print(f"⚠️  Warnings: {len(report.warnings)}")
    print(f"❌ Limitations: {len(report.limitations)}")
    
    for warning in report.warnings:
        print(f"[{warning.impact.value}] {warning.feature}: {warning.message}")
```

### See Also

- **[Mapping Limitations](MAPPING_LIMITATIONS.md)** - Full list of RDF/DTDL → Fabric conversion constraints
- **[DTDL Specification](https://learn.microsoft.com/azure/digital-twins/concepts-models)** - Official DTDL documentation
- **[Fabric Ontology API](API.md)** - Microsoft Fabric Ontology REST API reference

## Related Resources

- [DTDL Language Specification](https://github.com/Azure/opendigitaltwins-dtdl)
- [RealEstateCore DTDL](https://github.com/Azure/opendigitaltwins-building) - Example large DTDL ontology
- [Microsoft Fabric Ontology REST API](https://learn.microsoft.com/rest/api/fabric/ontology/items)
