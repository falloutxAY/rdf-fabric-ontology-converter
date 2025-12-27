# Troubleshooting Guide

## Quick Diagnostics

```powershell
# Run these commands to diagnose issues
python --version              # Should be 3.9+
python src/main.py test       # Test authentication
python -m pytest tests/ -v    # Run test suite
```

## Common Errors

| Error | Solution |
|-------|----------|
| **Unauthorized / 403 Forbidden** | Verify config.json credentials, ensure Contributor role on workspace, try `"use_interactive_auth": true` |
| **ItemDisplayNameAlreadyInUse** | Use `--update` flag or different name: `python src/main.py upload sample.ttl --name "MyOntology_v2"` |
| **CorruptedPayload** | Validate TTL syntax, check for special characters, ensure parent entities defined first |
| **Invalid baseEntityTypeId** | Parent class must be defined in same ontology, converter orders entities automatically |
| **Invalid RDF/TTL syntax** | Validate at [W3C Validator](https://www.w3.org/RDF/Validator/), check prefixes, ensure UTF-8 encoding |
| **No RDF triples found** | File is empty, wrong encoding, or missing prefix declarations |
| **Configuration file not found** | Copy `config.sample.json` to `src/config.json` and edit with your values |
| **Invalid JSON** | Validate at [jsonlint.com](https://jsonlint.com/), check for missing/extra commas |
| **MemoryError** | Use `--force-memory` flag or split large files (>500MB). Requires 3.5x file size in RAM |
| **FileNotFoundError** | Check file path and ensure file exists |
| **KeyError: workspace_id** | Add required field to config.json |

## Authentication Issues

Test authentication:
```powershell
python src/main.py test
```

If browser doesn't open for interactive auth:
- Check browser popup settings
- Manually copy authentication URL from terminal
- Verify correct tenant

## Upload Issues

```powershell
# Update existing ontology
python src/main.py upload sample.ttl --update

# List existing ontologies
python src/main.py list

# Delete and recreate
python src/main.py delete <ontology-id>
python src/main.py upload sample.ttl
```

## Memory Management

For large files (>500MB):
```powershell
# Use force flag if you have sufficient RAM (4x file size)
python src/main.py convert large.ttl --force-memory
python src/main.py upload large.ttl --force-memory

# Or split into smaller files by domain
```

Memory thresholds:
- Max file size: 500MB (without `--force-memory`)
- Minimum free memory: 256MB
- Memory overhead: 3.5x file size

## Valid TTL Example

```turtle
@prefix : <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:Person a owl:Class ;
    rdfs:label "Person" .
```

## Enable Debug Logging

Edit `src/config.json`:
```json
{
  "logging": {
    "level": "DEBUG",
    "file": "logs/debug.log"
  }
}
```

Check logs:
```powershell
# Windows
type logs\debug.log | findstr ERROR

# Linux/Mac  
grep ERROR logs/debug.log
```

## Testing Issues

```powershell
# Ensure pytest is installed
pip install pytest

# Run from project root
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_converter.py::test_name -v
```

## Path Issues

- Windows: Use forward slashes `samples/file.ttl` or double backslashes `samples\\file.ttl`
- PowerShell: Quote paths with spaces `"samples/my file.ttl"`
- Linux/Mac: Check permissions `chmod +r sample.ttl`

## Additional Resources

- [Configuration Guide](CONFIGURATION.md) - Setup details
- [Testing Guide](TESTING.md) - Test suite documentation  
- [Mapping Limitations](MAPPING_LIMITATIONS.md) - RDF/OWL conversion constraints
