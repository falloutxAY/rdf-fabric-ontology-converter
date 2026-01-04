# DTDL to Fabric Ontology Guide

Convert Digital Twins Definition Language (DTDL) models to Microsoft Fabric Ontology format.

## Supported Versions

- DTDL v2
- DTDL v3
- DTDL v4

## Quick Start

```powershell
# Validate
python -m src.main validate --format dtdl models/ --recursive --verbose

# Convert only
python -m src.main convert --format dtdl models/ --output fabric.json

# Upload to Fabric
python -m src.main upload --format dtdl models/ --ontology-name MyDigitalTwin
```

## Mapping Reference

### ✅ Fully Supported

| DTDL Feature | Fabric Mapping |
|--------------|----------------|
| Interface | EntityType |
| Property | EntityTypeProperty |
| Telemetry | timeseriesProperties |
| Relationship | RelationshipType |
| extends (single) | baseEntityTypeId |
| displayName | name |
| description | description |

### Type Mapping

| DTDL Type | Fabric Type |
|-----------|-------------|
| `boolean` | Boolean |
| `integer`, `long` | BigInt |
| `double`, `float` | Double |
| `string` | String |
| `dateTime`, `date`, `time`, `duration` | DateTime |
| `byte` (v4) | BigInt |
| `uuid` (v4) | String |
| Complex types (Object, Array, Map) | JSON String |
| Geospatial types | JSON String |

### ⚠️ Configurable Features

#### Component Handling (`component_mode`)

| Mode | Behavior |
|------|----------|
| `skip` (default) | Components ignored |
| `flatten` | Properties merged with `{component}_` prefix |
| `separate` | Creates EntityType + `has_{component}` relationship |

#### Command Handling (`command_mode`)

| Mode | Behavior |
|------|----------|
| `skip` (default) | Commands ignored |
| `property` | Creates `command_{name}` property |
| `entity` | Creates `Command_{name}` EntityType |

#### ScaledDecimal Handling (`scaled_decimal_mode`)

| Mode | Behavior |
|------|----------|
| `json_string` (default) | `{"scale": n, "value": "x"}` |
| `structured` | `{prop}_scale` + `{prop}_value` properties |
| `calculated` | Computed Double value |

### ❌ Not Supported

- Multiple inheritance (first parent only)
- Relationship properties
- `writable`, `unit`, `semanticType` metadata
- Cardinality constraints
- Request/response schemas (in skip/property modes)

## Example

**Input DTDL:**
```json
{
  "@context": "dtmi:dtdl:context;3",
  "@id": "dtmi:com:example:Thermostat;1",
  "@type": "Interface",
  "displayName": "Thermostat",
  "contents": [
    {
      "@type": "Property",
      "name": "targetTemperature",
      "schema": "double"
    },
    {
      "@type": "Telemetry",
      "name": "temperature",
      "schema": "double"
    }
  ]
}
```

**Result:**
- EntityType: `Thermostat`
- Property: `targetTemperature` (Double)
- TimeseriesProperty: `temperature` (Double)

## Configuration

In `config.json`:

```json
{
  "dtdl": {
    "component_mode": "flatten",
    "command_mode": "property",
    "scaled_decimal_mode": "json_string"
  }
}
```

Or via CLI:
```powershell
python -m src.main convert --format dtdl models/ --component-mode flatten
```

## Validation Checks

The validator checks:
- DTMI format validity
- JSON-LD context (v2/v3/v4)
- Required fields (`@id`, `@type`)
- Inheritance cycles
- Relationship target existence
- Version-specific limits

### Version Limits

| Limit | v2 | v3 | v4 |
|-------|----|----|----| 
| Contents per interface | 300 | 100,000 | 100,000 |
| Extends depth | 10 | 10 | 12 |
| Schema depth | 5 | 5 | 8 |
| Name length | 64 | 512 | 512 |

## Key Considerations

### Information Loss

- Complex schemas (Object, Array, Map) become JSON strings
- Enum values stored in description only
- Property metadata (writable, unit) not preserved
- DTMI hashed to numeric ID (mapping saved with `--save-mapping`)

### Best Practices

1. **Validate first:** Run `validate` before upload
2. **Simple schemas:** Complex types become JSON strings
3. **Single inheritance:** Only first parent is used
4. **Save mappings:** Use `--save-mapping` to preserve DTMI→ID mapping

## See Also

- [CLI Commands](CLI_COMMANDS.md) - Command reference
- [RDF Guide](RDF_GUIDE.md) - RDF conversion
- [Configuration](CONFIGURATION.md) - DTDL settings
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
