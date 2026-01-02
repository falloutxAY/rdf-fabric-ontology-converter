# RDF and DTDL to Microsoft Fabric Ontology Converter

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Convert RDF/OWL/TTL ontologies and DTDL models to Microsoft Fabric Ontology format via the [Fabric Ontology REST API](https://learn.microsoft.com/rest/api/fabric/ontology/items).

## Disclaimer

This is a **personal project** and is **not an official Microsoft product**. It is **not supported, endorsed, or maintained by Microsoft Corporation**. Use at your own risk. See [LICENSE](LICENSE) for terms.

## Features

- **RDF/TTL Import** – Convert Turtle/OWL ontologies to Fabric format
- **DTDL Import** – Convert Azure Digital Twins models (v2/v3/v4)
- **Export & Compare** – Export Fabric ontologies back to TTL for verification
- **Pre-flight Validation** – Check compatibility before upload
- **Streaming Support** – Memory-efficient processing for large files
- **Resilience** – Rate limiting, circuit breaker, and retry logic

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Common Commands](#common-commands)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Prerequisites

- Python 3.9 or higher
- Microsoft Fabric workspace with Ontology support
- Contributor role on the Fabric workspace

## Installation

```bash
# Clone the repository
git clone https://github.com/falloutxAY/rdf-fabric-ontology-converter.git
cd rdf-fabric-ontology-converter

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install with dependencies
pip install -e .
```

## Quick Start

```powershell
# 1. Configure (copy sample and edit with your Fabric workspace details)
copy config.sample.json src\config.json

# 2. Validate an RDF/TTL ontology
python src\main.py rdf-validate samples/sample_supply_chain_ontology.ttl

# 3. Upload to Fabric
python src\main.py rdf-upload samples/sample_supply_chain_ontology.ttl --name "MyOntology"

# 4. Import DTDL models
python src\main.py dtdl-upload samples/dtdl/ --recursive --ontology-name "MyDTDL"
```

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for detailed configuration options.

## Common Commands

### RDF/TTL Operations

```powershell
# Validate a TTL file before upload
python src\main.py rdf-validate <file.ttl> --verbose

# Convert TTL to Fabric JSON (without upload)
python src\main.py rdf-convert <file.ttl> --output output.json

# Upload ontology to Fabric
python src\main.py rdf-upload <file.ttl> --name "OntologyName"

# Export Fabric ontology back to TTL
python src\main.py rdf-export <ontology_id> --output exported.ttl

# List all ontologies
python src\main.py list

# Delete an ontology
python src\main.py delete <ontology_id>
```

### DTDL Operations

```powershell
# Validate DTDL models
python src\main.py dtdl-validate <path> --recursive

# Convert DTDL to Fabric JSON
python src\main.py dtdl-convert <path> --recursive --output output.json

# Upload DTDL to Fabric
python src\main.py dtdl-upload <path> --recursive --ontology-name "MyDTDL"
```

### Large File Support

```powershell
# Use streaming mode for files >100MB
python src\main.py rdf-upload <large_file.ttl> --streaming

# Force processing for files >500MB (bypass memory checks)
python src\main.py rdf-upload <huge_file.ttl> --force-memory
```

For the complete command reference, see [docs/COMMANDS.md](docs/COMMANDS.md).

## Documentation

### 📚 User Guides
- **[Configuration Guide](docs/CONFIGURATION.md)** – Detailed setup, authentication, and API configuration
- **[Commands Reference](docs/COMMANDS.md)** – Complete command-line reference
- **[DTDL Guide](docs/DTDL_GUIDE.md)** – DTDL import, mapping, and examples
- **[Mapping Limitations](docs/MAPPING_LIMITATIONS.md)** – RDF/DTDL → Fabric conversion constraints
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** – Common issues and solutions

### 🛠️ Developer Guides  
- **[API Reference](docs/API.md)** – Fabric Ontology REST API usage and examples
- **[Architecture Overview](docs/ARCHITECTURE.md)** – System design, patterns, and module structure
- **[Testing Guide](docs/TESTING.md)** – Running tests, markers, and coverage reports

### 📁 Project Structure

```
src/
├── main.py                   # CLI entry point
├── formats/                  # Format-specific packages
│   ├── rdf/                  # RDF/OWL/TTL support
│   └── dtdl/                 # DTDL v2/v3/v4 support
├── cli/                      # Command handlers & parsers
├── converters/               # Type mapping & extraction
├── core/                     # Resilience, streaming, validation
├── models/                   # Shared data models
└── dtdl/                     # DTDL modules (legacy path)
```

For detailed architecture, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### 🤝 Community
- **[Contributing Guidelines](CONTRIBUTING.md)** – Development setup and contribution process
- **[Code of Conduct](CODE_OF_CONDUCT.md)** – Community standards
- **[Security Policy](SECURITY.md)** – Reporting vulnerabilities
- **[Changelog](CHANGELOG.md)** – Version history

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style guidelines, and the pull request process.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Related Links

- [Microsoft Fabric Documentation](https://learn.microsoft.com/fabric/)
- [Fabric Ontology REST API](https://learn.microsoft.com/rest/api/fabric/ontology/items)
- [Azure Digital Twins DTDL](https://learn.microsoft.com/azure/digital-twins/concepts-models)
- [RDFLib](https://github.com/RDFLib/rdflib)
