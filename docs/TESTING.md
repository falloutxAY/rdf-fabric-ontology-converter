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
pytest -m resilience     # Rate limiter, circuit breaker
pytest -m security       # Security tests
pytest -m slow           # Long-running tests
pytest -m "not slow"     # Skip slow tests
```

## Test Files

| File | Purpose |
|------|---------|
| `tests/rdf/test_converter.py` | RDF conversion, type mapping |
| `tests/dtdl/test_dtdl.py` | DTDL parsing, validation, conversion |
| `tests/core/test_resilience.py` | Rate limiter, circuit breaker |
| `tests/core/test_fabric_client.py` | Fabric API client |
| `tests/rdf/test_validation.py` | Pre-flight validation |

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
├── conftest.py          # Shared fixtures
├── run_tests.py         # Test runner utility
├── fixtures/            # Test data
│   ├── ttl_fixtures.py  # RDF samples
│   ├── dtdl_fixtures.py # DTDL samples
│   └── config_fixtures.py
├── core/                # Infrastructure tests
├── rdf/                 # RDF converter tests
├── dtdl/                # DTDL converter tests
├── plugins/             # Plugin tests
└── integration/         # End-to-end tests
```

## Writing Tests

### Unit Test Example

```python
import pytest
from src.formats.rdf import RDFToFabricConverter

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
