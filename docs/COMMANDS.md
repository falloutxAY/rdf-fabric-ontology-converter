# CLI Commands Reference

This document provides a comprehensive reference for all CLI commands available in the RDF/DTDL to Microsoft Fabric Ontology Converter.

## Table of Contents

- [Command Naming Convention](#command-naming-convention)
- [Feature Comparison Matrix](#feature-comparison-matrix)
- [RDF Commands](#rdf-commands)
- [DTDL Commands](#dtdl-commands)
- [Common Commands](#common-commands)
- [Streaming Mode](#streaming-mode)
- [Exit Codes](#exit-codes)
- [See Also](#see-also)

## Command Naming Convention

- **RDF commands**: Use `rdf-` prefix (e.g., `rdf-validate`, `rdf-convert`)
- **DTDL commands**: Use `dtdl-` prefix (e.g., `dtdl-validate`, `dtdl-convert`)
- **Common commands**: No prefix (e.g., `list`, `get`, `delete`)

## Feature Comparison Matrix

| Feature | RDF Commands | DTDL Commands | Notes |
|---------|--------------|---------------|-------|
| **Validation** | `rdf-validate` | `dtdl-validate` | Both support single files and directories |
| `--recursive` | ✓ | ✓ | Search directories recursively |
| `--verbose` | ✓ | ✓ | Show detailed output |
| `--output` | ✓ | ✓ | Save report to file |
| `--save-report` | ✓ | ✓ | Auto-name report file |
| `--continue-on-error` | N/A | ✓ | DTDL-specific: continue on parse errors |
| **Conversion** | `rdf-convert` | `dtdl-convert` | Both support batch processing |
| `--recursive` | ✓ | ✓ | Batch convert multiple files |
| `--output` | ✓ | ✓ | Specify output path |
| `--streaming` | ✓ | ✓ | Memory-efficient mode for large files |
| `--force-memory` | ✓ | ✓ | Skip memory checks |
| `--ontology-name` | N/A | ✓ | DTDL-specific: set ontology name |
| `--namespace` | N/A | ✓ | DTDL-specific: entity namespace |
| `--flatten-components` | N/A | ✓ | DTDL-specific: flatten components |
| `--save-mapping` | N/A | ✓ | DTDL-specific: save DTMI mapping |
| **Upload** | `rdf-upload` | `dtdl-upload` | Both upload to Fabric |
| `--recursive` | ✓ | ✓ | Batch upload multiple files |
| `--config` | ✓ | ✓ | Specify config file |
| `--name` | ✓ | ✓ (as `--ontology-name`) | Override ontology name |
| `--description` | ✓ | N/A | Set ontology description |
| `--update` | ✓ | N/A | Update existing ontology |
| `--force` | ✓ | N/A | Skip confirmation prompts |
| `--dry-run` | N/A | ✓ | Convert without uploading |
| `--skip-validation` | ✓ | N/A | Skip pre-flight validation |
| `--streaming` | ✓ | ✓ | Memory-efficient mode |
| `--force-memory` | ✓ | ✓ | Skip memory safety checks |
| **Export** | `rdf-export` | N/A | Export from Fabric to TTL |

## RDF Commands

### rdf-validate

Validate TTL files for Fabric Ontology compatibility.

```bash
# Validate a single file
python -m src.main rdf-validate ontology.ttl

# Validate with verbose output
python -m src.main rdf-validate ontology.ttl --verbose

# Validate all files in a directory recursively
python -m src.main rdf-validate ./ontologies/ --recursive

# Save validation report
python -m src.main rdf-validate ontology.ttl --output report.json
python -m src.main rdf-validate ontology.ttl --save-report  # Auto-names as ontology.validation.json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Output JSON report file path |
| `--save-report` | `-s` | Save report to `<file>.validation.json` |
| `--verbose` | `-v` | Show detailed human-readable report |
| `--recursive` | `-r` | Recursively search directories for TTL files |
| `--allow-relative-up` | | Allow `..` in paths within current directory |

### rdf-convert

Convert TTL files to Fabric Ontology JSON format without uploading.

```bash
# Convert a single file
python -m src.main rdf-convert ontology.ttl

# Convert with custom output path
python -m src.main rdf-convert ontology.ttl --output fabric_def.json

# Batch convert all files in a directory
python -m src.main rdf-convert ./ontologies/ --recursive

# Use streaming mode for large files
python -m src.main rdf-convert large_ontology.ttl --streaming
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Output JSON file path or directory |
| `--streaming` | `-s` | Use streaming mode for large files (>100MB) |
| `--force-memory` | | Skip memory safety checks |
| `--recursive` | `-r` | Recursively search directories for TTL files |
| `--allow-relative-up` | | Allow `..` in paths within current directory |

### rdf-upload

Upload TTL files to Microsoft Fabric Ontology.

```bash
# Upload a single file
python -m src.main rdf-upload ontology.ttl

# Upload with custom name
python -m src.main rdf-upload ontology.ttl --name MyOntology

# Batch upload directory
python -m src.main rdf-upload ./ontologies/ --recursive --force

# Update existing ontology
python -m src.main rdf-upload ontology.ttl --name ExistingOntology --update
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--config` | `-c` | Path to configuration file |
| `--name` | `-n` | Override ontology name |
| `--description` | `-d` | Ontology description |
| `--update` | `-u` | Update if ontology exists |
| `--skip-validation` | | Skip pre-flight validation |
| `--force` | `-f` | Proceed even if issues found |
| `--streaming` | `-s` | Use streaming mode for large files |
| `--force-memory` | | Skip memory safety checks |
| `--save-validation-report` | | Save validation report on cancel |
| `--recursive` | `-r` | Batch upload all TTL files in directory |
| `--allow-relative-up` | | Allow `..` in paths within current directory |

### rdf-export

Export an ontology from Fabric to TTL format.

```bash
# Export by ontology ID
python -m src.main rdf-export 12345678-1234-1234-1234-123456789012

# Export with custom output path
python -m src.main rdf-export 12345678-1234-1234-1234-123456789012 --output exported.ttl
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--config` | `-c` | Path to configuration file |
| `--output` | `-o` | Output TTL file path |

## DTDL Commands

### dtdl-validate

Validate DTDL (Digital Twin Definition Language) files.

```bash
# Validate a single file
python -m src.main dtdl-validate model.json

# Validate a directory recursively
python -m src.main dtdl-validate ./models/ --recursive

# Verbose output with interface details
python -m src.main dtdl-validate ./models/ --recursive --verbose

# Save validation report
python -m src.main dtdl-validate ./models/ --output report.json
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--recursive` | `-r` | Recursively search directories |
| `--continue-on-error` | | Continue even if parse errors occur |
| `--verbose` | `-v` | Show detailed interface information |
| `--output` | `-o` | Output JSON report file path |
| `--save-report` | `-s` | Save report to `<path>.validation.json` |

### dtdl-convert

Convert DTDL files to Fabric Ontology JSON format.

```bash
# Convert a single file
python -m src.main dtdl-convert model.json

# Convert directory with custom name
python -m src.main dtdl-convert ./models/ --ontology-name MyDigitalTwin

# Save DTMI mapping for reference
python -m src.main dtdl-convert ./models/ --save-mapping

# Flatten components into parent entities
python -m src.main dtdl-convert ./models/ --flatten-components

# Use streaming mode for large files
python -m src.main dtdl-convert large_models.json --streaming
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Output JSON file path |
| `--ontology-name` | `-n` | Name for the ontology |
| `--namespace` | | Namespace for entity types (default: `usertypes`) |
| `--recursive` | `-r` | Recursively search directories |
| `--flatten-components` | | Flatten component properties into parent |
| `--save-mapping` | | Save DTMI to Fabric ID mapping file |
| `--streaming` | `-s` | Use streaming mode for large files (>100MB) |
| `--force-memory` | | Skip memory safety checks |

### dtdl-upload

Import DTDL models to Fabric Ontology (validate + convert + upload pipeline).

```bash
# Upload DTDL models
python -m src.main dtdl-upload ./models/ --ontology-name MyDigitalTwin

# Dry run (convert without uploading)
python -m src.main dtdl-upload ./models/ --dry-run --output preview.json

# Upload with custom namespace
python -m src.main dtdl-upload ./models/ --namespace custom_ns
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--config` | `-c` | Path to configuration file |
| `--ontology-name` | `-n` | Name for the ontology |
| `--namespace` | | Namespace for entity types (default: `usertypes`) |
| `--recursive` | `-r` | Recursively search directories |
| `--flatten-components` | | Flatten component properties into parent |
| `--dry-run` | | Convert but do not upload |
| `--output` | `-o` | Output file path for dry-run mode |
| `--streaming` | `-s` | Use streaming mode for large files |
| `--force-memory` | | Skip memory safety checks |

## Common Commands

### list

List all ontologies in the configured Fabric workspace.

```bash
python -m src.main list
python -m src.main list --config custom_config.json
```

### get

Get details of a specific ontology.

```bash
python -m src.main get 12345678-1234-1234-1234-123456789012
python -m src.main get 12345678-1234-1234-1234-123456789012 --with-definition
```

### delete

Delete an ontology from Fabric.

```bash
python -m src.main delete 12345678-1234-1234-1234-123456789012
python -m src.main delete 12345678-1234-1234-1234-123456789012 --force
```

### compare

Compare two TTL files for semantic equivalence.

```bash
python -m src.main compare original.ttl exported.ttl
python -m src.main compare original.ttl exported.ttl --verbose
```

### test

Test the converter with a sample ontology.

```bash
python -m src.main test
python -m src.main test --upload-test  # Also upload to Fabric
```

## Streaming Mode

Streaming mode enables memory-efficient processing of large ontology files. The converter automatically suggests streaming when files exceed 100MB.

### When to Use Streaming

- Files larger than 100MB
- Systems with limited memory
- Processing multiple large files
- Avoiding out-of-memory errors

### Streaming for RDF Files

```bash
# Convert large TTL file with streaming
python -m src.main rdf-convert large_ontology.ttl --streaming

# Upload with streaming mode
python -m src.main rdf-upload large_ontology.ttl --streaming

# Force memory checks off (use with caution)
python -m src.main rdf-convert huge_ontology.ttl --force-memory
```

### Streaming for DTDL Files

```bash
# Convert large DTDL file with streaming
python -m src.main dtdl-convert large_models.json --streaming

# Upload with streaming mode
python -m src.main dtdl-upload ./large_models/ --ontology-name MyOntology --streaming

# Force memory checks off (use with caution)
python -m src.main dtdl-convert huge_models.json --force-memory
```

### Streaming Architecture

The converter uses a common streaming engine (`src/core/streaming.py`) that supports both RDF and DTDL formats:

| Component | Description |
|-----------|-------------|
| `StreamConfig` | Configuration for chunk sizes and memory thresholds |
| `StreamReader` | Format-specific file readers (RDF, DTDL) |
| `ChunkProcessor` | Format-specific chunk processors |
| `StreamingEngine` | Main orchestrator for streaming operations |

### Streaming Features

- **Chunked Processing**: Files are processed in configurable chunks (default: 10,000 items)
- **Progress Callbacks**: Real-time progress reporting during conversion
- **Memory Monitoring**: Automatic memory pressure detection
- **Cancellation Support**: Operations can be cancelled mid-stream
- **Statistics Tracking**: Detailed processing statistics and timing

### Programmatic Streaming

```python
from src.core.streaming import (
    StreamingEngine,
    DTDLStreamReader,
    DTDLChunkProcessor,
    StreamConfig,
)

# Configure streaming
config = StreamConfig(
    chunk_size=5000,           # Process 5000 items per chunk
    memory_threshold_mb=50,    # Suggest streaming above 50MB
    enable_progress=True,
)

# Create and run streaming engine
engine = StreamingEngine(
    reader=DTDLStreamReader(),
    processor=DTDLChunkProcessor(),
    config=config
)

result = engine.process_file(
    "./large_models/",
    progress_callback=lambda n: print(f"Processed: {n}")
)

print(result.stats.get_summary())
```

See [API.md](API.md#streaming-engine) for complete API documentation.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Warning/minor issues |
| 2 | Error/parse failure |
| 130 | Cancelled by user (Ctrl+C) |

## See Also

- [CONFIGURATION.md](CONFIGURATION.md) - Configuration file reference
- [API.md](API.md) - Programmatic API documentation
- [MAPPING_LIMITATIONS.md](MAPPING_LIMITATIONS.md) - Conversion limitations
