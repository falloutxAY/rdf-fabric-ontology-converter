# Testing Documentation

## 🚀 Quick Start

```powershell
# Run all tests
python -m pytest tests/ -v

# Or use the test runner
python tests/run_tests.py all
```

## 📊 Test Statistics

| Metric | Count | Status |
|--------|-------|--------|
| **Total Tests** | 112 | ✅ ALL PASSING |
| Converter Unit Tests | 42 | ✅ |
| Exporter Unit Tests | 21 | ✅ |
| Integration Tests | 15 | ✅ |
| Pre-flight Validation Tests | 34 | ✅ |
| Sample TTL Files Validated | 4 | ✅ |

## 📋 Test Files

| File | Purpose | Tests |
|------|---------|-------|
| `test_converter.py` | Core RDF conversion | 42 |
| `test_exporter.py` | Fabric to TTL export | 21 |
| `test_integration.py` | Integration & E2E | 15 |
| `test_preflight_validator.py` | Pre-flight validation | 34 |
| `run_tests.py` | Test runner utility | - |

## Running Tests

### Quick Commands
```powershell
# Run all tests
python tests/run_tests.py all

# Run unit tests only
python tests/run_tests.py core

# Run sample file tests
python tests/run_tests.py samples

# Run a specific test
python tests/run_tests.py single test_foaf_ontology_ttl

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

### Test Categories
```powershell
# Core converter tests
python -m pytest tests/test_converter.py::TestRDFConverter -v

# Sample file tests
python -m pytest tests/test_converter.py::TestSampleOntologies -v

# Error handling tests
python -m pytest tests/test_converter.py::TestErrorHandling -v

# End-to-end tests
python -m pytest tests/test_integration.py::TestEndToEnd -v
```

### Specific Tests
```powershell
# Run a test class
python -m pytest tests/test_converter.py::TestSampleOntologies -v

# Run a single test
python -m pytest tests/test_converter.py::TestSampleOntologies::test_foaf_ontology_ttl -v -s
```

## ✨ Sample Test Output

Run the sample file tests to see current results:

```powershell
python -m pytest tests/test_converter.py::TestSampleOntologies::test_all_sample_ttl_files -v -s
```

## Sample TTL File Testing

All sample ontology files in the `samples/` directory are tested:

| File | Description |
|------|-------------|
| **sample_supply_chain_ontology.ttl** | Supply Chain domain |
| **sample_foaf_ontology.ttl** | Friend of a Friend vocabulary |
| **sample_iot_ontology.ttl** | IoT device management |
| **sample_fibo_ontology.ttl** | Financial Industry Business Ontology |

## What the Tests Validate

### Core Functionality ✅
- ✅ TTL parsing with rdflib
- ✅ Entity type extraction (owl:Class)
- ✅ Property extraction (owl:DatatypeProperty)
- ✅ Relationship extraction (owl:ObjectProperty)
- ✅ URI to name conversion and sanitization
- ✅ XSD type to Fabric type mapping
- ✅ Class hierarchy (rdfs:subClassOf) handling
- ✅ Multiple domain/range handling

### Fabric Ontology Generation ✅
- ✅ Correct "parts" array structure
- ✅ .platform metadata generation
- ✅ EntityTypes/ and RelationshipTypes/ path structure
- ✅ Base64 payload encoding
- ✅ Topological sorting (parents before children)

### Error Handling ✅
- ✅ Empty/invalid input
- ✅ Malformed TTL syntax
- ✅ Missing files
- ✅ Invalid configuration
- ✅ Permission errors

### Real-World Scenarios ✅
- ✅ Manufacturing ontology
- ✅ Social network (FOAF)
- ✅ IoT devices
- ✅ Financial ontology (FIBO)
- ✅ Large files (100+ classes)
- ✅ Unicode characters

## Adding New Tests

To add a new test:

1. Choose the appropriate test class or create a new one
2. Follow the naming convention: `test_<description>`
3. Use pytest fixtures for common setup (e.g., `converter`, `samples_dir`)
4. Add descriptive docstrings
5. Use assertions to validate expected behavior

Example:
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

## Troubleshooting

### Import errors
Ensure you're running from the project root directory with dependencies installed:

```powershell
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

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
```

Optional testing tools:
```powershell
pip install pytest-cov pytest-watch pytest-xdist
```

## Continuous Integration

Example for CI/CD pipelines:

```yaml
# GitHub Actions
- name: Run tests
  run: |
    pip install -r requirements.txt
    python -m pytest tests/ -v --junitxml=test-results.xml
```

## 💡 Testing Best Practices

- ✅ Run tests before committing changes
- ✅ Add tests for new features (TDD)
- ✅ Keep test data in samples/ directory
- ✅ Use descriptive test names
- ✅ Review test coverage regularly
- ✅ Update tests when requirements change

