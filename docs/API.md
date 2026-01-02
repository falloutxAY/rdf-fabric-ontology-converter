# API Reference

This document provides detailed API documentation for the RDF/DTDL to Microsoft Fabric Ontology converter.

---

## Core Modules

### `src.models` — Shared Data Models

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

## Core Utilities

### `InputValidator`

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

### `URLValidator`

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

### `ValidationRateLimiter`

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

## RDF Converter

### `RDFToFabricConverter`

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

#### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `parse_ttl(content)` | `str` | `Tuple[List[EntityType], List[RelationshipType]]` | Parse TTL string |
| `parse_ttl_file(path)` | `str` | Same as above | Parse TTL file |

#### Convenience Functions

```python
# Basic parsing
definition, name, result = parse_ttl_with_result(ttl_content, id_prefix=1000000000000)

# Streaming for large files
definition, name, result = parse_ttl_streaming(file_path, progress_callback=lambda n: print(n))
```

---

## DTDL Converter

### `DTDLParser`

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

### `DTDLScaledDecimal`

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

### `DTDLValidator`

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

### `DTDLToFabricConverter`

Converts DTDL interfaces to Fabric format.

```python
from src.dtdl import DTDLToFabricConverter

converter = DTDLToFabricConverter(
    namespace="usertypes",
    flatten_components=False
)

result = converter.convert(interfaces)
definition = converter.to_fabric_definition(result, "my_ontology")
```

**v4 Type Mappings:**
| DTDL v4 Type | Fabric ValueType |
|--------------|------------------|
| `scaledDecimal` | `string` (JSON-encoded) |
| `byte` | `integer` |
| `bytes` | `binary` |
| `decimal` | `string` |
| `short` | `integer` |
| `uuid` | `string` |
| `unsignedByte` | `integer` |
| `unsignedShort` | `integer` |
| `unsignedInteger` | `integer` |
| `unsignedLong` | `integer` |

---

## Fabric Client

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

## RDF Converter Components

The RDF conversion functionality has been modularized for better maintainability. The following components are available in `src/converters/`:

### `MemoryManager`

Manages memory usage during RDF parsing to prevent out-of-memory crashes.

```python
from src.converters import MemoryManager

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

### `RDFGraphParser`

Handles TTL/RDF parsing with memory safety checks.

```python
from src.converters import RDFGraphParser

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

### `ClassExtractor`

Extracts OWL/RDFS classes as entity types.

```python
from src.converters import ClassExtractor

entity_types, uri_to_id = ClassExtractor.extract_classes(
    graph,
    id_generator=lambda: str(counter := counter + 1),
    uri_to_name=lambda uri: uri.split('/')[-1]
)
```

### `DataPropertyExtractor`

Extracts data properties and assigns them to entity types.

```python
from src.converters import DataPropertyExtractor

property_to_domain, uri_to_id = DataPropertyExtractor.extract_data_properties(
    graph,
    entity_types,
    id_generator,
    uri_to_name
)
```

### `ObjectPropertyExtractor`

Extracts object properties as relationship types.

```python
from src.converters import ObjectPropertyExtractor

relationship_types, uri_to_id = ObjectPropertyExtractor.extract_object_properties(
    graph,
    entity_types,
    property_to_domain,
    id_generator,
    uri_to_name,
    skip_callback=lambda type, name, reason, uri: print(f"Skipped {name}: {reason}")
)
```

### `EntityIdentifierSetter`

Sets entity ID parts and display name properties for entity types.

```python
from src.converters import EntityIdentifierSetter

# Modifies entity_types in place
EntityIdentifierSetter.set_identifiers(entity_types)
```

### Other Converter Utilities

```python
from src.converters import TypeMapper, URIUtils, ClassResolver, FabricSerializer

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

## CLI Commands

### Import RDF

```bash
python -m src.main import <ttl_file> [options]

Options:
  --name NAME           Ontology name (default: extracted from file)
  --description DESC    Description
  --config PATH         Configuration file path
  --force               Skip confirmations
  --streaming           Use streaming mode for large files
  --skip-validation     Skip pre-flight validation
```

### Import DTDL

```bash
python -m src.main dtdl-upload <path> [options]

Options:
  --ontology-name NAME  Ontology name
  --namespace NS        Target namespace (default: usertypes)
  --recursive           Parse subdirectories
  --dry-run             Convert but don't upload
  --config PATH         Configuration file
```

### Other Commands

```bash
# Validate TTL file
python -m src.main rdf-validate <ttl_file>

# List ontologies
python -m src.main list

# Get ontology details
python -m src.main get <ontology_id> [--with-definition]

# Delete ontology
python -m src.main delete <ontology_id> [--force]

# Export to TTL
python -m src.main rdf-export <ontology_id> [--output FILE]

# Convert to JSON (without upload)
python -m src.main rdf-convert <ttl_file> [--output FILE]
```

> **Note:** Legacy command names without the `rdf-` prefix (e.g., `validate`, `upload`, `convert`, `export`)
> and `dtdl-import` are deprecated but still work for backward compatibility.

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
