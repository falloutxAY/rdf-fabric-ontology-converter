# API Reference

Programmatic usage of the converter components.

## Quick Start

```python
# RDF Conversion
from src.rdf import RDFToFabricConverter

converter = RDFToFabricConverter()
result = converter.convert_file("ontology.ttl")

print(f"Entities: {len(result.entity_types)}")
print(f"Relationships: {len(result.relationship_types)}")

# DTDL Conversion
from src.dtdl import DTDLParser, DTDLToFabricConverter

parser = DTDLParser()
interfaces = parser.parse_file("models/")
converter = DTDLToFabricConverter()
result = converter.convert(interfaces)
```

## Data Models

### EntityType

```python
from src.shared.models import EntityType, EntityTypeProperty

entity = EntityType(
    id="1000000000001",
    name="Machine",
    namespace="usertypes",
    properties=[
        EntityTypeProperty(id="1000000001", name="serialNumber", valueType="String")
    ],
    timeseriesProperties=[
        EntityTypeProperty(id="1000000002", name="temperature", valueType="Double")
    ],
)
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `str` | Unique 13-digit numeric ID |
| `name` | `str` | Display name |
| `namespace` | `str` | Namespace (default: `usertypes`) |
| `baseEntityTypeId` | `Optional[str]` | Parent entity ID |
| `properties` | `List[EntityTypeProperty]` | Regular properties |
| `timeseriesProperties` | `List[EntityTypeProperty]` | Time-series properties |

### RelationshipType

```python
from src.shared.models import RelationshipType, RelationshipEnd

rel = RelationshipType(
    id="2000000000001",
    name="produces",
    source=RelationshipEnd(entityTypeId="1000000000001"),
    target=RelationshipEnd(entityTypeId="1000000000002"),
)
```

### ConversionResult

```python
result = converter.convert(content)

print(result.success_rate)       # Percentage
print(result.has_warnings)       # True/False
print(result.get_summary())      # Human-readable summary

for entity in result.entity_types:
    print(entity.name)

for skip in result.skipped_items:
    print(f"Skipped: {skip.name} - {skip.reason}")
```

## RDF Converter

```python
from src.rdf import RDFToFabricConverter, PreflightValidator

# Validate first
validator = PreflightValidator()
issues = validator.validate_file("ontology.ttl")

if issues.is_valid:
    # Convert
    converter = RDFToFabricConverter(id_prefix=1000000000000)
    result = converter.convert_file("ontology.ttl")
```

## DTDL Converter

```python
from src.dtdl import (
    DTDLParser,
    DTDLValidator, 
    DTDLToFabricConverter,
    ComponentMode,
    CommandMode,
)

# Parse
parser = DTDLParser()
interfaces = parser.parse_directory("models/")

# Validate
validator = DTDLValidator()
issues = validator.validate(interfaces)

# Convert with options
converter = DTDLToFabricConverter(
    component_mode=ComponentMode.FLATTEN,
    command_mode=CommandMode.PROPERTY,
)
result = converter.convert(interfaces)
```

## Fabric Client

```python
from src.core import FabricOntologyClient, FabricConfig

config = FabricConfig.from_file("config.json")
client = FabricOntologyClient(config)

# List ontologies
ontologies = client.list_ontologies()

# Create ontology
ontology = client.create_ontology(
    name="MyOntology",
    description="My ontology"
)

# Update definition
client.update_definition(
    ontology_id=ontology.id,
    entity_types=result.entity_types,
    relationship_types=result.relationship_types,
)

# Delete
client.delete_ontology(ontology_id)
```

## Streaming

For large files (>100MB):

```python
from src.core.streaming import StreamingEngine, StreamConfig

config = StreamConfig(
    chunk_size=10000,
    memory_threshold_mb=100,
)

engine = StreamingEngine(config=config)
result = engine.process_file(
    "large_ontology.ttl",
    progress_callback=lambda n: print(f"Processed: {n}")
)
```

### Streaming Pipeline Interface

For custom streaming implementations, use the formal pipeline interface:

```python
from src.core.services.pipeline import (
    StreamingPipeline,
    PipelineConfig,
    PipelineResult,
    StreamReaderProtocol,
    StreamProcessorProtocol,
    StreamAggregatorProtocol,
    create_pipeline_from_format,
)

# Quick start with format-specific pipeline
config = PipelineConfig(
    chunk_size=10000,
    memory_limit_mb=512,
    enable_progress=True,
)
pipeline = create_pipeline_from_format("rdf", config)

# Execute with progress callback
result = pipeline.execute(
    input_path="large_ontology.ttl",
    output_path="output.json",
    progress_callback=lambda stats: print(f"Items: {stats.items_produced}")
)

print(result.stats.get_summary())
```

### Pipeline Components

| Component | Protocol | Purpose |
|-----------|----------|---------|
| Reader | `StreamReaderProtocol` | Read file in chunks |
| Processor | `StreamProcessorProtocol` | Parse/convert chunks |
| Aggregator | `StreamAggregatorProtocol` | Combine results |

### Pipeline Configuration

```python
config = PipelineConfig(
    chunk_size=10000,         # Items per chunk
    memory_limit_mb=512,      # Memory ceiling
    buffer_size_bytes=65536,  # I/O buffer (64KB)
    enable_progress=True,     # Progress callbacks
    fail_fast=True,           # Stop on first error
)
```

### Pipeline Statistics

```python
result = pipeline.execute("input.ttl")

print(result.stats.chunks_processed)   # Chunks handled
print(result.stats.items_produced)     # Entities created
print(result.stats.bytes_read)         # Total bytes read
print(result.stats.duration_seconds)   # Execution time
print(result.stats.peak_memory_mb)     # Peak memory usage
```

## Validation

```python
from src.core.validators import InputValidator, FabricLimitsValidator

# File path validation
path = InputValidator.validate_file_path(
    "ontology.ttl",
    allowed_extensions=['.ttl', '.rdf'],
    check_exists=True,
)

# Fabric limits validation
limits = FabricLimitsValidator()
errors = limits.validate_all(entity_types, relationship_types)
```

## Type Mappings

### RDF/XSD → Fabric

| XSD Type | Fabric Type |
|----------|-------------|
| `xsd:string` | String |
| `xsd:boolean` | Boolean |
| `xsd:integer`, `xsd:long` | BigInt |
| `xsd:double`, `xsd:float` | Double |
| `xsd:decimal` | Decimal |
| `xsd:dateTime`, `xsd:date` | DateTime |

### DTDL → Fabric

| DTDL Type | Fabric Type |
|-----------|-------------|
| `boolean` | Boolean |
| `integer`, `long` | BigInt |
| `double`, `float` | Double |
| `string` | String |
| `dateTime`, `date` | DateTime |
| Complex types | JSON String |

## See Also

- [Architecture](ARCHITECTURE.md) - System design
- [RDF Guide](RDF_GUIDE.md) - RDF conversion details
- [DTDL Guide](DTDL_GUIDE.md) - DTDL conversion details
- [Unofficial Fabric Ontology SDK](https://github.com/falloutxAY/Unofficial-Fabric-Ontology-SDK) - SDK documentation (v0.4.0+)

## SDK Integration

The converter exports key SDK constants through `sdk_adapter.py` for validation consistency:

```python
from src.core.platform.sdk_adapter import (
    NAME_PATTERN,       # Regex for valid entity/property names
    PropertyDataType,   # Valid data types enum
)

import re

# Validate names
if re.match(NAME_PATTERN, name):
    print("Valid name")

# Check data types
from src.core.platform.sdk_adapter import PropertyDataType
valid_types = [t.value for t in PropertyDataType]
```

**Available PropertyDataType values:** `BIGINT`, `STRING`, `DOUBLE`, `FLOAT`, `BOOLEAN`, `DATETIME`, `OBJECT`
