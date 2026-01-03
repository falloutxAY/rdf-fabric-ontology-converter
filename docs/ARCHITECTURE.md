# Architecture Overview

This document provides a comprehensive overview of the RDF/DTDL to Microsoft Fabric Ontology Converter architecture, design decisions, and component interactions.

## Table of Contents

- [High-Level Design](#high-level-design)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Module Structure](#module-structure)
- [Design Patterns](#design-patterns)
- [Extensibility](#extensibility)

---

## High-Level Design

The converter follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLI Layer                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────┐│
│  │   RDF Cmds   │ │   DTDL Cmds  │ │  Common Cmds (list/get/etc) ││
│  │  rdf-validate│ │  dtdl-validate│ │  list-ontologies            ││
│  │  rdf-convert │ │  dtdl-convert│ │  get-ontology               ││
│  │  rdf-upload  │ │  dtdl-upload │ │  delete-ontology            ││
│  │  rdf-export  │ │              │ │  fabric-to-ttl              ││
│  └──────┬───────┘ └──────┬───────┘ └────────────┬─────────────────┘│
└─────────┼────────────────┼──────────────────────┼──────────────────┘
          │                │                      │
          ▼                ▼                      │
┌─────────────────────────────────────────────────────────────────────┐
│                       Converter Layer                                │
│  ┌──────────────────────┐          ┌──────────────────────────────┐│
│  │   RDF Pipeline       │          │      DTDL Pipeline           ││
│  │  ┌────────────────┐  │          │  ┌────────────────────────┐ ││
│  │  │PreflightValidator│ │          │  │   DTDLParser           │ ││
│  │  └────────┬─────────┘│          │  └──────────┬─────────────┘ ││
│  │           ▼          │          │             ▼               ││
│  │  ┌────────────────┐  │          │  ┌────────────────────────┐ ││
│  │  │ RDFToFabric    │  │          │  │   DTDLValidator        │ ││
│  │  │  Converter     │  │          │  └──────────┬─────────────┘ ││
│  │  │ (rdflib Graph) │  │          │             ▼               ││
│  │  └────────┬───────┘  │          │  ┌────────────────────────┐ ││
│  │           │          │          │  │  DTDLToFabricConverter │ ││
│  │           │          │          │  └──────────┬─────────────┘ ││
│  └───────────┼──────────┘          └─────────────┼───────────────┘│
│              │                                    │                 │
│              └────────────┬───────────────────────┘                 │
│                           ▼                                         │
│              ┌─────────────────────────┐                            │
│              │   Shared Models         │                            │
│              │  - EntityType           │                            │
│              │  - RelationshipType     │                            │
│              │  - ConversionResult     │                            │
│              │  - ValidationResult     │                            │
│              └────────────┬────────────┘                            │
└───────────────────────────┼─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Fabric Client Layer                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────┐│
│  │Rate Limiter  │ │Circuit Breaker│ │   Core Utilities             ││
│  │Token Bucket  │ │State Machine  │ │   - CancellationToken        ││
│  │10 req/min    │ │5 fail → OPEN  │ │   - MemoryManager            ││
│  └──────┬───────┘ └──────┬───────┘ └──────────┬───────────────────┘│
│         │                │                    │                     │
│         └────────────────┼────────────────────┘                     │
│                          ▼                                          │
│              ┌────────────────────────┐                             │
│              │ FabricOntologyClient   │                             │
│              │  - create_ontology()   │                             │
│              │  - update_definition() │                             │
│              │  - list_ontologies()   │                             │
│              │  - delete_ontology()   │                             │
│              └────────────┬───────────┘                             │
└───────────────────────────┼─────────────────────────────────────────┘
                            │
                            ▼
               ┌─────────────────────────┐
               │  Microsoft Fabric API   │
               │  /v1/workspaces/{id}/   │
               │    ontology/items/*     │
               └─────────────────────────┘
```

---

## Component Architecture

### 1. CLI Layer (`src/cli/`)

**Responsibility:** User interface and command dispatch

**Components:**
- `commands/` - Modular command implementations:
  - `base.py` - BaseCommand ABC and protocol interfaces
  - `common.py` - Common commands (list, get, delete, test, compare)
  - `rdf.py` - RDF/TTL commands (validate, upload, convert, export)
  - `dtdl.py` - DTDL commands (validate, convert, upload)
- `helpers.py` - Utility functions for CLI operations
- `parsers.py` - Argument parsing and validation

**Key Features:**
- Command pattern for extensibility
- Consistent error handling and exit codes
- Progress indicators for long-running operations
- Graceful cancellation support (Ctrl+C)

### 2. Converter Layer

#### 2.1 RDF Pipeline (`src/rdf/`)

**PreflightValidator** (`rdf/preflight_validator.py`)
- Scans TTL files before conversion
- Detects unsupported OWL constructs (restrictions, property chains)
- Validates file size and estimates memory requirements
- Generates detailed validation reports

**RDFToFabricConverter** (`rdf/rdf_converter.py`) - Facade/Orchestrator
- Main entry point for RDF to Fabric conversion
- Uses composition pattern delegating to extracted components:
  - `rdf/rdf_parser.py` - TTL parsing with memory management
  - `rdf/property_extractor.py` - Class/property extraction
  - `rdf/type_mapper.py` - XSD to Fabric type mapping
  - `rdf/uri_utils.py` - URI parsing and name extraction
  - `rdf/class_resolver.py` - OWL class expression resolution
  - `rdf/fabric_serializer.py` - Fabric API JSON serialization
- Handles OWL/RDFS constructs:
  - `owl:Class` → EntityType
  - `owl:DatatypeProperty` → EntityTypeProperty
  - `owl:ObjectProperty` → RelationshipType
  - `rdfs:subClassOf` → inheritance

**RDF Converter Components** (`src/rdf/`)
- `rdf_parser.py` - MemoryManager and RDFGraphParser for TTL parsing
- `property_extractor.py` - ClassExtractor, DataPropertyExtractor, ObjectPropertyExtractor
- `type_mapper.py` - TypeMapper for XSD to Fabric type mapping
- `uri_utils.py` - URIUtils for URI parsing and name extraction
- `class_resolver.py` - ClassResolver for OWL class expression resolution
- `fabric_serializer.py` - FabricSerializer for Fabric API JSON creation

**FabricToTTLExporter** (`rdf/fabric_to_ttl.py`)
- Reverse conversion: Fabric → TTL
- Preserves class hierarchy
- Generates valid RDF/OWL syntax

#### 2.2 DTDL Pipeline (`src/dtdl/`)

**DTDLParser** (`dtdl_parser.py`)
- Parses DTDL v2, v3, and v4 JSON files
- Supports all DTDL primitive types including v4 additions:
  - `byte`, `bytes`, `decimal`, `short`, `uuid`
  - Unsigned types: `unsignedByte`, `unsignedShort`, `unsignedInteger`, `unsignedLong`
  - `scaledDecimal` for high-precision decimal values
- Handles complex schemas (Array, Enum, Map, Object)
- Supports geospatial schemas: `point`, `lineString`, `polygon`, `multiPoint`, `multiLineString`, `multiPolygon`
- Resolves `extends` inheritance (max 12 levels per v4 spec)

**DTDLValidator** (`dtdl_validator.py`)
- Validates DTMI format
- Checks interface structure
- Verifies relationship targets
- Validates semantic types and units
- Enforces v4 limits: 12 inheritance levels, 8 complex schema depth

**DTDLToFabricConverter** (`dtdl_converter.py`)
- Maps DTDL interfaces to EntityType
- Converts properties and telemetry
- Handles relationships with cardinality
- Flattens components to properties
- Maps `scaledDecimal` to JSON-encoded strings

### 3. Shared Models (`src/models/`)

**Purpose:** Single source of truth for data structures

**Components:**
- `base.py` - Abstract converter interface
- `fabric_types.py` - EntityType, RelationshipType definitions
- `conversion.py` - ConversionResult, SkippedItem, ValidationResult

**Benefits:**
- Eliminates code duplication
- Type safety across converters
- Easy to extend with new formats

### 4. Core Utilities (`src/core/`)

**Rate Limiter** (`rate_limiter.py`)
- Token bucket algorithm
- 10 requests/min default (configurable)
- Burst allowance for short spikes
- Thread-safe implementation

**Circuit Breaker** (`circuit_breaker.py`)
- Three states: CLOSED, OPEN, HALF_OPEN
- 5 failures → OPEN (configurable)
- 60s recovery timeout
- Per-endpoint isolation

**Cancellation Handler** (`cancellation.py`)
- Graceful Ctrl+C handling
- Callback registration for cleanup
- No resource leaks on interrupt

**Memory Manager** (`memory.py`)
- Pre-flight memory checks
- Prevents OOM crashes
- File size × 3.5 multiplier for RDF parsing
- Warning messages for large files

**Authentication** (`auth.py`)
- `CredentialFactory` - Creates Azure credentials (service principal, browser, managed identity)
- `TokenManager` - Thread-safe token caching with automatic refresh

**HTTP Client** (`http_client.py`)
- `RequestHandler` - Centralized HTTP request handling with rate limiting
- `ResponseHandler` - Response parsing and error handling
- `TransientAPIError` / `FabricAPIError` - Exception classes for API errors
- Helper functions: `is_transient_error`, `get_retry_wait_time`, `sanitize_display_name`

**LRO Handler** (`lro_handler.py`)
- `LROHandler` - Long-running operation polling with progress reporting
- Supports cancellation tokens
- Handles result fetching from operation URLs

**Streaming Engine** (`streaming.py`)
- `StreamingEngine` - Memory-efficient processing for large files
- Format adapters for RDF and DTDL
- Auto-detection based on file extension

### 5. Fabric Client (`core/fabric_client.py`)

**Responsibilities:**
- Authentication (interactive, service principal, managed identity)
- HTTP requests with retry logic (exponential backoff)
- Multi-part ontology definition upload
- Error handling and logging

**Authentication Modes:**
1. **Interactive** - Browser-based Azure login
2. **Service Principal** - Client ID + Secret/Certificate
3. **Managed Identity** - For Azure-hosted apps

---

## Data Flow

### RDF Import Flow

```
┌─────────────┐
│  User Input │
│  TTL File   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│  PreflightValidator     │
│  - Check file size      │
│  - Scan for unsupported │
│    OWL constructs       │
│  - Estimate memory      │
└──────┬──────────────────┘
       │ validation_ok?
       ▼ (yes)
┌─────────────────────────┐
│  RDFToFabricConverter   │
│  - Parse with rdflib    │
│  - Extract classes      │
│  - Extract properties   │
│  - Map XSD types        │
│  - Resolve URIs         │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  ConversionResult       │
│  - entity_types[]       │
│  - relationship_types[] │
│  - skipped_items[]      │
│  - warnings[]           │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  FabricSerializer       │
│  - Build JSON structure │
│  - Multi-part format    │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  FabricOntologyClient   │
│  - Rate limiting        │
│  - Circuit breaker      │
│  - POST /ontology/items │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Microsoft Fabric API   │
└─────────────────────────┘
```

### DTDL Import Flow

```
┌─────────────┐
│  User Input │
│ DTDL JSON   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│  DTDLParser             │
│  - Parse JSON           │
│  - Build model graph    │
│  - Resolve extends      │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  DTDLValidator          │
│  - Validate DTMIs       │
│  - Check structure      │
│  - Verify references    │
└──────┬──────────────────┘
       │ valid?
       ▼ (yes)
┌─────────────────────────┐
│  DTDLToFabricConverter  │
│  - Map interfaces       │
│  - Convert properties   │
│  - Handle telemetry     │
│  - Create relationships │
└──────┬──────────────────┘
       │
       ▼
       ... (same as RDF flow)
```

---

## Module Structure

```
src/
├── __init__.py
├── main.py                    # Entry point
├── constants.py               # Centralized constants
│
├── rdf/                       # RDF/OWL/TTL format support
│   ├── __init__.py            # Package exports
│   ├── rdf_converter.py       # Main RDF → Fabric converter
│   ├── preflight_validator.py # Pre-conversion validation
│   ├── fabric_to_ttl.py       # Fabric → TTL export
│   ├── rdf_parser.py          # TTL parsing with memory management
│   ├── property_extractor.py  # Class/property extraction
│   ├── type_mapper.py         # XSD → Fabric type mapping
│   ├── uri_utils.py           # URI resolution
│   ├── class_resolver.py      # OWL class handling
│   └── fabric_serializer.py   # JSON serialization
│
├── dtdl/                      # DTDL v2/v3/v4 format support
│   ├── __init__.py            # Package exports
│   ├── cli.py                 # DTDL-specific commands
│   ├── dtdl_parser.py         # Parse DTDL JSON
│   ├── dtdl_validator.py      # Validate DTDL structure
│   ├── dtdl_converter.py      # DTDL → Fabric conversion
│   ├── dtdl_models.py         # DTDL data structures
│   └── dtdl_type_mapper.py    # DTDL type mapping
│
├── core/                      # Shared infrastructure
│   ├── __init__.py            # Package exports
│   ├── fabric_client.py       # Fabric API client
│   ├── rate_limiter.py        # Token bucket rate limiting
│   ├── circuit_breaker.py     # Fault tolerance
│   ├── cancellation.py        # Graceful shutdown
│   ├── memory.py              # Memory management
│   ├── streaming.py           # Memory-efficient processing
│   ├── validators.py          # Input validation, SSRF protection
│   ├── compliance.py          # DTDL/RDF compliance validation
│   ├── plugins.py             # Plugin architecture for custom converters
│   ├── auth.py                # Azure authentication helpers
│   ├── http_client.py         # HTTP utilities
│   └── lro_handler.py         # Long-running operation handling
│
├── models/                    # Shared data models
│   ├── __init__.py
│   ├── base.py                # Abstract converter interface
│   ├── fabric_types.py        # EntityType, RelationshipType
│   └── conversion.py          # ConversionResult, ValidationResult
│
└── cli/                       # Command-line interface
    ├── commands/              # Modular command implementations
    │   ├── base.py            # BaseCommand ABC
    │   ├── common.py          # List, Get, Delete, Test, Compare
    │   ├── rdf.py             # RDF commands with batch support
    │   └── dtdl.py            # DTDL commands
    ├── helpers.py             # CLI utilities
    └── parsers.py             # Argument parsing
```

### Recommended Import Patterns

**Format-based imports:**
```python
# RDF format
from rdf import RDFToFabricConverter, PreflightValidator, parse_ttl_content

# DTDL format  
from dtdl import DTDLParser, DTDLValidator

# Core infrastructure
from core import FabricConfig, FabricOntologyClient, CircuitBreaker, CancellationToken
```

**Package-level imports:**
```python
from src import RDFToFabricConverter
from src.rdf import parse_ttl_content
from src.core import FabricConfig
```

---

## Design Patterns

### 1. Command Pattern (CLI)

Each CLI command is implemented as a separate function with consistent signature:

```python
def upload_command(args: argparse.Namespace) -> int:
    """Upload ontology to Fabric."""
    # Implementation
    return ExitCode.SUCCESS  # or ExitCode.ERROR
```

**Benefits:**
- Easy to add new commands
- Testable in isolation
- Consistent error handling

### 2. Strategy Pattern (Converters)

Multiple converters implementing the same interface:

```python
class BaseConverter(ABC):
    @abstractmethod
    def convert_file(self, path: Path) -> ConversionResult:
        pass

class RdfConverter(BaseConverter):
    def convert_file(self, path: Path) -> ConversionResult:
        # RDF-specific implementation
        pass

class DtdlConverter(BaseConverter):
    def convert_file(self, path: Path) -> ConversionResult:
        # DTDL-specific implementation
        pass
```

### 3. Circuit Breaker Pattern (Resilience)

Prevents cascading failures when Fabric API is unavailable:

```python
breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

try:
    result = breaker.call(client.create_ontology, name, definition)
except CircuitBreakerOpenError:
    print("Service temporarily unavailable, please retry later")
```

**States:**
- **CLOSED** - Normal operation
- **OPEN** - Blocking requests after failures
- **HALF_OPEN** - Testing if service recovered

### 4. Token Bucket (Rate Limiting)

Smooth rate limiting with burst support:

```python
limiter = TokenBucketRateLimiter(
    rate=10,      # requests per minute
    burst=15      # max burst size
)

limiter.acquire()  # Blocks if rate exceeded
make_api_call()
```

### 5. Observer Pattern (Cancellation)

Components register cleanup callbacks:

```python
token = CancellationToken()
token.register_callback(cleanup_temp_files)
token.register_callback(close_connections)

# On Ctrl+C, all callbacks execute
```

### 6. Plugin Pattern (Extensibility)

The plugin architecture allows extending the converter without modifying core code:

```python
from src.core.plugins import FormatConverter, PluginRegistry, ConversionOutput

class MyConverter(FormatConverter):
    format_name = "myformat"
    file_extensions = [".myf"]
    
    def convert(self, source, context=None, **options):
        output = ConversionOutput()
        # Convert source to Fabric format
        return output

# Register and use
PluginRegistry.register_converter(MyConverter())
converter = PluginRegistry.get_converter("myformat")
```

**Discovery mechanisms:**
- Programmatic registration
- Entry points (pip packages)
- Plugin directory scanning

---

## Extensibility

### Plugin Architecture

The converter supports a flexible plugin system for adding custom format converters, validators, and exporters without modifying core code. 

**Key Features:**
- **Format Converters** - Convert custom formats to Fabric Ontology
- **Validators** - Validate files before conversion
- **Exporters** - Export Fabric Ontology to custom formats
- **Discovery** - Automatic plugin discovery via entry points or directory scanning
- **Infrastructure Integration** - Plugins leverage rate limiting, circuit breakers, cancellation, and memory management

**Plugin Types:**

| Type | Base Class | Purpose |
|------|------------|---------|
| Converter | `FormatConverter` | Convert source format → Fabric Ontology |
| Validator | `FormatValidator` | Validate files before conversion |
| Exporter | `FormatExporter` | Export Fabric Ontology → target format |

**Quick Example:**
```python
from src.core.plugins import FormatConverter, PluginRegistry

class MyConverter(FormatConverter):
    format_name = "myformat"
    file_extensions = [".myf"]
    
    def convert(self, source, context=None, **options):
        # Implementation
        pass

# Register and use
PluginRegistry.register_converter(MyConverter())
converter = PluginRegistry.get_converter("myformat")
result = converter.convert("data.myf")
```

**For comprehensive plugin development documentation, see [PLUGIN_GUIDE.md](PLUGIN_GUIDE.md).**

### Legacy: Adding a Converter Without Plugins

### Adding Custom Type Mapping

Extend `type_mapper.py` with new XSD types:

```python
XSD_TO_FABRIC_TYPE[str(XSD.gYear)] = "String"
XSD_TO_FABRIC_TYPE[str(XSD.gMonthDay)] = "String"
```

### Adding Custom Validation Rules

Extend `PreflightValidator` or `DTDLValidator`:

```python
class CustomValidator(PreflightValidator):
    def validate_custom_rule(self, graph):
        # Custom validation logic
        pass
```

---

## Performance Considerations

### Memory Management

- **RDF Parsing:** Uses ~3.5x file size in memory
- **Large Files:** Streaming mode reduces memory footprint
- **Memory Checks:** Pre-flight validation prevents OOM crashes

### API Rate Limiting

- **Default:** 10 requests/minute
- **Configurable:** Adjust based on Fabric plan limits
- **Burst Handling:** Short spikes allowed (15 req burst)

### Circuit Breaker

- **Fail Fast:** Prevents wasting time on unavailable services
- **Auto-Recovery:** Automatic retry after timeout

---

## Error Handling Strategy

1. **Validation Errors** - Exit code 2, detailed report
2. **Network Errors** - Retry with exponential backoff
3. **Authentication Errors** - Exit code 4, clear message
4. **User Cancellation** - Exit code 7, cleanup executed
5. **Internal Errors** - Exit code 1, stack trace logged

---

## Testing Architecture

The project maintains a comprehensive test suite organized by functional area and test type.

**Test Organization:**

```
tests/
├── conftest.py                       # Pytest configuration and shared fixtures
├── run_tests.py                      # Test runner utility
│
├── test_converter.py                 # RDF conversion pipeline
├── test_dtdl.py                      # DTDL parsing and validation
├── test_resilience.py                # Fault tolerance infrastructure
├── test_fabric_client.py             # API client and streaming
├── test_validation.py                # Pre-flight checks and E2E
├── test_plugins.py                   # Plugin system
├── test_compliance.py                # Format compliance
├── test_edge_cases.py                # Edge cases
├── test_fabric_limits.py             # API constraints
├── test_ssrf_protection.py           # Security
├── test_streaming.py                 # Large file handling
├── test_validation_rate_limiting.py  # Rate limiting
│
├── fixtures/                         # Centralized test data
└── integration/                      # End-to-end workflows
```

**Test Strategy:**

| Aspect | Approach |
|--------|----------|
| **Coverage** | 627 tests passing (5 skipped), targeting 80%+ code coverage |
| **Organization** | Grouped by architectural component (converter, client, plugins) |
| **Isolation** | Pytest markers for selective execution (`unit`, `integration`, `slow`, `security`, `resilience`) |
| **Fixtures** | Centralized test data in `fixtures/` for consistency |
| **Mocking** | API responses mocked to match official Fabric documentation |

**Key Test Areas:**
- **Core Conversion** - Entity/property extraction, type mapping, relationship handling
- **Format Support** - RDF/OWL, DTDL v2/v3/v4 including new features (scaledDecimal, geospatial)
- **Resilience** - Rate limiting, circuit breakers, retry logic, graceful cancellation
- **Security** - Path validation, symlink detection, SSRF protection
- **Plugin System** - Converter registration, context integration, discovery mechanisms
- **Integration** - Complete workflows from input parsing to Fabric API upload

**For detailed testing instructions, see [TESTING.md](TESTING.md).**

---

## References

- [Microsoft Fabric Ontology API](https://learn.microsoft.com/rest/api/fabric/ontology/items)
- [DTDL v4 Specification](https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v4/DTDL.v4.md)
- [RDF 1.1 Specification](https://www.w3.org/TR/rdf11-concepts/)
- [OWL 2 Web Ontology Language](https://www.w3.org/TR/owl2-overview/)
- [rdflib Documentation](https://rdflib.readthedocs.io/)

---

**Last Updated:** January 1, 2026
