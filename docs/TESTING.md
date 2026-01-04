# Testing

## Table of Contents

- [🚀 Quick Start](#-quick-start)
- [📋 Test Files (consolidated)](#-test-files-consolidated)
  - [Pytest markers](#pytest-markers)
- [Running tests](#running-tests)
  - [Quick Commands](#quick-commands)
  - [Examples](#examples)
  - [Specific tests](#specific-tests)
- [✨ Sample output](#-sample-output)
- [What the tests cover](#what-the-tests-cover)
  - [DTDL v4 Test Coverage](#dtdl-v4-test-coverage)
- [Adding new tests](#adding-new-tests)
  - [Example: Unit test](#example-unit-test)
  - [Example: Integration test with mocked API](#example-integration-test-with-mocked-api)
- [Troubleshooting](#troubleshooting)
  - [Import errors](#import-errors)
  - [Tests run slowly](#tests-run-slowly)
- [Dependencies](#dependencies)
- [💡 Best practices](#-best-practices)
- [📚 API documentation](#-api-documentation)

## 🚀 Quick Start

```powershell
# Run all tests (~367 tests)
python -m pytest tests/ -v

# Or use the test runner
python tests/run_tests.py all

# Run by category using markers
pytest -m unit           # Fast unit tests
pytest -m integration    # Integration tests
pytest -m samples        # Sample file tests
pytest -m resilience     # Rate limiter, circuit breaker, cancellation
pytest -m security       # Security-related tests
pytest -m slow           # Long-running tests

> ℹ️  JSON-LD inputs do not have a standalone plugin anymore. Use the `rdf`
> format (which auto-detects `.jsonld`) when writing or running tests against
> JSON-LD samples.
```

## 📋 Test Files (consolidated)

| File | Purpose | Est. Tests |
|------|----------|------------|
| `test_converter.py` | Core RDF conversion, type mapping | ~90 |
| `test_dtdl.py` | DTDL parsing, validation, conversion, v4 features | ~31 |
| `test_resilience.py` | Rate limiter, circuit breaker, cancellation | ~107 |
| `test_fabric_client.py` | Fabric API client, streaming converter | ~62 |
| `test_validation.py` | Pre-flight validation, exporter, E2E | ~74 |
| `conftest.py` | Shared fixtures and pytest markers | - |
| `run_tests.py` | Test runner utility | - |
| `fixtures/` | Centralized test fixtures | - |
| `fixtures/ttl_fixtures.py` | RDF/TTL sample content | - |
| `fixtures/dtdl_fixtures.py` | DTDL JSON samples | - |
| `fixtures/config_fixtures.py` | Configuration samples | - |

> **Note:** The former `tests/cli` and `tests/models` packages were consolidated into the
> format and core suites to avoid shadowing `src.cli` and `src.models`. CLI-facing behavior
> is covered alongside the Fabric client and converter tests listed above.

### Pytest markers

Configure in `conftest.py`:
- `@pytest.mark.unit` - Fast unit tests (default)
- `@pytest.mark.integration` - Tests with external dependencies
- `@pytest.mark.slow` - Long-running tests (>5s)
- `@pytest.mark.security` - Security/path validation tests
- `@pytest.mark.resilience` - Fault tolerance tests
- `@pytest.mark.samples` - Tests using sample files

## Running tests

### Quick Commands
```powershell
# Run all tests
python -m pytest tests/ -v

# Run by marker
pytest -m unit -v                    # Unit tests only
pytest -m "integration and samples"  # Combined markers
pytest -m "not slow"                 # Exclude slow tests

# Run specific test file
pytest tests/rdf/test_converter.py -v
pytest tests/core/test_resilience.py -v
pytest tests/core/test_fabric_client.py -v
pytest tests/rdf/test_validation.py -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

### Examples
```powershell
# Core converter tests
python -m pytest tests/rdf/test_converter.py::TestRDFConverter -v

# Sample file tests
pytest -m samples -v

# Rate limiter tests
pytest tests/core/test_resilience.py::TestTokenBucketRateLimiter -v

# Circuit breaker tests  
pytest tests/core/test_resilience.py::TestCircuitBreakerStates -v

# Cancellation tests
pytest tests/core/test_resilience.py::TestCancellationToken -v

# Fabric API integration tests
pytest tests/core/test_fabric_client.py::TestListOntologies -v

# Streaming converter tests
pytest tests/core/test_fabric_client.py::TestStreamingRDFConverterBasic -v

# Pre-flight validation tests
pytest tests/rdf/test_validation.py::TestPreflightValidator -v

# End-to-end tests
pytest tests/rdf/test_validation.py::TestEndToEnd -v
```

### Specific tests
```powershell
# Run a test class
pytest tests/rdf/test_converter.py::TestSampleOntologies -v

# Run a single test
pytest tests/rdf/test_converter.py::TestSampleOntologies::test_foaf_ontology_ttl -v -s

# Run tests matching a pattern
pytest -k "rate_limit" -v
pytest -k "circuit" -v
```

## ✨ Sample output

Use `-v` for verbose and `-s` to print output during tests.

## What the tests cover

High-level coverage includes:
- Core conversion (entities, properties, relationships, type mapping)
- Fabric definition structure and serialization
- Error handling and security guards (paths, symlinks, config)
- Resilience (rate limiter, circuit breaker, retries)
- Fabric client behavior and streaming converter
- Validation, exporter, and end-to-end flows
- JSON-LD parity by routing `.jsonld` fixtures through the RDF converter
- **DTDL v4 features** (scaledDecimal, new primitive types, validation limits)

### Testing JSON-LD inputs

Because JSON-LD now flows through the RDF plugin, there is no dedicated
`jsonld` marker or plugin test suite. To validate JSON-LD handling:

- Place sample files in `samples/jsonld/` (several fixtures already exist).
- Run the same RDF-focused tests/CLI commands, letting the `.jsonld` extension
  auto-select the RDF path, for example:

```powershell
# Validate JSON-LD sample through RDF pipeline
python -m src.main validate samples/jsonld/simple_person.jsonld

# Convert JSON-LD to Fabric using explicit flag (optional)
python -m src.main convert --format rdf samples/jsonld/ecommerce_catalog.jsonld -o out.json
```

Adding or updating tests for JSON-LD scenarios simply means extending the RDF
tests (e.g., under `tests/rdf/`) with `.jsonld` fixtures—no separate plugin is
required.

### DTDL v4 Test Coverage

The `TestDTDLv4Features` class in `test_dtdl.py` validates:
- Primitive type parsing (byte, bytes, decimal, short, uuid, unsigned types)
- `scaledDecimal` schema parsing and validation
- Geospatial schema DTMIs with v4 version suffix
- Inheritance depth limits (max 12 levels)
- Complex schema depth limits (max 8 levels)
- `scaledDecimal` to Fabric conversion (mapped to JSON string)
- DTDLScaledDecimal model methods (`to_dict()`, `get_json_schema()`)
- Nullable command payload support

## Adding new tests

To add a new test:

1. Choose the appropriate test class or create a new one
2. Follow the naming convention: `test_<description>`
3. Use pytest fixtures for common setup (e.g., `converter`, `samples_dir`)
4. Add descriptive docstrings
5. Use assertions to validate expected behavior

### Example: Unit test
```python
def test_my_new_feature(self, converter):
    """Test description"""
    ttl = """
    @prefix : <http://example.org/> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    
    :MyClass a owl:Class .
    """
    
    entity_types, _ = converter.parse_ttl(ttl)
    assert len(entity_types) == 1
```

### Example: Integration test with mocked API
```python
def test_create_ontology_success(self, fabric_client):
    """Test successful ontology creation with mocked Fabric API."""
    mock_response = create_mock_response(
        status_code=201,
        json_data=create_ontology_response(
            ontology_id="5b218778-e7a5-4d73-8187-f10824047715",
            display_name="MyOntology"
        )
    )
    
    with patch('requests.request', return_value=mock_response):
        result = fabric_client.create_ontology(
            display_name="MyOntology",
            definition={"parts": []},
            wait_for_completion=False
        )
    
    assert result["id"] == "5b218778-e7a5-4d73-8187-f10824047715"
    assert result["type"] == "Ontology"
```

## Troubleshooting

### Import errors
Ensure you're running from the project root directory with dependencies installed:

```powershell
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install dependencies with dev extras
pip install -e ".[dev]"

# Run tests from project root
python -m pytest tests/ -v
```

### Tests run slowly
Use pytest-xdist for parallel execution:
```powershell
pip install pytest-xdist
python -m pytest tests/ -n auto
```

## Dependencies

Required packages:
```
pytest>=7.4.0
rdflib>=7.0.0
azure-identity>=1.15.0
requests>=2.31.0
tenacity>=8.2.0
tqdm>=4.66.0
```

Optional testing tools:
```powershell
pip install pytest-cov pytest-watch pytest-xdist
```

## 💡 Best practices

- ✅ Run tests before committing changes
- ✅ Add tests for new features (TDD)
- ✅ Keep test data in samples/ directory
- ✅ Use descriptive test names
- ✅ Review test coverage regularly
- ✅ Update tests when requirements change
- ✅ Use mock responses that match official API documentation
- ✅ Include both success and error path tests

## 📚 API documentation

Integration tests are aligned with official Microsoft Fabric API documentation:

- [Using Fabric APIs](https://learn.microsoft.com/en-us/rest/api/fabric/articles/using-fabric-apis)
- [Ontology Items API](https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items)
- [Long Running Operations](https://learn.microsoft.com/en-us/rest/api/fabric/articles/long-running-operation)
- [Rate Limiting/Throttling](https://learn.microsoft.com/en-us/rest/api/fabric/articles/using-fabric-apis#throttling)

