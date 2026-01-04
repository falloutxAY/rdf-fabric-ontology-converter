# RDF & DTDL to Microsoft Fabric Ontology Converter

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Convert RDF/OWL and DTDL ontologies to Microsoft Fabric Ontology format via the [Fabric Ontology REST API](https://learn.microsoft.com/rest/api/fabric/ontology/items).

> ⚠️ **Disclaimer:** This is a personal project, **not an official Microsoft product**. Use at your own risk. See [LICENSE](LICENSE).

## Features

| Feature | Description |
|---------|-------------|
| **RDF Import** | Turtle, RDF/XML, N-Triples, N-Quads, TriG, N3, JSON-LD |
| **DTDL Import** | Azure Digital Twins models (v2/v3/v4) |
| **Validation** | Pre-flight compatibility checks before upload |
| **Export** | Export Fabric ontologies back to TTL |
| **Streaming** | Memory-efficient processing for large files |
| **Extensible** | Plugin system for custom formats |

## Quick Start

```powershell
# 1. Setup
git clone https://github.com/falloutxAY/rdf-fabric-ontology-converter.git
cd rdf-fabric-ontology-converter
python -m venv .venv && .venv\Scripts\activate
pip install -e .

# 2. Configure (edit with your Fabric workspace details)
copy config.sample.json src\config.json

# 3. Validate & Upload
python -m src.main validate --format rdf samples/rdf/sample_supply_chain_ontology.ttl
python -m src.main upload --format rdf samples/rdf/sample_supply_chain_ontology.ttl
```

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `validate` | Check Fabric compatibility | `python -m src.main validate --format rdf ontology.ttl` |
| `convert` | Convert to Fabric JSON | `python -m src.main convert --format dtdl models/` |
| `upload` | Upload to Fabric | `python -m src.main upload --format rdf ontology.ttl` |
| `export` | Export to TTL (RDF only) | `python -m src.main export <ontology-id>` |
| `list` | List workspace ontologies | `python -m src.main list` |
| `delete` | Delete an ontology | `python -m src.main delete <ontology-id>` |

## Documentation

| Guide | Description |
|-------|-------------|
| [Configuration](docs/CONFIGURATION.md) | Setup, authentication, API settings |
| [CLI Reference](docs/CLI_COMMANDS.md) | Complete command-line options |
| [RDF Guide](docs/RDF_GUIDE.md) | RDF/OWL mapping & limitations |
| [DTDL Guide](docs/DTDL_GUIDE.md) | DTDL mapping & limitations |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues & solutions |
| [Architecture](docs/ARCHITECTURE.md) | System design & module structure |
| [API Reference](docs/API.md) | Programmatic usage |
| [Testing](docs/TESTING.md) | Running tests |
| [Plugin Guide](docs/PLUGIN_GUIDE.md) | Creating custom plugins |

## Prerequisites

- Python 3.9+
- Microsoft Fabric workspace with Ontology support
- Contributor role on the workspace

## Project Structure

```
src/
├── main.py              # CLI entry point
├── app/cli/             # Command implementations
├── formats/             # RDF & DTDL converters
│   ├── rdf/             # RDF converter, validator, exporter
│   └── dtdl/            # DTDL parser, validator, converter
├── core/                # Fabric client, rate limiter, circuit breaker
├── shared/models/       # EntityType, RelationshipType, ConversionResult
└── plugins/             # Plugin system

tests/                   # Test suites
samples/                 # Sample ontologies (rdf/, dtdl/, jsonld/)
docs/                    # Documentation
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines.

## License

MIT License - see [LICENSE](LICENSE)

## Links

- [Microsoft Fabric Docs](https://learn.microsoft.com/fabric/)
- [Fabric Ontology API](https://learn.microsoft.com/rest/api/fabric/ontology/items)
- [RDFLib](https://github.com/RDFLib/rdflib)
