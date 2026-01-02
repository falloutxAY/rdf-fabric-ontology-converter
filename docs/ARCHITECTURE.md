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
- `commands.py` - Command implementations (1382 lines, consider splitting)
- `helpers.py` - Utility functions for CLI operations
- `parsers.py` - Argument parsing and validation

**Key Features:**
- Command pattern for extensibility
- Consistent error handling and exit codes
- Progress indicators for long-running operations
- Graceful cancellation support (Ctrl+C)

### 2. Converter Layer

#### 2.1 RDF Pipeline (`src/`)

**PreflightValidator** (`preflight_validator.py`)
- Scans TTL files before conversion
- Detects unsupported OWL constructs (restrictions, property chains)
- Validates file size and estimates memory requirements
- Generates detailed validation reports

**RDFToFabricConverter** (`rdf_converter.py`)
- Uses `rdflib` for RDF graph parsing
- Handles OWL/RDFS constructs:
  - `owl:Class` → EntityType
  - `owl:DatatypeProperty` → EntityTypeProperty
  - `owl:ObjectProperty` → RelationshipType
  - `rdfs:subClassOf` → inheritance
- Type mapping via `converters/type_mapper.py`
- URI resolution via `converters/uri_utils.py`

**FabricToTTLExporter** (`fabric_to_ttl.py`)
- Reverse conversion: Fabric → TTL
- Preserves class hierarchy
- Generates valid RDF/OWL syntax

#### 2.2 DTDL Pipeline (`src/dtdl/`)

**DTDLParser** (`dtdl_parser.py`)
- Parses DTDL v4 JSON files
- Supports all DTDL primitive types
- Handles complex schemas (Array, Enum, Map, Object)
- Resolves `extends` inheritance (max 12 levels)

**DTDLValidator** (`dtdl_validator.py`)
- Validates DTMI format
- Checks interface structure
- Verifies relationship targets
- Validates semantic types and units

**DTDLToFabricConverter** (`dtdl_converter.py`)
- Maps DTDL interfaces to EntityType
- Converts properties and telemetry
- Handles relationships with cardinality
- Flattens components to properties

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

### 5. Fabric Client (`fabric_client.py`)

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
├── models/                    # Shared data models
│   ├── __init__.py
│   ├── base.py                # Abstract converter interface
│   ├── fabric_types.py        # EntityType, RelationshipType
│   └── conversion.py          # ConversionResult, ValidationResult
│
├── core/                      # Cross-cutting concerns
│   ├── __init__.py
│   ├── rate_limiter.py        # Token bucket rate limiting
│   ├── circuit_breaker.py     # Fault tolerance
│   ├── cancellation.py        # Graceful shutdown
│   └── memory.py              # Memory management
│
├── converters/                # RDF conversion utilities
│   ├── type_mapper.py         # XSD → Fabric type mapping
│   ├── uri_utils.py           # URI resolution
│   ├── class_resolver.py      # OWL class handling
│   └── fabric_serializer.py   # JSON serialization
│
├── dtdl/                      # DTDL support
│   ├── cli.py                 # DTDL-specific commands
│   ├── dtdl_parser.py         # Parse DTDL JSON
│   ├── dtdl_validator.py      # Validate DTDL structure
│   ├── dtdl_converter.py      # DTDL → Fabric conversion
│   ├── dtdl_models.py         # DTDL data structures
│   └── dtdl_type_mapper.py    # DTDL type mapping
│
├── cli/                       # Command-line interface
│   ├── commands.py            # Command implementations
│   ├── helpers.py             # CLI utilities
│   └── parsers.py             # Argument parsing
│
├── rdf_converter.py           # RDF → Fabric converter (2514 lines)
├── fabric_client.py           # Fabric API client (1324 lines)
├── preflight_validator.py     # Pre-conversion validation
└── fabric_to_ttl.py           # Fabric → RDF export
```

**Note:** Large files (`rdf_converter.py`, `fabric_client.py`, `cli/commands.py`) are candidates for future refactoring.

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

---

## Extensibility

### Adding a New Format Converter

1. **Create converter module:**
   ```python
   # src/formats/newformat/converter.py
   from src.models.base import BaseConverter
   from src.models.conversion import ConversionResult
   
   class NewFormatConverter(BaseConverter):
       @property
       def supported_extensions(self) -> List[str]:
           return ['.newext']
       
       def convert_file(self, path: Path) -> ConversionResult:
           # Implementation
           pass
   ```

2. **Add CLI commands:**
   ```python
   # src/cli/commands.py
   def newformat_import_command(args):
       converter = NewFormatConverter()
       result = converter.convert_file(args.file)
       # Upload to Fabric
   ```

3. **Register command:**
   ```python
   # src/cli/parsers.py
   parser.add_parser('newformat-import', ...)
   ```

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

```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_type_mapper.py
│   ├── test_uri_utils.py
│   └── ...
│
├── integration/             # End-to-end workflows
│   ├── test_rdf_pipeline.py
│   ├── test_dtdl_pipeline.py
│   └── test_cross_format.py
│
└── fixtures/                # Test data
    ├── sample_ontologies/
    └── mock_responses/
```

**Coverage:** 354 tests passing, targeting 80%+ coverage

---

## Future Architecture Improvements

### Planned Refactoring

1. **Split Large Files**
   - `rdf_converter.py` (2514 lines) → parser, processor, output modules
   - `cli/commands.py` (1382 lines) → separate command files

2. **Reorganize into `formats/` Structure**
   ```
   src/formats/
   ├── rdf/
   │   ├── converter.py
   │   ├── validator.py
   │   └── exporter.py
   └── dtdl/
       ├── converter.py
       └── validator.py
   ```

3. **Plugin Architecture**
   - Allow third-party format converters
   - Dynamic command registration
   - Custom validation rules

---

## References

- [Microsoft Fabric Ontology API](https://learn.microsoft.com/rest/api/fabric/ontology/items)
- [DTDL v4 Specification](https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v4/DTDL.v4.md)
- [RDF 1.1 Specification](https://www.w3.org/TR/rdf11-concepts/)
- [OWL 2 Web Ontology Language](https://www.w3.org/TR/owl2-overview/)
- [rdflib Documentation](https://rdflib.readthedocs.io/)

---

**Last Updated:** January 1, 2026
