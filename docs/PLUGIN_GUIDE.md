# Plugin Development Guide

This guide explains how to extend the Fabric Ontology Converter with custom format converters, validators, and exporters using the plugin architecture.

## Overview

The plugin system allows you to add support for new file formats without modifying the core codebase. Plugins integrate seamlessly with the converter's infrastructure, including rate limiting, circuit breakers, cancellation support, and memory management.

## Plugin Types

The plugin system supports three types:

| Type | Base Class | Purpose |
|------|------------|---------|
| Converter | `FormatConverter` | Convert source format → Fabric Ontology |
| Validator | `FormatValidator` | Validate files before conversion |
| Exporter | `FormatExporter` | Export Fabric Ontology → target format |

## Creating a Converter Plugin

### 1. Implement the Interface

Create a class that extends `FormatConverter`:

```python
from src.core.plugins import FormatConverter, ConversionOutput, ConversionStatus
from src.models.ontology import EntityType, PropertyDefinition, RelationshipType

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
        """
        Convert source file to Fabric Ontology format.
        
        Args:
            source: File path or file-like object
            context: Optional ConversionContext for infrastructure integration
            **options: Additional conversion options
        
        Returns:
            ConversionOutput with entity_types and relationship_types
        """
        output = ConversionOutput()
        
        try:
            # Parse source file
            data = self._parse_file(source)
            
            # Convert to entity types
            for item in data:
                entity = EntityType(
                    name=item['name'],
                    display_name=item.get('display_name'),
                    description=item.get('description'),
                    properties=self._convert_properties(item['properties'])
                )
                output.entity_types.append(entity)
            
            output.status = ConversionStatus.SUCCESS
        except Exception as e:
            output.status = ConversionStatus.FAILED
            output.errors.append(str(e))
        
        return output
    
    def can_convert(self, source) -> bool:
        """
        Optional: Check if this converter can handle the source.
        
        Override for content-based detection beyond file extension.
        """
        # Default implementation checks file extension
        return super().can_convert(source)
```

### 2. Core Infrastructure Integration

The `ConversionContext` provides access to core utilities:

```python
def convert(self, source, context=None, **options):
    output = ConversionOutput()
    
    # Memory check - estimate file size needed
    if context:
        file_size_mb = os.path.getsize(source) / (1024 * 1024)
        if not context.check_memory(file_size_mb):
            output.status = ConversionStatus.FAILED
            output.errors.append("Insufficient memory")
            return output
    
    # Input validation - security checks
    if context:
        try:
            context.validate_input(str(source), check_exists=False)
        except Exception as e:
            output.status = ConversionStatus.FAILED
            output.errors.append(f"Invalid input: {e}")
            return output
    
    items = self._parse_file(source)
    total = len(items)
    
    for idx, item in enumerate(items):
        # Cancellation support
        if context and context.is_cancelled():
            output.status = ConversionStatus.PARTIAL
            output.warnings.append(f"Cancelled after {idx}/{total} items")
            break
        
        # Progress reporting
        if context:
            context.report_progress(idx + 1, total, f"Processing {item.name}")
        
        # Rate-limited API calls (if needed)
        if context:
            context.acquire_rate_limit()
        
        # Circuit breaker for external services
        if context and some_external_service:
            result = context.call_with_circuit_breaker(
                external_api.call, 
                item
            )
        
        # Process item
        output.entity_types.append(self._convert_item(item))
    
    output.status = ConversionStatus.SUCCESS
    return output
```

### Core Infrastructure Features

| Feature | Context Method | Description |
|---------|----------------|-------------|
| Rate Limiting | `context.acquire_rate_limit(tokens=1)` | Token bucket rate limiting for API calls |
| Circuit Breaker | `context.call_with_circuit_breaker(func, *args)` | Fault tolerance for external services |
| Cancellation | `context.is_cancelled()`, `context.throw_if_cancelled()` | Graceful shutdown support |
| Memory Management | `context.check_memory(file_size_mb)` | Memory availability monitoring |
| Input Validation | `context.validate_input(path, check_exists=False)` | Security checks for file paths |
| Progress Reporting | `context.report_progress(current, total, message)` | User feedback for long operations |

## Registering Plugins

### Option A: Programmatic Registration

```python
from src.core.plugins import PluginRegistry
from my_plugin import MyFormatConverter

# Register the converter
PluginRegistry.register_converter(MyFormatConverter())

# Verify registration
assert PluginRegistry.has_converter("myformat")
```

### Option B: Entry Point Registration

Add to your package's `pyproject.toml`:

```toml
[project.entry-points."fabric_ontology.converters"]
myformat = "mypackage.converters:MyFormatConverter"

[project.entry-points."fabric_ontology.validators"]
myvalidator = "mypackage.validators:MyFormatValidator"

[project.entry-points."fabric_ontology.exporters"]
myexporter = "mypackage.exporters:MyFormatExporter"
```

Then install your package and the plugin will be auto-discovered:

```bash
pip install -e .
```

### Option C: Plugin Directory

Place your plugin file in a plugins directory:

```python
from src.core.plugins import PluginRegistry

# Set plugins directory
PluginRegistry.set_plugins_directory("/path/to/plugins")

# Discover all plugins in directory
PluginRegistry.discover_plugins()
```

## Using Plugins

### Basic Usage

```python
from src.core.plugins import PluginRegistry

# Get converter by format name
converter = PluginRegistry.get_converter("myformat")

# Or auto-detect from file extension
converter = PluginRegistry.get_converter_for_file("data.myf")

# Convert
result = converter.convert("data.myf")

if result.is_success:
    print(f"Converted {len(result.entity_types)} entities")
else:
    print(f"Errors: {result.errors}")
```

### With Core Infrastructure

```python
from src.core.plugins import PluginRegistry, ConversionContext

# Create context with all features enabled
context = ConversionContext.create_with_defaults(
    enable_rate_limiter=True,      # Token bucket rate limiting
    enable_circuit_breaker=True,   # Fault tolerance
    enable_cancellation=True,      # Graceful shutdown support
    enable_memory_manager=True,    # Memory monitoring
)

# Configure options
context.config.update({
    'rate_limit': {'rate': 100, 'per': 60},
    'circuit_breaker': {'failure_threshold': 5, 'recovery_timeout': 60}
})

# Convert with infrastructure support
converter = PluginRegistry.get_converter("myformat")
result = converter.convert("data.myf", context=context)
```

### Custom Progress Callback

```python
def progress_handler(current, total, message):
    percent = (current / total) * 100
    print(f"Progress: {percent:.1f}% - {message}")

context = ConversionContext(progress_callback=progress_handler)
result = converter.convert("data.myf", context=context)
```

### Cancellation Support

```python
from src.core.cancellation import CancellationToken

token = CancellationToken()
context = ConversionContext(cancellation_token=token)

# Start conversion in background
import threading
def convert_async():
    result = converter.convert("large_file.myf", context=context)

thread = threading.Thread(target=convert_async)
thread.start()

# User cancels operation
token.cancel("User requested cancellation")
thread.join()
```

## Plugin Discovery

The `PluginRegistry` discovers plugins through multiple mechanisms:

### 1. Entry Points (Recommended)

Plugins installed via pip are auto-discovered:

```python
# Automatically finds all plugins with fabric_ontology.* entry points
PluginRegistry.discover_entry_points()
```

### 2. Directory Scanning

```python
# Scan a directory for plugin modules
PluginRegistry.discover_from_directory("/path/to/plugins")
```

### 3. Programmatic Registration

```python
# Manually register a plugin instance
PluginRegistry.register_converter(MyConverter())
```

## Validator Plugins

Validators check file validity before conversion:

```python
from src.core.plugins import FormatValidator, ValidationOutput, ValidationStatus

class MyFormatValidator(FormatValidator):
    format_name = "myformat"
    file_extensions = [".myf"]
    
    def validate(self, source, context=None, **options):
        output = ValidationOutput()
        
        try:
            # Check file structure
            with open(source, 'r') as f:
                data = json.load(f)
            
            # Validate required fields
            if 'entities' not in data:
                output.errors.append("Missing 'entities' field")
                output.status = ValidationStatus.INVALID
                return output
            
            # Validate each entity
            for entity in data['entities']:
                if 'name' not in entity:
                    output.errors.append(f"Entity missing 'name' field")
                    output.status = ValidationStatus.INVALID
            
            if not output.errors:
                output.status = ValidationStatus.VALID
        except Exception as e:
            output.status = ValidationStatus.ERROR
            output.errors.append(str(e))
        
        return output
```

## Exporter Plugins

Exporters convert Fabric Ontology to other formats:

```python
from src.core.plugins import FormatExporter, ExportOutput, ExportStatus

class MyFormatExporter(FormatExporter):
    format_name = "myformat"
    file_extensions = [".myf"]
    
    def export(self, entity_types, relationship_types, destination, context=None, **options):
        output = ExportOutput()
        
        try:
            data = {
                'entities': [self._export_entity(e) for e in entity_types],
                'relationships': [self._export_relationship(r) for r in relationship_types]
            }
            
            with open(destination, 'w') as f:
                json.dump(data, f, indent=2)
            
            output.status = ExportStatus.SUCCESS
            output.destination = destination
        except Exception as e:
            output.status = ExportStatus.FAILED
            output.errors.append(str(e))
        
        return output
```

## Best Practices

### 1. Error Handling

Use appropriate status codes and provide helpful error messages:

```python
try:
    # Conversion logic
    output.status = ConversionStatus.SUCCESS
except FileNotFoundError as e:
    output.status = ConversionStatus.FAILED
    output.errors.append(f"File not found: {e}")
except ValueError as e:
    output.status = ConversionStatus.PARTIAL
    output.warnings.append(f"Invalid value, using default: {e}")
```

### 2. Progress Reporting

Report progress for long operations:

```python
total = len(items)
for idx, item in enumerate(items):
    if context:
        context.report_progress(idx + 1, total, f"Processing {item.name}")
    # Process item
```

### 3. Memory Management

Check memory before loading large files:

```python
if context:
    file_size_mb = os.path.getsize(source) / (1024 * 1024)
    if not context.check_memory(file_size_mb):
        output.status = ConversionStatus.FAILED
        output.errors.append("Insufficient memory for this file")
        return output
```

### 4. Cancellation Support

Check for cancellation in loops:

```python
for item in items:
    if context and context.is_cancelled():
        output.status = ConversionStatus.PARTIAL
        output.warnings.append("Conversion cancelled by user")
        break
    # Process item
```

### 5. Documentation

Provide comprehensive documentation:

```python
class MyFormatConverter(FormatConverter):
    """
    Convert MyFormat schema files to Fabric Ontology.
    
    MyFormat is a JSON-based schema format used for...
    
    Supported Features:
    - Entity definitions with properties
    - Relationship inference from foreign keys
    - Type mapping from MyFormat types to Fabric types
    
    Limitations:
    - Does not support nested entities
    - Maximum file size: 100MB
    
    Example:
        >>> converter = MyFormatConverter()
        >>> result = converter.convert("schema.myf")
        >>> print(len(result.entity_types))
        5
    """
```

### 6. Content Detection

Override `can_convert()` for smarter detection:

```python
def can_convert(self, source) -> bool:
    """Check if this is a valid MyFormat file."""
    # Check extension first
    if not super().can_convert(source):
        return False
    
    # Check file content
    try:
        with open(source, 'r') as f:
            data = json.load(f)
            return 'schema_version' in data and data['schema_version'] == '2.0'
    except:
        return False
```

## Testing Plugins

### Basic Tests

```python
import pytest
from src.core.plugins import PluginRegistry
from my_plugin import MyFormatConverter

def test_conversion():
    converter = MyFormatConverter()
    result = converter.convert("test_data.myf")
    
    assert result.is_success
    assert len(result.entity_types) > 0

def test_error_handling():
    converter = MyFormatConverter()
    result = converter.convert("invalid.myf")
    
    assert not result.is_success
    assert len(result.errors) > 0

def test_registration():
    PluginRegistry.register_converter(MyFormatConverter())
    assert PluginRegistry.has_converter("myformat")
    
    converter = PluginRegistry.get_converter("myformat")
    assert isinstance(converter, MyFormatConverter)
```

### Integration Tests

```python
def test_with_infrastructure():
    from src.core.plugins import ConversionContext
    
    context = ConversionContext.create_with_defaults(
        enable_rate_limiter=True,
        enable_cancellation=True,
    )
    
    converter = MyFormatConverter()
    result = converter.convert("test_data.myf", context=context)
    
    assert result.is_success

def test_cancellation():
    from src.core.cancellation import CancellationToken
    
    token = CancellationToken()
    context = ConversionContext(cancellation_token=token)
    
    # Cancel immediately
    token.cancel()
    
    converter = MyFormatConverter()
    result = converter.convert("large_file.myf", context=context)
    
    assert result.status == ConversionStatus.PARTIAL
```

## Example: CSV Schema Converter

See [samples/plugins/csv_schema_converter.py](../samples/plugins/csv_schema_converter.py) for a complete example showing:

- CSV parsing with proper error handling
- Type mapping from database types to Fabric types
- Relationship inference from column naming conventions
- Progress reporting and cancellation support
- Content-based file detection
- Comprehensive documentation

## See Also

- [API.md](API.md) - Complete API reference
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [CONFIGURATION.md](CONFIGURATION.md) - Configuration options
- [samples/plugins/README.md](../samples/plugins/README.md) - Sample plugins
