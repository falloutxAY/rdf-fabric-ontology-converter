# RDF to Microsoft Fabric Ontology Converter

Convert RDF TTL (Turtle) ontology files to Microsoft Fabric Ontology format and upload them via the Fabric REST API. Also supports exporting Fabric ontologies back to TTL format with round-trip verification.

## Disclaimer

This is a **personal project** and is **not an official Microsoft product**. It is not supported, endorsed, or maintained by Microsoft Corporation. The views and implementations here are my own and do not represent Microsoft's positions or recommendations.

This tool was created as part of my personal learning with AI-assisted development. There may be errors, and outputs may not be complete or correct for all ontologies. **Use at your own risk.**

Please refer to the [LICENSE](LICENSE) file for full terms.

## Features

- Bidirectional conversion: RDF TTL → Fabric and Fabric → RDF TTL
- Pre-flight validation: Check TTL files for Fabric compatibility before import
- List, get, and delete ontologies
- Round-trip testing with semantic comparison

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Examples](#examples)
- [Limitations](#Limitations)
- [Documentation](#documentation)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [License](#license)

## Prerequisites

- Python 3.9 or higher
- Microsoft Fabric workspace with Ontology support
- Contributor role on the Fabric workspace

## Installation

1. Clone the repository:
```bash
git clone https://github.com/falloutxAY/rdf-fabric-ontology-converter.git
cd rdf-fabric-ontology-converter
```

2. Create and activate a virtual environment:
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure your settings:
```bash
# Copy the sample configuration into src (config.json is git-ignored)
cp config.sample.json src/config.json

# Edit src/config.json with your Fabric workspace details
```

## Configuration

Create `src/config.json` from `config.sample.json` (config.json is git-ignored):

```json
{
  "fabric": {
    "workspace_id": "YOUR_WORKSPACE_ID",
    "tenant_id": "YOUR_TENANT_ID",
    "client_id": "",
    "use_interactive_auth": "true",
    "api_base_url": "https://api.fabric.microsoft.com/v1"
  },
  "ontology": {
    "default_namespace": "usertypes",
    "id_prefix": 1000000000000
  },
  "logging": {
    "level": "INFO",
    "file": "logs/app.log"
  }
}
```

For detailed configuration options, see [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Quick Start

```powershell
# Validate a TTL file if it can be seamlessly imported into Fabric Ontology
python src/main.py validate samples\sample_ontology.ttl --verbose

# Convert a TTL file to Fabric format
python src/main.py convert samples\sample_ontology.ttl --config src\config.json

# Upload an ontology to Fabric (with pre-flight validation)
python src/main.py upload samples\sample_ontology.ttl --name "MyOntology" --config src\config.json

# List all ontologies in your workspace
python src/main.py list --config src\config.json

# Run tests
python -m pytest -q
```

## Usage

### Validate TTL File (Pre-flight Check)
```powershell
# Check if a TTL file can be imported seamlessly
python src/main.py validate <ttl_file> [--verbose] [--save-report]

# Save detailed validation report to JSON
python src/main.py validate <ttl_file> --output validation_report.json
```
You can try this for samples/foaf_ontology.ttl

### Convert TTL to JSON
```powershell
python src/main.py convert <ttl_file> [--output <output.json>] --config src\config.json

# For very large files (>500MB), bypass memory safety checks
python src/main.py convert <ttl_file> --force-memory
```

### Upload Ontology
```powershell
# Upload with pre-flight validation (default)
python src/main.py upload <ttl_file> [--name <ontology_name>] [--update] --config src\config.json

# Skip validation and upload directly
python src/main.py upload <ttl_file> --skip-validation --config src\config.json

# Force upload even if validation issues are found
python src/main.py upload <ttl_file> --force --config src\config.json

# For very large files, bypass memory safety checks (use with caution)
python src/main.py upload <ttl_file> --force-memory --config src\config.json
```

### Export Ontology to TTL
```powershell
python src/main.py export <ontology_id> [--output <output.ttl>] --config src\config.json
```

### Compare Two TTL Files
```powershell
python src/main.py compare <ttl_file1> <ttl_file2> [--verbose]
```

### Round-Trip Test
```powershell
# Offline test (TTL -> JSON -> TTL)
python src/main.py roundtrip <ttl_file> --save-export

# Full test with Fabric upload
python src/main.py roundtrip <ttl_file> --upload --cleanup --config src\config.json
```

### List Ontologies
```powershell
python src/main.py list --config src\config.json
```

### Get Ontology Details
```powershell
python src/main.py get <ontology_id> --config src\config.json
```

### Delete Ontology
```powershell
python src/main.py delete <ontology_id> --config src\config.json
```

### Test Connection
```powershell
python src/main.py test --config src\config.json
```

## Examples

### Example 1: Validate Before Import
```bash
# Check if a TTL file can be imported seamlessly
python src/main.py validate samples/foaf_ontology.ttl --verbose
```

### Example 2: Manufacturing Ontology
```bash
python src/main.py upload samples/sample_ontology.ttl --name "ManufacturingOntology" --config src/config.json
```

### Example 3: FOAF Vocabulary
```bash
python src/main.py upload samples/foaf_ontology.ttl --name "FOAF" --config src/config.json
```

### Example 4: Convert Only (No Upload)
```bash
python src/main.py convert samples/sample_iot_ontology.ttl --output iot_definition.json
```

### Example 5: Export from Fabric
```bash
python src/main.py export abc123-def456 --output my_ontology.ttl --config src/config.json
```

### Example 6: Compare Two Ontologies
```bash
python src/main.py compare original.ttl exported.ttl --verbose
```

### Example 7: Round-Trip Verification
```bash
# Test that TTL -> Fabric Ontology -> TTL preserves semantics
python src/main.py roundtrip samples/sample_ontology.ttl --save-export
```

## Limitations

**Conversions are not 1:1**: RDF/OWL is highly expressive with features like complex class expressions, property restrictions, and inference-driven semantics that cannot be fully represented in Microsoft Fabric Ontology's business-friendly model.

### Pre-flight Validation

Use the **validate** command to check if your TTL file can be imported seamlessly:

```bash
python src/main.py validate samples/foaf_ontology.ttl --verbose
```

### Strict Semantics

This tool adheres to strict semantics by default:
- Properties require explicit `rdfs:domain` and `rdfs:range` declarations
- Referenced classes must be declared locally in the TTL file
- Complex OWL constructs (restrictions, property characteristics) are flagged but not preserved
- `owl:unionOf`, `owl:intersectionOf`, and `owl:complementOf` are supported for domain/range with:
  - Recursive resolution of nested blank nodes
  - Cycle detection to prevent infinite loops
  - Depth limiting for protection against deeply nested structures

For complete details, see:
- **[Mapping Limitations](docs/MAPPING_LIMITATIONS.md)** - Why TTL → Fabric is not perfectly lossless


## Documentation

- **[Configuration Guide](docs/CONFIGURATION.md)** - Detailed setup instructions
- **[Testing Guide](docs/TESTING.md)** - Comprehensive testing documentation
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Mapping Challenges and Limitations](docs/MAPPING_LIMITATIONS.md)** - Why TTL → Fabric is not perfectly lossless

 
## Testing

Run the comprehensive test suite:

```bash
# Run all tests
python tests/run_tests.py all

# Run unit tests only
python tests/run_tests.py core

# Run sample file tests
python tests/run_tests.py samples

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

For more details, see [docs/TESTING.md](docs/TESTING.md).

## 📁 Project Structure

```
rdf-fabric-ontology-converter/
├── src/                          # Source code
│   ├── __init__.py
│   ├── main.py                   # CLI entry point
│   ├── rdf_converter.py          # RDF parsing & TTL→Fabric conversion
│   ├── fabric_to_ttl.py          # Fabric→TTL export & comparison
│   ├── fabric_client.py          # Fabric API client with retry logic
│   └── preflight_validator.py    # Pre-flight validation for Fabric compatibility
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_converter.py         # Converter unit tests (29 tests)
│   ├── test_exporter.py          # Exporter unit tests (21 tests)
│   ├── test_integration.py       # Integration tests (15 tests)
│   ├── test_preflight_validator.py # Pre-flight validation tests (34 tests)
│   └── run_tests.py              # Test runner
├── samples/                      # Sample ontology files
│   ├── sample_ontology.ttl       # Manufacturing example
│   ├── foaf_ontology.ttl         # FOAF vocabulary
│   ├── sample_iot_ontology.ttl   # IoT devices
│   └── sample_fibo_ontology.ttl  # Financial ontology
├── docs/                         # Documentation
│   ├── CONFIGURATION.md          # Configuration guide
│   ├── TESTING.md                # Comprehensive testing guide
│   ├── TROUBLESHOOTING.md        # Common issues
│   └── MAPPING_LIMITATIONS.md    # Mapping limitations
├── config.sample.json            # Sample configuration
├── src/config.json               # Your local config (git-ignored)
├── requirements.txt              # Python dependencies
├── .gitignore                    # Git ignore rules
├── LICENSE                       # MIT License
└── README.md                     # This file
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


## Related Links

- [Microsoft Fabric Documentation](https://learn.microsoft.com/fabric/)
- [RDFLib](https://github.com/RDFLib/rdflib) for RDF parsing support
- Sample vocabularies: [FOAF](http://xmlns.com/foaf/spec/) and [FIBO](https://spec.edmcouncil.org/fibo/)

---
