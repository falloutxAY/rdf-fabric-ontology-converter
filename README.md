# RDF to Microsoft Fabric Ontology Converter

Convert RDF TTL (Turtle) ontology files to Microsoft Fabric Ontology format and upload them via the Fabric REST API. Also supports exporting Fabric ontologies back to TTL format with round-trip verification.

## Disclaimer

This repository was created as part of my personal learning and experimenting with AI‑assisted software development (Actually AI did 99.9% of the work). There may be mistakes or omissions, and the outputs may not be complete or correct for all ontologies.

Please refer to the `LICENSE` file for the full terms governing use, distribution, and limitations.

## ✨ Features

- 🔄 **Bidirectional conversion**: RDF TTL → Fabric and Fabric → RDF TTL
- 🔍 List, get, and delete ontologies
- 🔁 Round-trip testing with semantic comparison
- 🎯 Automatic XSD to Fabric type mapping
- ✅ Comprehensive test suite (65 tests) 

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Examples](#examples)
- [Strict Semantics and FOAF Considerations](#strict-semantics-and-foaf-considerations)
- [FAQ](#faq)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## 🔧 Prerequisites

- Python 3.9 or higher
- Microsoft Fabric workspace with Ontology support
- Contributor role on the Fabric workspace

## 📦 Installation

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

## 🚀 Quick Start

```powershell
# Convert a TTL file to Fabric format
python src/main.py convert samples\sample_ontology.ttl --config src\config.json

# Upload an ontology to Fabric
python src/main.py upload samples\sample_ontology.ttl --name "MyOntology" --config src\config.json

# List all ontologies in your workspace
python src/main.py list --config src\config.json

# Run tests
python -m pytest -q
```

## 📖 Usage

### Convert TTL to JSON
```powershell
python src/main.py convert <ttl_file> [--output <output.json>] --config src\config.json
```

### Upload Ontology
```powershell
python src/main.py upload <ttl_file> [--name <ontology_name>] [--update] --config src\config.json
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

## ⚙️ Configuration

Create `src/config.json` from `config.sample.json` (config.json is git-ignored):

```json
{
  "fabric": {
    "workspace_id": "YOUR_WORKSPACE_ID",
    "tenant_id": "YOUR_TENANT_ID",
    "client_id": "04b07795-8ddb-461a-bbee-02f9e1bf7b46",
    "use_interactive_auth": true,
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

## 🧪 Testing

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

**Test Results:** ✅ 

For more details, see [docs/TESTING.md](docs/TESTING.md).

## 📁 Project Structure

```
rdf-fabric-ontology-converter/
├── src/                          # Source code
│   ├── __init__.py
│   ├── main.py                   # CLI entry point
│   ├── rdf_converter.py          # RDF parsing & TTL→Fabric conversion
│   ├── fabric_to_ttl.py          # Fabric→TTL export & comparison
│   └── fabric_client.py          # Fabric API client with retry logic
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_converter.py         # Converter unit tests (29 tests)
│   ├── test_exporter.py          # Exporter unit tests (21 tests)
│   ├── test_integration.py       # Integration tests (15 tests)
│   └── run_tests.py              # Test runner
├── samples/                      # Sample ontology files
│   ├── sample_ontology.ttl       # Manufacturing example
│   ├── foaf_ontology.ttl         # FOAF vocabulary
│   ├── sample_iot_ontology.ttl   # IoT devices
│   └── sample_fibo_ontology.ttl  # Financial ontology
├── docs/                         # Documentation
│   ├── CONFIGURATION.md          # Configuration guide
│   ├── TESTING.md                # Combined testing guide
│   ├── TROUBLESHOOTING.md        # Common issues
│   ├── ERROR_HANDLING_SUMMARY.md # Error handling reference
│   └── QUICK_TEST_GUIDE.md       # Quick test instructions
├── config.sample.json            # Sample configuration
├── src/config.json               # Your local config (git-ignored)
├── requirements.txt              # Python dependencies
├── .gitignore                    # Git ignore rules
├── LICENSE                       # MIT License
└── README.md                     # This file
```

## 💡 Examples

### Example 1: Manufacturing Ontology
```bash
python main.py upload samples/sample_ontology.ttl --name "ManufacturingOntology"
```

### Example 2: FOAF Vocabulary
```bash
python main.py upload samples/foaf_ontology.ttl --name "FOAF"
```

### Example 3: Convert Only (No Upload)
```bash
python main.py convert samples/sample_iot_ontology.ttl --output iot_definition.json
```

### Example 4: Export from Fabric
```bash
python main.py export abc123-def456 --output my_ontology.ttl
```

### Example 5: Compare Two Ontologies
```bash
python main.py compare original.ttl exported.ttl --verbose
```

### Example 6: Round-Trip Verification
```bash
# Test that TTL -> Fabric -> TTL preserves semantics
python main.py roundtrip samples/sample_ontology.ttl --save-export
```

For more examples, see [docs/QUICK_TEST_GUIDE.md](docs/QUICK_TEST_GUIDE.md).

## Limitations
**Conversions are not 1:1**: for more details, see `docs/MAPPING_LIMIRATIONS.md`.

This tool adheres to strict semantics by default, ensuring predictable conversion aligned with RDF/OWL declarations:

- Properties and relationships are generated only when `rdfs:domain` and `rdfs:range` resolve to declared classes in the input TTL.
- Blank‑node class expressions using `owl:unionOf` are supported: each domain–range pair yields a distinct relationship type in the Fabric definition.
- Properties without explicit, resolvable `rdfs:domain`/`rdfs:range` are skipped with clear warnings; no heuristic attachment is performed.
- Expanded XSD mappings are included for common datatypes (e.g., `xsd:anyURI` → String, `xsd:dateTimeStamp` → DateTime, `xsd:time` → String).

FOAF and similar vocabularies sometimes rely on property signatures that are not explicitly declared in a single TTL file or reference external class definitions. Under strict semantics:

- If a property lacks explicit `rdfs:domain`/`rdfs:range` in the TTL (or references classes not declared locally), it will be skipped.
- To achieve round‑trip equivalence for FOAF:
  - Include explicit `rdfs:domain` and `rdfs:range` for the properties you want preserved.
  - Ensure referenced classes are declared within the same TTL (or merge the needed vocabularies).
  - Avoid complex OWL constructs not currently supported (e.g., certain `owl:Restriction` patterns) or extend support in future iterations.

An optional "loose inference" mode is planned as a future feature to heuristically attach properties when signatures are missing. It is intentionally disabled by default to maintain predictable, standards‑aligned behavior.

For more details, see `docs/ERROR_HANDLING_SUMMARY.md`.


## 📚 Documentation

- **[Configuration Guide](docs/CONFIGURATION.md)** - Detailed setup instructions
- **[Testing Guide](docs/TESTING.md)** - How to run and write tests
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Quick Test Guide](docs/QUICK_TEST_GUIDE.md)** - Fast test commands
- **[Error Handling Summary](docs/ERROR_HANDLING_SUMMARY.md)** - Common failures and resolutions
 - **[Mapping Challenges and Non‑1:1 Scenarios](docs/MAPPING_LIMITATIONS.md)** - Why TTL → Fabric is not perfectly lossless

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure:
- All tests pass (`python run_tests.py all`)
- Code follows Python best practices
- New features include tests
- Documentation is updated


## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.



## 🙏 Acknowledgments

- Microsoft Fabric documentation and ecosystem
- [RDFLib](https://github.com/RDFLib/rdflib) for RDF parsing support
- Sample vocabularies: [FOAF](http://xmlns.com/foaf/spec/) and [FIBO](https://spec.edmcouncil.org/fibo/)

## 📧 Support

For issues and questions:
- 🐛 [Report a bug](https://github.com/falloutxAY/rdf-fabric-ontology-converter/issues)
- 💡 [Request a feature](https://github.com/falloutxAY/rdf-fabric-ontology-converter/issues)
- 📖 [Read the docs](docs/)

## 🔗 Related Projects

- [Microsoft Fabric Documentation](https://learn.microsoft.com/fabric/)
- [RDFLib](https://github.com/RDFLib/rdflib)
---

**Made with ❤️ for the Fabric community**
