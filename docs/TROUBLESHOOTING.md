# Troubleshooting Guide

## Quick Diagnostics

```powershell
python --version              # Should be 3.9+
python -m src.main test       # Test authentication
python -m pytest tests/ -v    # Run test suite
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| **Unauthorized / 403** | Invalid credentials | Check config.json, verify workspace access |
| **CircuitBreakerOpen** | API failures | Wait for recovery, check Fabric service |
| **ItemDisplayNameAlreadyInUse** | Name exists | Use `--update` or different name |
| **CorruptedPayload** | Invalid data | Validate syntax, check encoding |
| **Invalid baseEntityTypeId** | Parent missing | Parent class must be in same ontology |
| **Invalid RDF/TTL syntax** | Parse error | Validate at [W3C Validator](https://www.w3.org/RDF/Validator/) |
| **No RDF triples found** | Empty/invalid file | Check encoding (UTF-8), prefix declarations |
| **MemoryError** | File too large | Use `--streaming` or split file |
| **Config not found** | Missing file | Copy `config.sample.json` to `src/config.json` |

## Authentication Issues

### Test Authentication
```powershell
python -m src.main test
```

### Interactive Auth Not Working
- Check `tenant_id` is correct
- Allow browser popups from Microsoft login
- Try signing out and back in

### Service Principal Issues
- Verify `client_id` and `client_secret`
- Ensure `Item.ReadWrite.All` permission
- Check app registration in correct tenant

## Upload Issues

```powershell
# Update existing ontology
python -m src.main upload --format rdf sample.ttl --update

# List existing ontologies
python -m src.main list

# Delete and recreate
python -m src.main delete <ontology-id>
python -m src.main upload --format rdf sample.ttl
```

## Memory Issues

For large files (>100MB):

```powershell
# Use streaming mode
python -m src.main upload --format rdf large.ttl --streaming

# Or force if you have enough RAM (4x file size)
python -m src.main upload --format rdf large.ttl --force-memory
```

## Path Issues

| Error | Solution |
|-------|----------|
| Symlinks not allowed | Use actual file path |
| Path traversal detected | Use absolute path or copy file |
| Extension not valid | Use .ttl, .rdf, .owl, .json, .dtdl |

### Windows Tips
```powershell
# Use forward slashes
python -m src.main validate --format rdf samples/rdf/ontology.ttl

# Quote paths with spaces
python -m src.main validate --format rdf "path with spaces/file.ttl"
```

## Valid TTL Example

```turtle
@prefix : <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:Person a owl:Class ;
    rdfs:label "Person" .
```

## Enable Debug Logging

Edit `config.json`:
```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

## Circuit Breaker

If you see "Circuit breaker is open":
1. Wait for automatic recovery (default: 60s)
2. Check Fabric service status
3. Check network connectivity

Adjust in config if needed:
```json
{
  "fabric": {
    "circuit_breaker": {
      "failure_threshold": 10,
      "recovery_timeout": 120.0
    }
  }
}
```

## See Also

- [Configuration](CONFIGURATION.md) - Setup details
- [RDF Guide](RDF_GUIDE.md) - RDF-specific issues
- [DTDL Guide](DTDL_GUIDE.md) - DTDL-specific issues
- [Testing](TESTING.md) - Run test suite
