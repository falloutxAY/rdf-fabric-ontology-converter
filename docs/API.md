# API Reference

This document provides detailed API documentation for the RDF/DTDL to Microsoft Fabric Ontology converter.

## Table of Contents

- [Package Structure](#package-structure)
- [Core Infrastructure](#core-infrastructure)
  - [Data Models](#data-models)
  - [Validators](#validators)
  - [Streaming Engine](#streaming-engine)
- [RDF/OWL Conversion](#rdfowl-conversion)
  - [RDF Converter](#rdf-converter)
  - [RDF Components](#rdf-components)
- [DTDL Conversion](#dtdl-conversion)
  - [DTDL Parser](#dtdl-parser)
  - [DTDL Validator](#dtdl-validator)
  - [DTDL to Fabric Converter](#dtdl-to-fabric-converter)
- [Fabric Client](#fabric-client)
- [CLI Commands](#cli-commands)
- [Error Handling](#error-handling)
- [Type Mappings](#type-mappings)

---

## Package Structure

The converter is organized into format-specific packages:

```python
# Format-based imports (recommended)
from rdf import RDFToFabricConverter, PreflightValidator, parse_ttl_content
from dtdl import DTDLParser, DTDLValidator
from core import FabricConfig, FabricOntologyClient, CircuitBreaker

# Package imports
from src.rdf import RDFToFabricConverter
from src.dtdl import DTDLParser
from src.core import FabricConfig
```

### Package Overview

| Package | Description |
|---------|-------------|
| `src.rdf` | RDF/OWL/TTL format support (converter, validator, exporter) |
| `src.dtdl` | DTDL v2/v3/v4 format support (parser, validator, converter) |
| `src.core` | Shared infrastructure (Fabric client, rate limiter, circuit breaker, cancellation) |
| `src.models` | Shared data models (EntityType, RelationshipType, ConversionResult) |

---

## Core Infrastructure

Shared components used by both RDF and DTDL converters.

### Data Models

#### `src.models` — Shared Data Models

#### `EntityType`

Represents an entity type in Fabric Ontology.

```python
from src.models import EntityType, EntityTypeProperty

entity = EntityType(
    id="1000000000001",
    name="Machine",
    namespace="usertypes",
    namespaceType="Custom",
    visibility="Visible",
    baseEntityTypeId=None,
    properties=[
        EntityTypeProperty(id="1000000001", name="serialNumber", valueType="String")
    ],
    timeseriesProperties=[
        EntityTypeProperty(id="1000000002", name="temperature", valueType="Double")
    ],
)
```

**Attributes:**

| Name | Type | Description |
|------|------|-------------|
| `id` | `str` | Unique numeric identifier (13 digits) |
| `name` | `str` | Display name |
| `namespace` | `str` | Ontology namespace (default: `"usertypes"`) |
| `namespaceType` | `str` | Namespace type (default: `"Custom"`) |
| `visibility` | `str` | Visibility setting (default: `"Visible"`) |
| `baseEntityTypeId` | `Optional[str]` | Parent entity ID for inheritance |
| `entityIdParts` | `List[str]` | Property IDs forming entity identity |
| `displayNamePropertyId` | `Optional[str]` | Property ID for display name |
| `properties` | `List[EntityTypeProperty]` | Regular properties |
| `timeseriesProperties` | `List[EntityTypeProperty]` | Time-series properties |

---

#### `RelationshipType`

Represents a relationship type in Fabric Ontology.

```python
from src.models import RelationshipType, RelationshipEnd

rel = RelationshipType(
    id="2000000000001",
    name="produces",
    source=RelationshipEnd(entityTypeId="1000000000001"),
    target=RelationshipEnd(entityTypeId="1000000000002"),
)
```

**Attributes:**

| Name | Type | Description |
|------|------|-------------|
| `id` | `str` | Unique numeric identifier |
| `name` | `str` | Relationship name |
| `source` | `RelationshipEnd` | Source entity reference |
| `target` | `RelationshipEnd` | Target entity reference |
| `namespace` | `str` | Ontology namespace |
| `namespaceType` | `str` | Namespace type |

---

#### `ConversionResult`

Container for conversion results with statistics.

```python
result = ConversionResult(
    entity_types=[...],
    relationship_types=[...],
    skipped_items=[...],
    warnings=[...],
    triple_count=1234,
)

print(result.success_rate)      # 95.5
print(result.has_skipped_items) # True
print(result.get_summary())     # Human-readable summary
```

**Attributes:**

| Name | Type | Description |
|------|------|-------------|
| `entity_types` | `List[EntityType]` | Successfully converted entities |
| `relationship_types` | `List[RelationshipType]` | Successfully converted relationships |
| `skipped_items` | `List[SkippedItem]` | Items that couldn't be converted |
| `warnings` | `List[str]` | Warning messages |
| `triple_count` | `int` | RDF triples processed |
| `interface_count` | `int` | DTDL interfaces processed |

**Properties:**

| Name | Returns | Description |
|------|---------|-------------|
| `success_rate` | `float` | Percentage of successful conversions |
| `has_skipped_items` | `bool` | Whether any items were skipped |
| `has_warnings` | `bool` | Whether any warnings were generated |
| `skipped_by_type` | `Dict[str, int]` | Skipped counts by type |

---

### Validators

#### `InputValidator`

Centralized input validation with security checks. Located in `src/core/validators.py`.

```python
from src.core.validators import InputValidator

# Validate file path with security checks
validated_path = InputValidator.validate_file_path(
    "ontology.ttl",
    allowed_extensions=['.ttl', '.rdf'],
    check_exists=True,
    reject_symlinks=True  # Security: reject symlinks by default
)

# Validate TTL input file specifically
validated_path = InputValidator.validate_input_ttl_path("ontology.ttl")

# Validate JSON input file
validated_path = InputValidator.validate_input_json_path("config.json")

# Validate output file path
validated_path = InputValidator.validate_output_file_path(
    "output.ttl",
    allowed_extensions=['.ttl']
)

# Validate TTL content
content = InputValidator.validate_ttl_content(ttl_string)

# Validate ID prefix
prefix = InputValidator.validate_id_prefix(1000000000000)
```

**Security Features:**
- Path traversal detection (`../` patterns)
- Symlink detection and rejection
- Extension validation
- Directory boundary awareness

---

#### `URLValidator`

SSRF (Server-Side Request Forgery) protection for URL handling. Located in `src/core/validators.py`.

```python
from src.core.validators import URLValidator

# Basic URL validation (HTTPS only by default)
validated_url = URLValidator.validate_url("https://example.com/ontology.ttl")

# Validate with domain allowlist
validated_url = URLValidator.validate_url(
    "https://w3.org/ontology.ttl",
    allowed_domains=['w3.org', 'example.com']
)

# Validate ontology URL (uses trusted ontology domains)
validated_url = URLValidator.validate_ontology_url("https://www.w3.org/2002/07/owl#")

# Check if string is a URL
is_url = URLValidator.is_url("https://example.com")  # True
is_url = URLValidator.is_url("/local/path.ttl")      # False

# Sanitize URL for logging (removes credentials/query params)
safe_url = URLValidator.sanitize_url_for_logging("https://user:pass@example.com?secret=key")
```

**Security Features:**
- Protocol validation (HTTPS only by default)
- Private IP blocking (prevents access to 10.x.x.x, 192.168.x.x, 127.0.0.1, etc.)
- Localhost blocking
- Domain allowlist support
- Port restriction (443, 8443 by default)

**Default Trusted Ontology Domains:**
- `w3.org` (W3C standards)
- `purl.org` (Persistent URLs)
- `schema.org` (Schema.org)
- `xmlns.com` (XML namespaces)
- `github.com`, `raw.githubusercontent.com` (GitHub)

---

#### `ValidationRateLimiter`

Rate limiter and resource guard for validation operations. Protects against resource exhaustion attacks. Located in `src/core/validators.py`.

```python
from src.core.validators import ValidationRateLimiter

# Create limiter with default settings
limiter = ValidationRateLimiter()

# Create limiter with custom settings
limiter = ValidationRateLimiter(
    requests_per_minute=30,      # Max validations per minute
    max_content_size_mb=50,      # Max content size in MB
    max_concurrent=5,            # Max concurrent validations
    max_memory_percent=80,       # Max system memory usage %
)

# Check if validation is allowed
allowed, reason = limiter.check_validation_allowed(content)
if not allowed:
    raise ValueError(f"Validation not allowed: {reason}")

# Use context manager for automatic tracking
ctx = limiter.validation_context()
ctx.check(content)
with ctx:
    if ctx.allowed:
        result = validate_content(content)
    else:
        print(f"Blocked: {ctx.reason}")

# Get statistics
stats = limiter.get_statistics()
print(f"Total validations: {stats['total_validations']}")
print(f"Rejected (rate): {stats['rejected_rate_limit']}")
print(f"Rejected (size): {stats['rejected_size']}")

# Disable rate limiting (for testing)
limiter = ValidationRateLimiter(enabled=False)
```

**Protection Features:**
- Request rate limiting (requests per minute)
- Content size limits (prevents processing extremely large files)
- Memory usage monitoring (rejects when system memory is high)
- Concurrent operation limits (prevents resource exhaustion)
- Statistics tracking for monitoring

---

#### `FabricLimitsValidator`

Validates Fabric Ontology definitions against API limits and constraints. Located in `src/core/validators.py`.

```python
from src.core.validators import FabricLimitsValidator

# Create validator with default limits
validator = FabricLimitsValidator()

# Create validator with custom limits
validator = FabricLimitsValidator(
    max_entity_name_length=256,
    max_property_name_length=256,
    max_relationship_name_length=256,
    max_definition_size_kb=1024,
    warn_definition_size_kb=768,
    max_entity_types=500,
    max_relationship_types=500,
    max_properties_per_entity=200,
    max_entity_id_parts=5,
)

# Validate entity types
entity_errors = validator.validate_entity_types(entity_types)

# Validate relationship types
rel_errors = validator.validate_relationship_types(relationship_types)

# Validate definition size
size_errors = validator.validate_definition_size(entity_types, relationship_types)

# Validate all at once
all_errors = validator.validate_all(entity_types, relationship_types)

# Check for errors vs warnings
if validator.has_errors(all_errors):
    critical = validator.get_errors_only(all_errors)
    raise ValueError(f"Fabric limits exceeded: {critical[0].message}")

# Log warnings
for warning in validator.get_warnings_only(all_errors):
    logger.warning(f"Approaching limit: {warning.message}")
```

**Validation Checks:**

| Check | Default Limit | Description |
|-------|---------------|-------------|
| Entity name length | 256 chars | Maximum characters in entity type name |
| Property name length | 256 chars | Maximum characters in property name |
| Relationship name length | 256 chars | Maximum characters in relationship name |
| Definition size | 1024 KB | Maximum JSON size of entire definition |
| Entity type count | 500 | Maximum entity types per ontology |
| Relationship type count | 500 | Maximum relationship types per ontology |
| Properties per entity | 200 | Maximum properties per entity type |
| entityIdParts count | 5 | Maximum properties in entityIdParts |

**FabricLimitValidationError:**

```python
@dataclass
class FabricLimitValidationError:
    level: str          # "error" or "warning"
    message: str        # Human-readable description
    entity_name: str    # Affected entity/property name
    field: str          # Field that violated limit
    current_value: Any  # Current value
    limit_value: Any    # Limit that was exceeded
```

---

#### `EntityIdPartsInferrer`

Intelligently infers and sets `entityIdParts` for entity types. Located in `src/core/validators.py`.

```python
from src.core.validators import EntityIdPartsInferrer

# Auto strategy (default) - looks for id/key patterns, falls back to first valid type
inferrer = EntityIdPartsInferrer(strategy="auto")

# First valid strategy - uses first String/BigInt property
inferrer = EntityIdPartsInferrer(strategy="first_valid")

# Explicit strategy - only uses explicit mappings
inferrer = EntityIdPartsInferrer(
    strategy="explicit",
    explicit_mappings={
        "Machine": ["serialNumber"],
        "Product": ["productCode", "batchId"],
    }
)

# None strategy - never auto-set entityIdParts
inferrer = EntityIdPartsInferrer(strategy="none")

# Custom patterns for primary key detection
inferrer = EntityIdPartsInferrer(
    strategy="auto",
    custom_patterns=["record_id", "asset_code"],
)

# Infer for single entity
entity_id_parts = inferrer.infer_entity_id_parts(entity)

# Infer for all entities (modifies in place)
updated_count = inferrer.infer_all(entity_types, overwrite=False)

# Set displayNamePropertyId
display_prop_id = inferrer.set_display_name_property(entity)
```

**Inference Strategies:**

| Strategy | Behavior |
|----------|----------|
| `auto` | Match property names against primary key patterns, then fall back to first valid |
| `first_valid` | Use first property with valid type (String or BigInt) |
| `explicit` | Only set if entity name has explicit mapping |
| `none` | Never automatically set entityIdParts |

**Default Primary Key Patterns:**
- `id`, `identifier`, `pk`, `primary_key`, `key`
- `uuid`, `guid`, `oid`, `object_id`
- `entity_id`, `record_id`, `unique_id`

**Valid Types for entityIdParts:**
- `String`
- `BigInt`

---

### Streaming Engine

The streaming engine provides a unified infrastructure for memory-efficient processing of large ontology files in both RDF (TTL) and DTDL (JSON) formats. Located in `src/core/streaming.py`.

#### Overview

```python
from src.core.streaming import (
    StreamingEngine,
    StreamConfig,
    RDFStreamReader,
    DTDLStreamReader,
    RDFChunkProcessor,
    DTDLChunkProcessor,
    RDFStreamAdapter,
    DTDLStreamAdapter,
    should_use_streaming,
)

# Quick check if streaming is recommended
if should_use_streaming("large_ontology.ttl", threshold_mb=100):
    print("Consider using streaming mode")
```

#### `StreamConfig`

Configuration for streaming operations.

```python
from src.core.streaming import StreamConfig, StreamFormat

# Default configuration
config = StreamConfig()

# Custom configuration
config = StreamConfig(
    chunk_size=5000,           # Items per chunk (default: 10000)
    memory_threshold_mb=50.0,  # When to use streaming (default: 100)
    max_memory_usage_mb=256.0, # Memory limit (default: 512)
    enable_progress=True,      # Enable callbacks (default: True)
    format=StreamFormat.AUTO,  # AUTO, RDF, or DTDL
    buffer_size_bytes=65536,   # I/O buffer size (default: 64KB)
)

# Check if streaming should be used
if config.should_use_streaming(file_size_mb=150.0):
    use_streaming_mode()
```

#### `StreamingEngine`

Main orchestrator for streaming operations.

```python
from src.core.streaming import (
    StreamingEngine, 
    DTDLStreamReader, 
    DTDLChunkProcessor,
    StreamConfig,
)

# Create engine with explicit reader/processor
engine = StreamingEngine(
    reader=DTDLStreamReader(),
    processor=DTDLChunkProcessor(),
    config=StreamConfig(chunk_size=100)
)

# Process file with progress callback
def progress(items_processed):
    print(f"Processed {items_processed} items")

result = engine.process_file(
    "large_models.json",
    progress_callback=progress,
    cancellation_token=None  # Optional CancellationToken
)

# Check results
if result.success:
    print(f"Interfaces found: {result.data.interface_count}")
    print(f"Properties found: {result.data.property_count}")
    print(result.stats.get_summary())
else:
    print(f"Error: {result.error_message}")
```

#### `StreamResult`

Container for streaming operation results.

```python
from src.core.streaming import StreamResult

# StreamResult attributes:
# - data: The processed result (format-specific)
# - stats: StreamStats with processing statistics
# - success: bool indicating success/failure
# - error_message: Error description if failed
```

#### `StreamStats`

Statistics collected during streaming.

```python
from src.core.streaming import StreamStats

stats = StreamStats()
print(stats.chunks_processed)    # Number of chunks processed
print(stats.items_processed)     # Total items (triples, interfaces)
print(stats.bytes_read)          # Total bytes read
print(stats.errors_encountered)  # Recoverable errors
print(stats.peak_memory_mb)      # Peak memory usage
print(stats.duration_seconds)    # Processing time
print(stats.get_summary())       # Human-readable summary
```

#### RDF Streaming

```python
from src.core.streaming import (
    RDFStreamReader,
    RDFChunkProcessor,
    RDFStreamAdapter,
    StreamingEngine,
)

# Using the streaming engine
engine = StreamingEngine(
    reader=RDFStreamReader(),
    processor=RDFChunkProcessor()
)
result = engine.process_file("ontology.ttl")

# Using the adapter (wraps existing StreamingRDFConverter)
adapter = RDFStreamAdapter(
    id_prefix=1000000000000,
    batch_size=10000,
    loose_inference=False
)
conversion_result = adapter.convert_streaming(
    "large_ontology.ttl",
    progress_callback=lambda n: print(f"Processed {n} triples")
)
```

#### DTDL Streaming

```python
from src.core.streaming import (
    DTDLStreamReader,
    DTDLChunkProcessor,
    DTDLStreamAdapter,
    StreamingEngine,
    StreamConfig,
)

# Process single file
engine = StreamingEngine(
    reader=DTDLStreamReader(),
    processor=DTDLChunkProcessor()
)
result = engine.process_file("models.json")

# Process directory of DTDL files
result = engine.process_file("./models/")

# Using the adapter for full conversion
adapter = DTDLStreamAdapter(
    config=StreamConfig(chunk_size=50),
    ontology_name="LargeOntology",
    namespace="usertypes"
)
conversion_result = adapter.convert_streaming("./large_models/")
```

#### Custom Streaming Implementation

Extend the base classes for custom formats:

```python
from src.core.streaming import StreamReader, ChunkProcessor, StreamingEngine

class MyChunk:
    """Custom chunk type."""
    data: list
    
class MyResult:
    """Custom result type."""
    items: list

class MyStreamReader(StreamReader[MyChunk]):
    def read_chunks(self, file_path, config):
        # Yield chunks from file
        yield MyChunk(data=[...]), bytes_read
    
    def get_total_size(self, file_path):
        return os.path.getsize(file_path)
    
    def supports_format(self, file_path):
        return file_path.endswith('.custom')

class MyChunkProcessor(ChunkProcessor[MyChunk, MyResult]):
    def process_chunk(self, chunk, chunk_index):
        return MyResult(items=chunk.data)
    
    def merge_results(self, results):
        merged = MyResult(items=[])
        for r in results:
            merged.items.extend(r.items)
        return merged
    
    def finalize(self, result):
        return result

# Use custom implementation
engine = StreamingEngine(
    reader=MyStreamReader(),
    processor=MyChunkProcessor()
)
```

#### Utility Functions

```python
from src.core.streaming import should_use_streaming, get_streaming_threshold

# Check if streaming is recommended
if should_use_streaming("large_file.json", threshold_mb=50):
    use_streaming()

# Get configured threshold
threshold = get_streaming_threshold()  # Default: 100 MB
```

---

## RDF/OWL Conversion

Components for converting RDF/OWL/TTL ontologies to Fabric format.

### RDF Converter

#### `RDFToFabricConverter`

Converts RDF/TTL ontologies to Fabric format.

```python
from src.rdf_converter import RDFToFabricConverter, parse_ttl_with_result

# Using the converter class
converter = RDFToFabricConverter()
entity_types, relationship_types = converter.parse_ttl(ttl_content)

# Using the convenience function
definition, ontology_name, result = parse_ttl_with_result(
    ttl_content,
    id_prefix=1000000000000,
    force_large_file=False
)
```

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `parse_ttl(content)` | `str` | `Tuple[List[EntityType], List[RelationshipType]]` | Parse TTL string |
| `parse_ttl_file(path)` | `str` | Same as above | Parse TTL file |

**Convenience Functions:**

```python
# Basic parsing
definition, name, result = parse_ttl_with_result(ttl_content, id_prefix=1000000000000)

# Streaming for large files
definition, name, result = parse_ttl_streaming(file_path, progress_callback=lambda n: print(n))
```

---

### RDF Components

The RDF conversion functionality has been modularized for better maintainability. The following components are available in `src/rdf/`:

#### `MemoryManager`

Manages memory usage during RDF parsing to prevent out-of-memory crashes.

```python
from rdf import MemoryManager

# Check if enough memory is available to parse a file
can_proceed, message = MemoryManager.check_memory_available(
    file_size_mb=100.0,
    force=False
)

if can_proceed:
    print(f"Memory OK: {message}")
else:
    print(f"Insufficient memory: {message}")

# Get current memory status
available_mb = MemoryManager.get_available_memory_mb()
process_mb = MemoryManager.get_memory_usage_mb()

# Log memory status for debugging
MemoryManager.log_memory_status("After parsing")
```

#### `RDFGraphParser`

Handles TTL/RDF parsing with memory safety checks.

```python
from rdf import RDFGraphParser

# Parse TTL content with memory safety
graph, triple_count, size_mb = RDFGraphParser.parse_ttl_content(
    ttl_content,
    force_large_file=False
)

# Parse TTL file with memory safety
graph, triple_count, size_mb = RDFGraphParser.parse_ttl_file(
    "ontology.ttl",
    force_large_file=False
)
```

#### `ClassExtractor`

Extracts OWL/RDFS classes as entity types.

```python
from rdf import ClassExtractor

entity_types, uri_to_id = ClassExtractor.extract_classes(
    graph,
    id_prefix,
    uri_to_name=lambda uri: uri.split('/')[-1]
)
```

#### `DataPropertyExtractor`

Extracts data properties and assigns them to entity types.

```python
from rdf import DataPropertyExtractor

property_to_domain, uri_to_id = DataPropertyExtractor.extract_data_properties(
    graph,
    entity_types,
    id_prefix,
    uri_to_name
)
```

#### `ObjectPropertyExtractor`

Extracts object properties as relationship types.

```python
from rdf import ObjectPropertyExtractor

relationship_types, uri_to_id = ObjectPropertyExtractor.extract_object_properties(
    graph,
    entity_types,
    id_prefix,
    uri_to_id_map,
    uri_to_name,
    skip_callback=lambda type, name, reason, uri: print(f"Skipped {name}: {reason}")
)
```

#### `EntityIdentifierSetter`

Sets entity ID parts and display name properties for entity types.

```python
from rdf import EntityIdentifierSetter

# Modifies entity_types in place
EntityIdentifierSetter.set_identifiers(entity_types)
```

#### Other Converter Utilities

```python
from rdf import TypeMapper, URIUtils, ClassResolver, FabricSerializer

# Type mapping
fabric_type = TypeMapper.get_fabric_type("http://www.w3.org/2001/XMLSchema#string")

# URI utilities  
name = URIUtils.uri_to_name(uri, fallback_counter=1)

# Class resolution (for union/intersection types)
targets = ClassResolver.resolve_class_targets(graph, node)

# Fabric JSON serialization
definition = FabricSerializer.create_definition(entity_types, relationship_types, "MyOntology")
```

---

## DTDL Conversion

Components for converting DTDL (Digital Twins Definition Language) v2/v3/v4 models to Fabric format.

### DTDL Parser

#### `DTDLParser`

Parses DTDL v2, v3, and v4 JSON files into typed models.

```python
from src.dtdl import DTDLParser

parser = DTDLParser()

# Parse a single file
result = parser.parse_file("models/thermostat.json")

# Parse a directory
result = parser.parse_directory("models/", recursive=True)

# Parse JSON string
result = parser.parse_string(json_content)
```

**Returns:** `ParseResult` with:
- `interfaces: List[DTDLInterface]`
- `errors: List[str]`
- `success: bool`

**Supported DTDL v4 Types:**
- All v2/v3 primitives: `boolean`, `date`, `dateTime`, `double`, `duration`, `float`, `integer`, `long`, `string`, `time`
- New v4 primitives: `byte`, `bytes`, `decimal`, `short`, `uuid`, `unsignedByte`, `unsignedShort`, `unsignedInteger`, `unsignedLong`
- v4 `scaledDecimal` schema for high-precision decimals
- Geospatial types: `point`, `lineString`, `polygon`, `multiPoint`, `multiLineString`, `multiPolygon`

---

#### `DTDLScaledDecimal`

Represents a DTDL v4 scaled decimal schema with arbitrary precision.

```python
from src.dtdl.dtdl_models import DTDLScaledDecimal

# Create a scaled decimal schema for temperature with 2 decimal places
schema = DTDLScaledDecimal(precision=10, scale=2)

# Convert to DTDL dict representation
dtdl_dict = schema.to_dict()
# {'@type': 'ScaledDecimal', 'precision': 10, 'scale': 2}

# Get JSON schema representation
json_schema = schema.get_json_schema()
# {'type': 'string', 'pattern': '^-?\\d+\\.\\d{2}$', 'description': 'Scaled decimal...'}
```

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `precision` | `int` | Total number of significant digits (must be > 0) |
| `scale` | `int` | Digits after decimal point (0 ≤ scale ≤ precision) |

**DTMI:** `dtmi:dtdl:instance:Schema:scaledDecimal;4`

---

### DTDL Validator

#### `DTDLValidator`

Validates DTDL interfaces for correctness. Supports v4 validation limits.

```python
from src.dtdl import DTDLValidator

validator = DTDLValidator(
    allow_external_references=True,
    strict_mode=False
)

result = validator.validate(interfaces)

if result.is_valid:
    print("Validation passed!")
else:
    for error in result.errors:
        print(error)
```

**v4 Validation Limits:**
- Maximum inheritance depth: 12 levels
- Maximum complex schema nesting: 8 levels

---

### DTDL to Fabric Converter

#### `DTDLToFabricConverter`

Converts DTDL interfaces to Fabric format with configurable handling of Components, Commands, and scaledDecimal.

```python
from src.dtdl import (
    DTDLToFabricConverter,
    ComponentMode,
    CommandMode,
    ScaledDecimalMode
)

# Basic usage (default modes)
converter = DTDLToFabricConverter(
    namespace="usertypes"
)
result = converter.convert(interfaces)

# Advanced usage with all modes configured
converter = DTDLToFabricConverter(
    namespace="usertypes",
    component_mode=ComponentMode.SEPARATE,    # Create separate entities for components
    command_mode=CommandMode.ENTITY,          # Create Command entities
    scaled_decimal_mode=ScaledDecimalMode.STRUCTURED  # Create _scale/_value properties
)
result = converter.convert(interfaces)
definition = converter.to_fabric_definition(result, "my_ontology")
```

**Constructor Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `id_prefix` | `int` | `1000000000000` | Base prefix for generated IDs |
| `namespace` | `str` | `"usertypes"` | Namespace for entity types |
| `component_mode` | `ComponentMode` | `SKIP` | How to handle DTDL Components |
| `command_mode` | `CommandMode` | `SKIP` | How to handle DTDL Commands |
| `scaled_decimal_mode` | `ScaledDecimalMode` | `JSON_STRING` | How to handle scaledDecimal |
| `flatten_components` | `bool` | `False` | DEPRECATED: Use `component_mode=FLATTEN` |
| `include_commands` | `bool` | `False` | DEPRECATED: Use `command_mode=PROPERTY` |

**`ComponentMode` Enum:**

| Value | Behavior |
|-------|----------|
| `SKIP` | Components are ignored (default) |
| `FLATTEN` | Properties merged into parent with `{component}_` prefix |
| `SEPARATE` | Creates separate EntityType with `has_{component}` relationship |

**`CommandMode` Enum:**

| Value | Behavior |
|-------|----------|
| `SKIP` | Commands are ignored (default) |
| `PROPERTY` | Creates `command_{name}` String property |
| `ENTITY` | Creates `Command_{name}` EntityType with request/response properties |

**`ScaledDecimalMode` Enum:**

| Value | Behavior |
|-------|----------|
| `JSON_STRING` | Stored as JSON: `{"scale": n, "value": "x"}` (default) |
| `STRUCTURED` | Creates `{prop}_scale` (BigInt) and `{prop}_value` (String) properties |
| `CALCULATED` | Calculates `value × 10^scale` and stores as Double |

**`ScaledDecimalValue` Class:**

Helper class for working with scaledDecimal values.

```python
from src.dtdl import ScaledDecimalValue

# Create and calculate
sd = ScaledDecimalValue(scale=7, value="1234.56")
actual = sd.calculate_actual_value()  # Returns 12345600000.0

# Get JSON representation
json_obj = sd.to_json_object()
# {"scale": 7, "value": "1234.56", "calculatedValue": 12345600000.0}
```

**v4 Type Mappings:**
| DTDL v4 Type | Fabric ValueType | Notes |
|--------------|------------------|-------|
| `scaledDecimal` | `String` / `Double` | Depends on `scaled_decimal_mode` |
| `byte` | `BigInt` | |
| `bytes` | `String` | Base64 encoded |
| `decimal` | `Double` | |
| `short` | `BigInt` | |
| `uuid` | `String` | |
| `unsignedByte` | `BigInt` | |
| `unsignedShort` | `BigInt` | |
| `unsignedInteger` | `BigInt` | |
| `unsignedLong` | `BigInt` | |

---

## Fabric Client

HTTP client for interacting with Microsoft Fabric Ontology API.

### `FabricOntologyClient`

HTTP client for the Fabric Ontology API.

```python
from src.fabric_client import FabricOntologyClient, FabricConfig

config = FabricConfig(
    tenant_id="...",
    client_id="...",
    workspace_id="...",
)

client = FabricOntologyClient(config)

# List ontologies
ontologies = client.list_ontologies()

# Get ontology
ontology = client.get_ontology(ontology_id)

# Get definition
definition = client.get_ontology_definition(ontology_id)

# Create or update
result = client.create_or_update_ontology(
    display_name="My Ontology",
    description="Description",
    definition=definition,
    wait_for_completion=True
)

# Delete
client.delete_ontology(ontology_id)
```

---

## CLI Commands

The converter provides a comprehensive command-line interface for importing, validating, and managing ontologies. For detailed documentation on all available commands, options, and usage patterns, see [COMMANDS.md](COMMANDS.md).

### Quick Reference

**RDF/OWL Operations:**
```bash
# Import TTL/RDF ontology
python -m src.main import <ttl_file> [--name NAME] [--streaming]

# Validate TTL file
python -m src.main rdf-validate <ttl_file>

# Convert to JSON (without upload)
python -m src.main rdf-convert <ttl_file> [--output FILE]

# Export to TTL
python -m src.main rdf-export <ontology_id> [--output FILE]
```

**DTDL Operations:**
```bash
# Import DTDL models
python -m src.main dtdl-upload <path> [--ontology-name NAME] [--recursive]

# Validate DTDL models
python -m src.main dtdl-validate <path> [--recursive]
```

**Ontology Management:**
```bash
# List ontologies
python -m src.main list

# Get ontology details
python -m src.main get <ontology_id> [--with-definition]

# Delete ontology
python -m src.main delete <ontology_id> [--force]
```

> **Note:** See [COMMANDS.md](COMMANDS.md) for complete documentation including all options, examples, and advanced usage patterns.

---

## Error Handling

### `FabricAPIError`

```python
from src.fabric_client import FabricAPIError

try:
    client.create_or_update_ontology(...)
except FabricAPIError as e:
    print(f"Error: {e.message}")
    print(f"Code: {e.error_code}")
    print(f"Status: {e.status_code}")
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `ItemDisplayNameAlreadyInUse` | Ontology name already exists |
| `InvalidOntologyDefinition` | Definition validation failed |
| `RateLimitExceeded` | Too many requests |
| `Unauthorized` | Authentication failed |

---

## Type Mappings

### XSD → Fabric

| XSD Type | Fabric Type |
|----------|-------------|
| `xsd:string` | String |
| `xsd:boolean` | Boolean |
| `xsd:dateTime`, `xsd:date` | DateTime |
| `xsd:integer`, `xsd:int`, `xsd:long` | BigInt |
| `xsd:double`, `xsd:float`, `xsd:decimal` | Double |
| `xsd:anyURI` | String |
| `xsd:time` | String |

### DTDL → Fabric

| DTDL Type | Fabric Type |
|-----------|-------------|
| `boolean` | Boolean |
| `integer`, `long`, `short`, `byte` | BigInt |
| `double`, `float` | Double |
| `string`, `uuid` | String |
| `dateTime`, `date` | DateTime |
| `duration`, `time` | String |
| Complex types (Object, Array, Map) | String (JSON) |
