# Architecture Overview

## High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                             │
│   validate | convert | upload | export | list | delete       │
└─────────────────────────────────┬───────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                     Format Pipelines                         │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────┐  │
│  │ RDF Pipeline  │  │ DTDL Pipeline │  │  CDM Pipeline   │  │
│  │ Parser        │  │ Parser        │  │  Parser         │  │
│  │ Validator     │  │ Validator     │  │  Validator      │  │
│  │ Converter     │  │ Converter     │  │  Converter      │  │
│  └───────────────┘  └───────────────┘  └─────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                     Shared Models                            │
│     EntityType | RelationshipType | ConversionResult         │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    Fabric Client                             │
│   Rate Limiter | Circuit Breaker | HTTP Client | LRO         │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                   Microsoft Fabric API
```

## Components

### CLI Layer (`src/app/cli/`)

User interface and command dispatch:
- `commands.py` - Command registry
- `parsers.py` - Argument parsing
- `commands/unified/` - Format-agnostic commands (split modules):
  - `validate.py` - ValidateCommand
  - `convert.py` - ConvertCommand
  - `upload.py` - UploadCommand
  - `export.py` - ExportCommand
- `commands/common.py` - list/get/delete
- `commands/base.py` - BaseCommand and protocols

### Format Pipelines (`src/formats/`)

#### RDF Pipeline (`formats/rdf/`)

| Component | File | Purpose |
|-----------|------|---------|
| Parser | `rdf_parser.py` | Parse TTL/RDF/OWL/JSON-LD via rdflib |
| Validator | `preflight_validator.py` | Check Fabric compatibility |
| Converter | `rdf_converter.py` | Map OWL classes/properties to Fabric |
| Exporter | `fabric_to_ttl.py` | Export Fabric → TTL |

#### DTDL Pipeline (`formats/dtdl/`)

| Component | File | Purpose |
|-----------|------|---------|
| Parser | `dtdl_parser.py` | Parse DTDL v2/v3/v4 JSON |
| Validator | `dtdl_validator.py` | Validate DTMI, structure |
| Converter | `dtdl_converter.py` | Map interfaces to Fabric |
| Type Mapper | `dtdl_type_mapper.py` | DTDL → Fabric type mapping |

#### CDM Pipeline (`formats/cdm/`)

| Component | File | Purpose |
|-----------|------|---------|
| Parser | `cdm_parser.py` | Parse CDM manifests and entities |
| Validator | `cdm_validator.py` | Validate CDM structure |
| Converter | `cdm_converter.py` | Map CDM entities to Fabric |
| Type Mapper | `cdm_type_mapper.py` | CDM → Fabric type mapping |
| Models | `cdm_models.py` | CDM data models |

### Shared Models (`src/shared/models/`)

| Model | Description |
|-------|-------------|
| `EntityType` | Fabric entity with properties |
| `RelationshipType` | Fabric relationship between entities |
| `ConversionResult` | Conversion output with stats |
| `ValidationResult` | Validation issues and warnings |

### Core Infrastructure (`src/core/`)

| Component | File | Purpose |
|-----------|------|---------|
| **SDK Adapter** | `platform/sdk_adapter.py` | **Bridges to fabric-ontology-sdk (recommended)** |
| Fabric Client | `fabric_client.py` | REST API with retry logic (legacy) |
| Rate Limiter | `rate_limiter.py` | Token bucket throttling |
| Circuit Breaker | `circuit_breaker.py` | Fault tolerance |
| Streaming | `streaming.py` | Large file processing |
| Pipeline | `services/pipeline.py` | Formalized streaming pipeline |
| Memory | `memory.py` | Memory safety checks |
| Schema Validator | `validators/fabric_schema.py` | Validate definitions before upload |

### SDK Integration (v0.4.0+)

The converter uses the [Unofficial-Fabric-Ontology-SDK](https://github.com/falloutxAY/Unofficial-Fabric-Ontology-SDK) as the single source of truth for:

| SDK Component | Converter Usage |
|---------------|-----------------|
| `NAME_PATTERN` | Validation in `sdk_adapter.py` (exported for consumers) |
| `PropertyDataType` | Type validation in `sdk_adapter.py` (exported for consumers) |
| `RateLimiter` | Token bucket rate limiting |
| `CircuitBreaker` | Fault tolerance for API calls |
| `fabric_ontology.testing` | Shared pytest fixtures for unit tests |

**Key Exports from sdk_adapter.py:**
```python
from src.core.platform.sdk_adapter import (
    NAME_PATTERN,           # r"^[a-zA-Z][a-zA-Z0-9_-]{0,25}$"
    PropertyDataType,       # BIGINT, STRING, DOUBLE, FLOAT, BOOLEAN, DATETIME, OBJECT
)
```

### Plugin System (`src/plugins/`)

Extensible architecture for custom formats:
- `base.py` - `OntologyPlugin` abstract base
- `manager.py` - Plugin discovery/registration
- `builtin/` - RDF and DTDL plugins

## Data Flow

### Upload Flow

```
Input File → Validate → Parse → Convert → Fabric Client → API
                ↓          ↓        ↓
           Warnings   Graph/AST  EntityTypes
                              RelationshipTypes
```

### Key Design Patterns

| Pattern | Usage |
|---------|-------|
| Pipeline | Sequential validation → parsing → conversion |
| Strategy | Pluggable format handlers |
| Circuit Breaker | Protect against API failures |
| Token Bucket | Rate limiting |

## Module Structure

```
src/
├── main.py              # Entry point
├── app/cli/             # CLI layer
│   └── commands/        # Command implementations
│       ├── unified/     # Format-agnostic commands
│       ├── base.py      # Base command class
│       └── common.py    # Workspace commands
├── formats/             # Format pipelines
│   ├── rdf/             # RDF/OWL/JSON-LD
│   ├── dtdl/            # DTDL v2/v3/v4
│   └── cdm/             # CDM manifests/entities
├── shared/              # Shared code
│   ├── models/          # Data models
│   └── utilities/       # Helpers
├── core/                # Infrastructure
│   ├── platform/        # SDK adapter layer
│   │   └── sdk_adapter.py  # Bridges to fabric-ontology-sdk
│   └── validators/      # Input validation
└── plugins/             # Plugin system
    └── builtin/         # Built-in plugins
```

## See Also

- [API Reference](API.md) - Programmatic usage
- [Plugin Guide](PLUGIN_GUIDE.md) - Creating plugins
