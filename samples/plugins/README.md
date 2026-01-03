# Sample Plugins

This directory contains sample plugins demonstrating how to extend the Fabric Ontology Converter with custom format converters.

For complete documentation on creating plugins, see [Plugin Development Guide](../../docs/PLUGIN_GUIDE.md).

## Available Samples

### CSV Schema Converter (`csv_schema_converter.py`)

A complete example showing how to create a custom converter for CSV-based schema definitions.

**Features:**
- Converts CSV schema files to Fabric Ontology format
- Automatic type mapping from common database types
- Relationship inference from `_id` suffix columns
- Progress reporting and cancellation support
- Content-based file detection
- Full integration with core infrastructure (rate limiting, circuit breaker, memory management)

**CSV Format:**
```csv
entity_name,property_name,property_type,is_id,description
Machine,serial_number,String,true,Unique serial number
Machine,manufacturer,String,false,Manufacturer name
Sensor,sensor_id,String,true,Unique sensor ID
Sensor,machine_id,String,false,Associated machine ID
```

**Usage:**
```python
from src.core.plugins import PluginRegistry, ConversionContext
from samples.plugins.csv_schema_converter import CSVSchemaConverter

# Register the plugin
PluginRegistry.register_converter(CSVSchemaConverter())

# Convert a file with core infrastructure support
context = ConversionContext.create_with_defaults(
    enable_rate_limiter=True,
    enable_cancellation=True,
    enable_memory_manager=True,
)

converter = PluginRegistry.get_converter("csvschema")
result = converter.convert("schema.csv", context=context)

if result.is_success:
    print(f"Converted {len(result.entity_types)} entities")
    print(f"Created {len(result.relationship_types)} relationships")
else:
    print(f"Errors: {result.errors}")
```

**Type Mapping:**

The converter maps common database types to Fabric types:

| CSV Type | Fabric Type |
|----------|-------------|
| String, VARCHAR, TEXT | String |
| Integer, INT, BIGINT | Int32/Int64 |
| Float, Double, Decimal | Double/Decimal |
| Boolean | Boolean |
| DateTime, Timestamp | DateTime |
| JSON, JSONB | String (JSON-encoded) |

**Relationship Inference:**

Properties ending with `_id` are treated as foreign keys:
- `machine_id` → Creates relationship to `Machine` entity
- `sensor_id` → Creates relationship to `Sensor` entity

## Quick Start

1. **Study the example:** Review `csv_schema_converter.py` to understand the plugin structure
2. **Read the guide:** See [PLUGIN_GUIDE.md](../../docs/PLUGIN_GUIDE.md) for comprehensive documentation
3. **Create your plugin:** Implement `FormatConverter` interface for your format
4. **Test it:** Write tests following the examples in `tests/test_plugins.py`
5. **Register it:** Use one of the three registration methods (programmatic, entry point, or directory)

## See Also

- [Plugin Development Guide](../../docs/PLUGIN_GUIDE.md) - Complete plugin development documentation
- [API Reference](../../docs/API.md) - Plugin API reference
- [Architecture Overview](../../docs/ARCHITECTURE.md) - System architecture
- [Testing Guide](../../docs/TESTING.md) - How to test your plugins
