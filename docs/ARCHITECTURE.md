# Architecture Overview

## High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                             │
│   validate | convert | upload | export | list | delete       │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                     Format Pipelines                         │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │    RDF Pipeline     │    │      DTDL Pipeline          │ │
│  │  Parser → Validator │    │  Parser → Validator         │ │
│  │      → Converter    │    │      → Converter            │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
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
| Fabric Client | `fabric_client.py` | REST API with retry logic |
| Rate Limiter | `rate_limiter.py` | Token bucket throttling |
| Circuit Breaker | `circuit_breaker.py` | Fault tolerance |
| Streaming | `streaming.py` | Large file processing |
| Pipeline | `services/pipeline.py` | Formalized streaming pipeline |
| Memory | `memory.py` | Memory safety checks |

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
│   └── dtdl/            # DTDL v2/v3/v4
├── shared/              # Shared code
│   ├── models/          # Data models
│   └── utilities/       # Helpers
├── core/                # Infrastructure
│   └── validators/      # Input validation
└── plugins/             # Plugin system
    └── builtin/         # Built-in plugins
```

## See Also

- [API Reference](API.md) - Programmatic usage
- [Plugin Guide](PLUGIN_GUIDE.md) - Creating plugins
