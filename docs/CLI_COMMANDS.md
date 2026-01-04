# CLI Commands Reference

## Command Structure

```bash
python -m src.main <command> [options]
```

## Format Commands

Commands that work with ontology files use `--format {rdf,dtdl}`:

### validate

Check files for Fabric compatibility.

```bash
python -m src.main validate --format rdf ontology.ttl
python -m src.main validate --format dtdl models/ --recursive --verbose
```

| Option | Description |
|--------|-------------|
| `--format` | `rdf` or `dtdl` (required) |
| `--output`, `-o` | Save JSON report to file |
| `--verbose`, `-v` | Show detailed report |
| `--recursive`, `-r` | Search directories recursively |

### convert

Convert to Fabric JSON without uploading.

```bash
python -m src.main convert --format rdf ontology.ttl --output fabric.json
python -m src.main convert --format dtdl models/ --ontology-name MyTwin
```

| Option | Description |
|--------|-------------|
| `--format` | `rdf` or `dtdl` (required) |
| `--output`, `-o` | Output file path |
| `--ontology-name`, `-n` | Name for the ontology |
| `--streaming` | Memory-efficient mode for large files |
| `--recursive`, `-r` | Process directories recursively |
| `--component-mode` | DTDL: `skip`, `flatten`, `separate` |
| `--command-mode` | DTDL: `skip`, `property`, `entity` |

### upload

Upload ontology to Microsoft Fabric.

```bash
python -m src.main upload --format rdf ontology.ttl --ontology-name MyOntology
python -m src.main upload --format dtdl models/ --update
```

| Option | Description |
|--------|-------------|
| `--format` | `rdf` or `dtdl` (required) |
| `--config`, `-c` | Configuration file path |
| `--ontology-name`, `-n` | Name for the ontology |
| `--update`, `-u` | Update if ontology exists |
| `--dry-run` | Convert without uploading |
| `--streaming` | Memory-efficient mode |
| `--skip-validation` | Skip pre-flight checks |

### export

Export Fabric ontology to TTL (RDF only).

```bash
python -m src.main export <ontology-id> --output exported.ttl
```

## Workspace Commands

Commands that manage ontologies in your Fabric workspace:

### list

```bash
python -m src.main list
```

### get

```bash
python -m src.main get <ontology-id>
python -m src.main get <ontology-id> --with-definition
```

### delete

```bash
python -m src.main delete <ontology-id>
python -m src.main delete <ontology-id> --force
```

### compare

Compare two RDF files for semantic equivalence.

```bash
python -m src.main compare original.ttl exported.ttl --verbose
```

### test

Test authentication with a sample ontology.

```bash
python -m src.main test
python -m src.main test --upload-test
```

## Plugin Commands

```bash
python -m src.main plugin list          # List available plugins
python -m src.main plugin info rdf      # Show plugin details
```

## Supported Formats

| Format | Extensions | Description |
|--------|------------|-------------|
| `rdf` | `.ttl`, `.rdf`, `.owl`, `.nt`, `.nq`, `.trig`, `.n3`, `.jsonld` | RDF/OWL ontologies |
| `dtdl` | `.json`, `.dtdl` | Digital Twins Definition Language v2/v3/v4 |

## Streaming Mode

For files >100MB, use `--streaming` for memory-efficient processing:

```bash
python -m src.main convert --format rdf large.ttl --streaming
python -m src.main upload --format rdf large.ttl --streaming
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Warning/minor issues |
| 2 | Error/parse failure |
| 130 | Cancelled (Ctrl+C) |

## See Also

- [Configuration](CONFIGURATION.md) - Setup and authentication
- [RDF Guide](RDF_GUIDE.md) - RDF conversion details
- [DTDL Guide](DTDL_GUIDE.md) - DTDL conversion details
