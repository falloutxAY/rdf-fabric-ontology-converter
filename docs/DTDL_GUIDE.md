# DTDL to Fabric Ontology Guide

This guide provides comprehensive information about importing **Digital Twins Definition Language (DTDL)** models from Azure IoT/Digital Twins into Microsoft Fabric Ontology.

## Table of Contents

- [What is DTDL?](#what-is-dtdl)
- [DTDL Commands](#dtdl-commands)
- [DTDL to Fabric Mapping](#dtdl-to-fabric-mapping)
- [What Gets Converted?](#what-gets-converted)
- [DTDL Validation Checks](#dtdl-validation-checks)
- [Examples](#examples)
- [Key Considerations](#key-considerations)

## What is DTDL?

[DTDL](https://learn.microsoft.com/azure/digital-twins/concepts-models) is a JSON-LD based modeling language used by Azure Digital Twins and Azure IoT. It defines:

- **Interfaces** - Digital twin types with properties, telemetry, relationships, and commands
- **Properties** - Static attributes of a twin
- **Telemetry** - Time-series sensor data  
- **Relationships** - Connections between twins
- **Components** - Reusable interface compositions

DTDL supports semantic modeling, inheritance, and type composition to create rich digital twin representations of physical environments, IoT devices, and business processes.

## DTDL Commands

> **📘 For complete command reference, see [COMMANDS.md](COMMANDS.md#dtdl-commands)**

This section shows the typical workflow for working with DTDL models.

### Quick Workflow

```powershell
# 1. Validate your DTDL models
python src\main.py dtdl-validate ./models/ --recursive --verbose

# 2. Convert to Fabric JSON (optional - for inspection)
python src\main.py dtdl-convert ./models/ --recursive --output fabric_output.json

# 3. Upload to Fabric
python src\main.py dtdl-upload ./models/ --recursive --ontology-name "MyDigitalTwin"
```

### Available Commands

| Command | Purpose |
|---------|----------|
| `dtdl-validate` | Validate DTDL schema and structure |
| `dtdl-convert` | Convert DTDL to Fabric JSON (no upload) |
| `dtdl-upload` | Full pipeline: validate → convert → upload |

### Common Options

- `--recursive` - Process directories recursively
- `--verbose` - Show detailed interface information
- `--output` - Specify output file path
- `--ontology-name` - Set the ontology name
- `--namespace` - Custom namespace (default: `usertypes`)
- `--flatten-components` - Flatten component properties into parent entities
- `--dry-run` - Convert without uploading

**See [COMMANDS.md](COMMANDS.md#dtdl-commands) for:**
- Complete command syntax and all options
- Component and command handling modes
- Advanced configuration examples
- Batch processing details

## DTDL to Fabric Mapping

> **📘 For complete mapping details and configuration options, see [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md#dtdl-supported-features)**

The converter maps DTDL concepts to Fabric Ontology:

- **Interface** → EntityType
- **Property** → EntityTypeProperty (primitive and complex types)
- **Telemetry** → TimeseriesProperty (for sensor data)
- **Relationship** → RelationshipType
- **Component** → Configurable (skip/flatten/separate)
- **Command** → Configurable (skip/property/entity)
- **Inheritance** (extends) → baseEntityTypeId (single parent only)

**Type Mapping:** DTDL primitive types (boolean, integer, double, string, date, etc.) map directly to Fabric types. Complex types (Object, Array, Map) are serialized to JSON strings. DTDL v4 types (byte, uuid, geospatial) are supported with appropriate conversions.

## What Gets Converted?

> **📘 For complete feature support matrix and configuration options, see [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md#dtdl-supported-features)**

### ✅ Fully Supported (DTDL v2/v3/v4)
- Interfaces, Properties, Telemetry, Relationships
- Single inheritance (extends)
- Primitive types and DTDL v4 types (byte, uuid, geospatial)
- Enums, display names, descriptions

### ⚠️ Configurable Features
- **Components:** skip / flatten / separate (see [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md#component-handling-modes))
- **Commands:** skip / property / entity (see [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md#command-handling-modes))
- **ScaledDecimal (v4):** json_string / structured / calculated (see [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md#scaleddecimal-handling-modes-dtdl-v4))

### ⚠️ Limited Support
- Multiple inheritance (first parent only)
- Complex schemas (Object, Array, Map → JSON strings)
- Relationship properties (not preserved)

### ❌ Not Supported
- Custom @context extensions
- Semantic type inference

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

## Key Considerations

> **📘 For comprehensive limitations, configuration modes, and best practices, see [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md)**

### Information Loss During Conversion

DTDL is designed for digital twins, while Fabric Ontology targets business data models. Some features don't translate directly:

- **Commands** are skipped by default (configurable via `command_mode`)
- **Complex schemas** (Object, Array, Map) become JSON strings
- **Multiple inheritance** simplified to first parent only
- **Relationship properties** are not preserved
- **Components** need configuration (`component_mode`)
- **Cardinality constraints** (minMultiplicity/maxMultiplicity) not enforced

### Configuration Options

Customize conversion behavior via config.json or command parameters:

```json
{
  "dtdl": {
    "component_mode": "flatten",
    "command_mode": "skip",
    "scaled_decimal_mode": "json_string"
  }
}
```

See [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md#component-handling-modes) for detailed mode descriptions.

### Before You Convert

1. **Validate first:** `python src\main.py dtdl-validate ./models/ --recursive`
2. **Choose configuration:** Decide how to handle Components, Commands, ScaledDecimals
3. **Review compliance report:** Understand what will be preserved vs. lost
4. **Test with samples:** Try conversion on a subset before full upload

### Compliance Reports

Generate detailed reports showing conversion impact:

```python
from dtdl import DTDLToFabricConverter

converter = DTDLToFabricConverter()
result, report = converter.convert_with_compliance_report(interfaces)

if report:
    print(f"⚠️  Warnings: {len(report.warnings)}")
    for warning in report.warnings:
        print(f"[{warning.impact.value}] {warning.feature}: {warning.message}")
```

### See Also

- **[MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md)** - Complete technical reference for conversion constraints and configuration
- **[DTDL Specification](https://learn.microsoft.com/azure/digital-twins/concepts-models)** - Official Azure documentation
- **[Fabric Ontology API](API.md)** - Microsoft Fabric API reference

## Related Resources

- [DTDL Language Specification](https://github.com/Azure/opendigitaltwins-dtdl)
- [RealEstateCore DTDL](https://github.com/Azure/opendigitaltwins-building) - Example large DTDL ontology
- [Microsoft Fabric Ontology REST API](https://learn.microsoft.com/rest/api/fabric/ontology/items)
