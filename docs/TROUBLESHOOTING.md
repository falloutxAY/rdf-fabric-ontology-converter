# Troubleshooting Guide

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Common Errors](#common-errors)
- [Authentication Issues](#authentication-issues)
- [Upload Issues](#upload-issues)
- [Circuit Breaker Issues](#circuit-breaker-issues)
- [Memory Management](#memory-management)
- [Valid TTL Example](#valid-ttl-example)
- [Enable Debug Logging](#enable-debug-logging)
- [Testing Issues](#testing-issues)
- [Path Issues](#path-issues)
- [Additional Resources](#additional-resources)

## Quick Diagnostics

```powershell
# Run these commands to diagnose issues
python --version                  # Should be 3.9+
python -m src.main test           # Test authentication
python -m pytest tests/ -v        # Run test suite
```

## Common Errors

| Error | Solution |
|-------|----------|
| **Unauthorized / 403 Forbidden** | Verify config.json credentials, ensure Contributor role on workspace, try `"use_interactive_auth": true` |
| **CircuitBreakerOpen** | API failing repeatedly; wait for recovery timeout or check Fabric service status |
| **ItemDisplayNameAlreadyInUse** | Use `--update` flag or different name: `python -m src.main upload --format rdf sample.ttl --ontology-name "MyOntology_v2"` |
| **CorruptedPayload** | Validate TTL syntax, check for special characters, ensure parent entities defined first |
| **Invalid baseEntityTypeId** | Parent class must be defined in same ontology, converter orders entities automatically |
| **Invalid RDF/TTL syntax** | Validate at [W3C Validator](https://www.w3.org/RDF/Validator/), check prefixes, ensure UTF-8 encoding |
| **No RDF triples found** | File is empty, wrong encoding, or missing prefix declarations |
| **Unknown format `jsonld`** | JSON-LD no longer has its own CLI switch—use `--format rdf` (or rely on `.jsonld` auto-detection) so the RDF plugin handles it |
| **Configuration file not found** | Copy `config.sample.json` to `src/config.json` and edit with your values |
| **Invalid JSON** | Validate at [jsonlint.com](https://jsonlint.com/), check for missing/extra commas |
| **MemoryError** | Use `--force-memory` flag or split large files (>500MB). Requires 3.5x file size in RAM |
| **FileNotFoundError** | Check file path and ensure file exists |
| **KeyError: workspace_id** | Add required field to config.json |

## Authentication Issues

Test authentication:
```powershell
python -m src.main test
```

If browser doesn't open for interactive auth:
- Check browser popup settings
- Manually copy authentication URL from terminal
- Verify correct tenant

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

## Circuit Breaker Issues

Protects you when the Fabric API is unhealthy.

If you see "Circuit breaker is open":
- Wait for automatic recovery (it will retry after the timeout)
- Check Fabric service status and your network
- Optionally relax thresholds in config (e.g., higher `failure_threshold`, longer `recovery_timeout`)

## Memory Management

For large files (>100MB), use streaming mode:
```powershell
# Use streaming mode for memory-efficient processing
python -m src.main convert --format rdf large.ttl --streaming
python -m src.main upload --format rdf large.ttl --streaming

# Or use force flag if you have sufficient RAM (4x file size)
python -m src.main convert --format rdf large.ttl --force-memory
python -m src.main upload --format rdf large.ttl --force-memory

# Or split into smaller files by domain
```

Memory thresholds (guidance): file size ~3.5× RAM overhead; use streaming for large files.

## Valid TTL Example

```turtle
@prefix : <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:Person a owl:Class ;
    rdfs:label "Person" .
```

For more examples, see [RDF_GUIDE.md](RDF_GUIDE.md).

## Enable Debug Logging

Edit `src/config.json` to set logging level to DEBUG. See [CONFIGURATION.md](CONFIGURATION.md) for details.

## Testing Issues

See [TESTING.md](TESTING.md) for complete test suite documentation and troubleshooting.

## Path Issues

The tool validates all file paths to prevent security issues:

- **Path traversal prevention**: Paths containing `..` are blocked
- **Symlink rejection**: Symbolic links are not allowed for input files
- **Extension validation**: Only valid file extensions are accepted (.ttl, .rdf, .owl, .json)
- **Permission checks**: Files must be readable before processing

If you need to access files outside the current directory:
```bash
# Copy files to working directory instead of using path traversal
cp /some/external/path/ontology.ttl ./ontology.ttl
python -m src.main upload --format rdf ontology.ttl --ontology-name "MyOntology"
```

- Windows: Use forward slashes `samples/file.ttl` or double backslashes `samples\\file.ttl`
- PowerShell: Quote paths with spaces `"samples/my file.ttl"`
- Linux/Mac: Check permissions `chmod +r sample.ttl`

If you see security-related errors:

| Error | Cause | Solution |
|-------|-------|----------|
| `Security Error: Symlinks are not allowed` | Input file is a symbolic link | Use the actual file path |
| `Security Error: Path traversal detected` | Path contains `..` | Use absolute path or copy file to working directory |
| `Configuration file must be in current working directory` | Config file outside cwd | Move config.json to working directory |

### Allowing relative-up safely (`--allow-relative-up`)

For trusted local use, you can allow `..` in paths by adding `--allow-relative-up` to the command. This is available on `validate`, `upload`, `convert`, and `compare`.

Important safeguards:

- `--allow-relative-up` only permits `..` when the resolved path stays within your current working directory.
- If the resolved path leaves the cwd, the CLI will block and show a friendly message:
  - “Path resolves outside the current directory”
  - “Relative up is only allowed within the current directory when using --allow-relative-up.”
  - Tip to `cd` into the target folder or use an absolute path inside the workspace.

Examples (Windows PowerShell):

```powershell
# Blocked: resolves outside the cwd
python -m src.main validate --format rdf ..\samples\rdf\sample_foaf_ontology.ttl --allow-relative-up --verbose

# Allowed: remains inside the cwd after resolution
python -m src.main validate --format rdf .\samples\..\samples\rdf\sample_foaf_ontology.ttl --allow-relative-up --verbose

# Tip: Always quote absolute paths with spaces
python -m src.main validate --format rdf "C:\Users\me\Projects\rdf-fabric-ontology-converter\samples\rdf\sample_foaf_ontology.ttl" --verbose
```

Notes:

- Absolute paths outside the cwd without `..` are permitted; a warning may be logged.
- Configuration files are always restricted to the current working directory for safety.

Additional error message you may see with `--allow-relative-up`:

| Error | Cause | Solution |
|-------|-------|----------|
| `Path resolves outside the current directory` | `--allow-relative-up` used but the resolved path left the cwd | `cd` into the target folder or use an absolute path inside the workspace |

## Additional Resources

- [Configuration Guide](CONFIGURATION.md) - Setup details
- [Testing Guide](TESTING.md) - Test suite documentation  
- [RDF Guide](RDF_GUIDE.md) - RDF/OWL conversion constraints and best practices
- [DTDL Guide](DTDL_GUIDE.md) - DTDL conversion constraints and best practices
