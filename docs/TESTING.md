# Testing Guide

## Quick Start

```powershell
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

## Test Categories

Use pytest markers to run specific test categories:

```powershell
pytest -m unit           # Fast unit tests
pytest -m integration    # Integration tests
pytest -m samples        # Sample file tests
pytest -m industry       # Industry accelerator tests (CDM)
pytest -m resilience     # Rate limiter, circuit breaker
pytest -m security       # Security tests
pytest -m slow           # Long-running tests
pytest -m contract       # API contract validation tests
pytest -m e2e            # End-to-end smoke tests
pytest -m live           # Live Fabric API tests (opt-in)
pytest -m "not slow"     # Skip slow tests
```

## Live Integration Tests

Live tests run against the real Fabric API. They are **disabled by default** to avoid accidental API calls.

```powershell
# Enable live tests with --run-live flag
pytest tests/integration/test_fabric_live.py -v --run-live

# Or set environment variable
$env:FABRIC_LIVE_TESTS = "1"
pytest tests/integration/ -v

# Override workspace ID
pytest --run-live --workspace-id "your-workspace-guid"
```

**Requirements for live tests:**
- Valid Azure credentials (interactive browser or DefaultAzureCredential)
- `workspace_id` configured in `config.json` or via `--workspace-id`
- Network access to `api.fabric.microsoft.com`

**Warning:** Live tests create, modify, and delete real ontologies in your workspace.

## Test Files

| File | Purpose |
|------|---------|
| `tests/rdf/test_converter.py` | RDF conversion, type mapping |
| `tests/rdf/test_rdf_formats.py` | All RDF format support (TTL, RDF/XML, N3, etc.) |
| `tests/dtdl/test_dtdl.py` | DTDL parsing, validation, conversion |
| `tests/cdm/test_cdm_parser.py` | CDM parsing |
| `tests/cdm/test_cdm_validator.py` | CDM validation |
| `tests/cdm/test_cdm_converter.py` | CDM conversion |
| `tests/cdm/test_cdm_samples.py` | CDM sample file tests |
| `tests/cdm/test_cdm_integration.py` | CDM integration tests |
| `tests/core/test_resilience.py` | Rate limiter, circuit breaker |
| `tests/core/test_fabric_client.py` | Fabric API client (mocked) |
| `tests/core/test_fabric_contract.py` | API contract validation with schema checks |
| `tests/rdf/test_validation.py` | Pre-flight validation |
| `tests/integration/test_fabric_live.py` | Live Fabric API tests (opt-in) |
| `tests/e2e/test_upload_smoke.py` | End-to-end upload pipeline |

## Running Specific Tests

```powershell
# Run a test file
pytest tests/rdf/test_converter.py -v

# Run a test class
pytest tests/rdf/test_converter.py::TestRDFConverter -v

# Run a single test
pytest tests/rdf/test_converter.py::TestRDFConverter::test_basic_class -v

# Match pattern
pytest -k "rate_limit" -v
```

## Coverage

```powershell
# Generate HTML report
pytest tests/ --cov=src --cov-report=html

# View report
start htmlcov/index.html
```

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures, markers, CLI options
├── run_tests.py         # Test runner utility
├── fixtures/            # Test data
│   ├── ttl_fixtures.py  # RDF samples
│   ├── dtdl_fixtures.py # DTDL samples
│   ├── config_fixtures.py
│   └── fabric_responses.py  # Validated API mock responses
├── core/                # Infrastructure tests
│   ├── test_fabric_client.py    # Mocked API tests
│   └── test_fabric_contract.py  # Contract validation tests
├── rdf/                 # RDF converter tests
├── dtdl/                # DTDL converter tests
├── plugins/             # Plugin tests
├── integration/         # Live API tests (opt-in)
│   └── test_fabric_live.py
└── e2e/                 # End-to-end smoke tests
    └── test_upload_smoke.py
```

## Writing Tests

### Unit Test Example

```python
import pytest
from src.rdf import RDFToFabricConverter

class TestRDFConverter:
    def test_basic_class(self):
        content = """
        @prefix : <http://example.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        
        :Person a owl:Class .
        """
        converter = RDFToFabricConverter()
        result = converter.convert(content)
        
        assert len(result.entity_types) == 1
        assert result.entity_types[0].name == "Person"
```

### Using Fixtures

```python
@pytest.fixture
def sample_ttl():
    return """
    @prefix : <http://example.org/> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    :Person a owl:Class .
    """

def test_with_fixture(sample_ttl):
    converter = RDFToFabricConverter()
    result = converter.convert(sample_ttl)
    assert len(result.entity_types) == 1
```

### Marking Tests

```python
@pytest.mark.unit
def test_fast_operation():
    pass

@pytest.mark.integration
def test_api_call():
    pass

@pytest.mark.slow
def test_large_file():
    pass
```

## Dependencies

Install test dependencies:
```powershell
pip install -e ".[dev]"
# or
pip install pytest pytest-cov
```

## Troubleshooting

### Import Errors

```powershell
# Ensure package is installed
pip install -e .
```

### Slow Tests

```powershell
# Skip slow tests
pytest -m "not slow" -v

# Run only unit tests
pytest -m unit -v
```

## See Also

- [Architecture](ARCHITECTURE.md) - Code structure
- [API Reference](API.md) - Programmatic usage
