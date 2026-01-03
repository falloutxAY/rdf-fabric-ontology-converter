# Sample Plugins

This directory contains sample plugins demonstrating how to extend the Fabric Ontology Converter with custom format converters.

## Available Samples

### CSV Schema Converter (`csv_schema_converter.py`)

A complete example showing how to create a custom converter for CSV-based schema definitions.

**Features:**
- Converts CSV schema files to Fabric Ontology format
- Automatic type mapping from common database types
- Relationship inference from `_id` suffix columns
- Progress reporting and cancellation support
- Content-based file detection

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
from src.core.plugins import PluginRegistry
from samples.plugins.csv_schema_converter import CSVSchemaConverter

# Register the plugin
PluginRegistry.register_converter(CSVSchemaConverter())

# Convert a file
converter = PluginRegistry.get_converter("csvschema")
result = converter.convert("schema.csv")

print(f"Converted {len(result.entity_types)} entities")
```

## Creating Your Own Plugin

### 1. Implement the Interface

Create a class that extends `FormatConverter`:

```python
from src.core.plugins import FormatConverter, ConversionOutput, ConversionStatus

class MyFormatConverter(FormatConverter):
    # Required: format identifier
    format_name = "myformat"
    
    # Required: file extensions this converter handles
    file_extensions = [".myf", ".myformat"]
    
    # Optional: human-readable description
    format_description = "My Custom Format converter"
    version = "1.0.0"
    author = "Your Name"
    
    def convert(self, source, context=None, **options):
        output = ConversionOutput()
        
        try:
            # Check memory availability (if memory manager is configured)
            if context and not context.check_memory("my conversion"):
                output.status = ConversionStatus.FAILED
                output.errors.append("Insufficient memory")
                return output
            
            # Your conversion logic here
            for item in items:
                # Check for cancellation
                if context and context.is_cancelled():
                    output.status = ConversionStatus.PARTIAL
                    break
                
                # Report progress
                if context:
                    context.report_progress(idx, total, f"Processing {item}")
                
                # Process item...
            
            output.status = ConversionStatus.SUCCESS
        except Exception as e:
            output.status = ConversionStatus.FAILED
            output.errors.append(str(e))
        
        return output
```

### 2. Register the Plugin

**Option A: Programmatic Registration**
```python
from src.core.plugins import PluginRegistry

PluginRegistry.register_converter(MyFormatConverter())
```

**Option B: Entry Point Registration**

Add to `pyproject.toml`:
```toml
[project.entry-points."fabric_ontology.converters"]
myformat = "mypackage.converters:MyFormatConverter"
```

**Option C: Plugin Directory**

Place your plugin file in a plugins directory and configure:
```python
PluginRegistry.set_plugins_directory("/path/to/plugins")
PluginRegistry.discover_plugins()
```

### 3. Use the Plugin

```python
from src.core.plugins import PluginRegistry, ConversionContext

# Get converter by format name
converter = PluginRegistry.get_converter("myformat")

# Create context with core infrastructure enabled
context = ConversionContext.create_with_defaults(
    enable_rate_limiter=True,      # Token bucket rate limiting
    enable_circuit_breaker=True,   # Fault tolerance
    enable_cancellation=True,      # Graceful shutdown support
    enable_memory_manager=True,    # Memory monitoring
)

# Convert with full infrastructure support
result = converter.convert("data.myf", context=context)
```

## Core Infrastructure Integration

The plugin system integrates with the following core utilities:

| Feature | Context Method | Description |
|---------|----------------|-------------|
| Rate Limiting | `context.acquire_rate_limit()` | Token bucket rate limiting for API calls |
| Circuit Breaker | `context.call_with_circuit_breaker()` | Fault tolerance for external services |
| Cancellation | `context.is_cancelled()`, `context.throw_if_cancelled()` | Graceful shutdown support |
| Memory Management | `context.check_memory()` | Memory availability monitoring |
| Input Validation | `context.validate_input()` | Security checks for file paths |
| Progress Reporting | `context.report_progress()` | User feedback for long operations |

**Example using all features:**
```python
def convert(self, source, context=None, **options):
    output = ConversionOutput()
    
    # Memory check
    if context and not context.check_memory("conversion"):
        return ConversionOutput(status=ConversionStatus.FAILED)
    
    # Input validation
    if context:
        context.validate_input(str(source))
    
    for idx, item in enumerate(items):
        # Cancellation check
        if context:
            context.throw_if_cancelled()
            context.report_progress(idx, len(items), f"Processing")
        
        # Rate-limited API call with circuit breaker
        if context:
            context.acquire_rate_limit()
            result = context.call_with_circuit_breaker(api_call, item)
        
        # Process result...
    
    return output
```

## Plugin Types

The plugin system supports three types:

| Type | Base Class | Purpose |
|------|------------|---------|
| Converter | `FormatConverter` | Convert source format → Fabric Ontology |
| Validator | `FormatValidator` | Validate files before conversion |
| Exporter | `FormatExporter` | Export Fabric Ontology → target format |

## Best Practices

1. **Handle errors gracefully** - Use ConversionStatus.PARTIAL for recoverable errors
2. **Provide useful warnings** - Help users understand conversion limitations
3. **Support progress reporting** - Use the context callback for long operations
4. **Document your format** - Include format specification in docstrings
5. **Add content detection** - Override `can_convert()` for smarter detection
6. **Include examples** - Provide sample files in your plugin package

## Testing Your Plugin

```python
import pytest
from src.core.plugins import PluginRegistry
from my_plugin import MyFormatConverter

def test_conversion():
    converter = MyFormatConverter()
    result = converter.convert("test_data.myf")
    
    assert result.is_success
    assert len(result.entity_types) > 0

def test_registration():
    PluginRegistry.register_converter(MyFormatConverter())
    assert PluginRegistry.has_converter("myformat")
```

## See Also

- [docs/API.md](../../docs/API.md) - Plugin API reference
- [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - System architecture
