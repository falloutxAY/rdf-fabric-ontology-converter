# Plugin Development Guide

Create custom plugins to support new ontology formats.

> **Note:** The plugin system is designed for **internal extensibility** only and is not exposed via CLI commands. Plugin CLI commands (`plugin list`, `plugin info`) are planned for a future release. Currently, plugins are used internally to provide a unified interface for different format handlers.

## Built-in Plugins

| Plugin | Format | Extensions |
|--------|--------|------------|
| RDF | `rdf` | `.ttl`, `.rdf`, `.owl`, `.nt`, `.nq`, `.trig`, `.n3`, `.jsonld` |
| DTDL | `dtdl` | `.json`, `.dtdl` |
| CDM | `cdm` | `.cdm.json`, `.manifest.cdm.json`, `model.json` |

## Plugin Architecture

```
┌────────────────────────────────────────────────────┐
│                  Plugin Manager                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │ RDF Plugin │  │ DTDL Plugin │  │ CDM Plugin  │  │
│  │  Parser    │  │  Parser     │  │  Parser     │  │
│  │  Validator │  │  Validator  │  │  Validator  │  │
│  │  Converter │  │  Converter  │  │  Converter  │  │
│  └────────────┘  └────────────┘  └────────────┘  │
└────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────┐
│                  Shared Models                     │
│  EntityType  │  RelationshipType                   │
│  ConversionResult                                  │
└────────────────────────────────────────────────────┘
```

## Creating a Plugin

### 1. Create Plugin Class

```python
# src/plugins/builtin/myformat_plugin.py
from src.plugins.base import OntologyPlugin
from typing import Set, Dict, List

class MyFormatPlugin(OntologyPlugin):
    
    @property
    def format_name(self) -> str:
        return "myformat"
    
    @property
    def display_name(self) -> str:
        return "My Format"
    
    @property
    def file_extensions(self) -> Set[str]:
        return {".myf", ".myformat"}
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def create_parser(self):
        return MyFormatParser()
    
    def create_validator(self):
        return MyFormatValidator()
    
    def create_converter(self):
        return MyFormatConverter()
    
    def get_type_mappings(self) -> Dict[str, str]:
        return {"mytype": "String"}
```

### 2. Implement Parser

```python
class MyFormatParser:
    def parse(self, content: str, file_path: str = None) -> dict:
        """Parse content and return structured data."""
        # Your parsing logic
        return parsed_data
    
    def parse_file(self, file_path: str) -> dict:
        with open(file_path, 'r') as f:
            return self.parse(f.read(), file_path)
```

### 3. Implement Validator

```python
from src.shared.utilities.validation import ValidationResult

class MyFormatValidator:
    def validate(self, content: str, file_path: str = None) -> ValidationResult:
        result = ValidationResult(format_name="myformat", source_path=file_path)
        
        # Validate syntax
        try:
            data = MyFormatParser().parse(content)
        except Exception as e:
            result.add_error("SYNTAX_ERROR", str(e))
            return result
        
        # Add more checks...
        return result
```

### 4. Implement Converter

```python
from src.shared.models import ConversionResult, EntityType

class MyFormatConverter:
    def __init__(self):
        self._id_counter = 1000000000000
    
    def convert(self, content: str, **kwargs) -> ConversionResult:
        entity_types = []
        relationship_types = []
        
        data = MyFormatParser().parse(content)
        
        # Convert to Fabric types
        for item in data.get("types", []):
            entity = EntityType(
                id=str(self._id_counter),
                name=item["name"],
                namespace="usertypes",
            )
            entity_types.append(entity)
            self._id_counter += 1
        
        return ConversionResult(
            entity_types=entity_types,
            relationship_types=relationship_types,
        )
```

### 5. Register Plugin

Add to `src/plugins/builtin/__init__.py`:

```python
from .myformat_plugin import MyFormatPlugin

__all__ = ["RDFPlugin", "DTDLPlugin", "CDMPlugin", "MyFormatPlugin"]
```

## Using Plugins

Plugins are automatically discovered and used by the CLI when you specify a format:

```bash
# Built-in formats work automatically
python -m src.main validate --format rdf ontology.ttl
python -m src.main validate --format dtdl models/
python -m src.main validate --format cdm model.manifest.cdm.json
```

> **Note:** Custom format plugins currently require code changes to add the format to the `--format` CLI choices. Plugin CLI commands for listing and managing plugins are planned for future implementation.

## Type Mappings

Map source types to Fabric types:

```python
def get_type_mappings(self) -> Dict[str, str]:
    return {
        "string": "String",
        "number": "Double",
        "integer": "BigInt",
        "boolean": "Boolean",
        "datetime": "DateTime",
    }
```

Fabric types: `String`, `Boolean`, `BigInt`, `Double`, `Decimal`, `DateTime`

## Best Practices

1. **Validate first:** Check syntax before conversion
2. **Generate unique IDs:** Use incrementing counter
3. **Handle errors:** Return skipped items with reasons
4. **Add warnings:** Surface potential issues to users
5. **Write tests:** Cover parser, validator, and converter

## Streaming Support

For large file support, implement the streaming protocols:

```python
from src.plugins.protocols import StreamingParserProtocol, StreamingConverterProtocol
from src.core.services.pipeline import StreamReaderProtocol, StreamProcessorProtocol
from typing import Iterator, Tuple, Dict, Any

class MyFormatStreamReader(StreamReaderProtocol[str]):
    """Read large files in chunks."""
    
    def read_chunks(self, file_path, config) -> Iterator[Tuple[str, int]]:
        with open(file_path, 'r') as f:
            buffer = []
            bytes_read = 0
            for line in f:
                buffer.append(line)
                bytes_read += len(line.encode())
                if len(buffer) >= config.chunk_size:
                    yield ''.join(buffer), bytes_read
                    buffer = []
                    bytes_read = 0
            if buffer:
                yield ''.join(buffer), bytes_read
    
    def get_file_size(self, file_path) -> int:
        return Path(file_path).stat().st_size
    
    def supports_format(self, file_path) -> bool:
        return Path(file_path).suffix in {'.myf', '.myformat'}

class MyFormatStreamProcessor(StreamProcessorProtocol[str, list]):
    """Process chunks incrementally."""
    
    def process_chunk(self, chunk: str, chunk_index: int, state: Dict[str, Any]):
        items = self._parse_chunk(chunk)
        entities = self._convert_items(items, state)
        return entities, len(entities)
    
    def initialize_state(self, config):
        return {"id_counter": 1000000000000, "seen_names": set()}
    
    def get_format_name(self) -> str:
        return "MyFormat"
```

Register streaming support in your plugin:

```python
class MyFormatPlugin(OntologyPlugin):
    @property
    def supports_streaming(self) -> bool:
        return True
    
    def create_stream_reader(self):
        return MyFormatStreamReader()
    
    def create_stream_processor(self):
        return MyFormatStreamProcessor()
```

## Example: CSV Plugin

```python
import csv
from io import StringIO

class CSVPlugin(OntologyPlugin):
    @property
    def format_name(self) -> str:
        return "csv"
    
    @property
    def file_extensions(self) -> Set[str]:
        return {".csv"}
    
    def create_converter(self):
        return CSVConverter()

class CSVConverter:
    def convert(self, content: str, **kwargs) -> ConversionResult:
        reader = csv.DictReader(StringIO(content))
        entity_types = []
        
        # First row defines entity type, columns are properties
        entity = EntityType(
            id="1000000000001",
            name=kwargs.get("entity_name", "CSVEntity"),
            namespace="usertypes",
            properties=[
                EntityTypeProperty(id=str(1000000001 + i), name=col, valueType="String")
                for i, col in enumerate(reader.fieldnames)
            ]
        )
        entity_types.append(entity)
        
        return ConversionResult(entity_types=entity_types)
```

## See Also

- [Architecture](ARCHITECTURE.md) - System design
- [API Reference](API.md) - Data models
