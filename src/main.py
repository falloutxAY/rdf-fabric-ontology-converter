#!/usr/bin/env python3
"""
RDF TTL to Microsoft Fabric Ontology Uploader

This is the main entry point for uploading RDF TTL ontologies to Microsoft Fabric.

Usage:
    python main.py upload <ttl_file> [--config <config.json>] [--name <ontology_name>]
    python main.py list [--config <config.json>]
    python main.py get <ontology_id> [--config <config.json>]
    python main.py delete <ontology_id> [--config <config.json>]
    python main.py test [--config <config.json>]
    python main.py convert <ttl_file> [--output <output.json>]
"""

import argparse
import json
import logging
import sys
import os
import tempfile
from pathlib import Path
from typing import Optional

from rdf_converter import parse_ttl_file, parse_ttl_content
from fabric_client import FabricConfig, FabricOntologyClient, FabricAPIError
from fabric_to_ttl import FabricToTTLConverter, compare_ontologies, round_trip_test
from preflight_validator import (
    PreflightValidator, ValidationReport, validate_ttl_file, validate_ttl_content,
    generate_import_log, IssueSeverity
)


# Setup logging with fallback locations
def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """
    Setup logging configuration with fallback locations.
    
    If the primary log file location fails (permission denied, disk full, etc.),
    attempts to write to fallback locations in order:
    1. Requested location
    2. System temp directory
    3. User home directory
    4. Console-only (final fallback)
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path. If None, logs to console only.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    handlers = [logging.StreamHandler(sys.stdout)]
    actual_log_file = None
    
    if log_file:
        # Define fallback locations
        log_filename = os.path.basename(log_file) or "rdf_converter.log"
        fallback_locations = [
            log_file,  # Primary location
            os.path.join(tempfile.gettempdir(), log_filename),  # System temp
            os.path.join(Path.home(), log_filename),  # User home
        ]
        
        file_handler = None
        for fallback_path in fallback_locations:
            try:
                # Ensure directory exists
                log_dir = os.path.dirname(fallback_path)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)
                
                # Try to create/open the file
                file_handler = logging.FileHandler(fallback_path, encoding='utf-8')
                handlers.append(file_handler)
                actual_log_file = fallback_path
                
                if fallback_path != log_file:
                    print(f"Note: Using fallback log file: {fallback_path}")
                break
                
            except PermissionError as e:
                print(f"  Could not create log at {fallback_path}: Permission denied")
                continue
            except OSError as e:
                print(f"  Could not create log at {fallback_path}: {e}")
                continue
            except Exception as e:
                print(f"  Unexpected error creating log at {fallback_path}: {e}")
                continue
        
        if not file_handler:
            print(f"Warning: Could not write log file to any location")
            print(f"  Requested: {log_file}")
            print(f"  Attempted fallbacks: {', '.join(fallback_locations[1:])}")
            print(f"  Logging to console only")
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
    )
    
    logger = logging.getLogger(__name__)
    if actual_log_file:
        logger.info(f"Logging to: {actual_log_file}")


def load_config(config_path: str) -> dict:
    """Load configuration from file."""
    if not config_path:
        raise ValueError("config_path cannot be empty")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Please create a config.json file or specify one with --config"
        )
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in configuration file {config_path} at line {e.lineno}, column {e.colno}: {e.msg}"
        )
    except UnicodeDecodeError as e:
        raise ValueError(f"File encoding error in {config_path}: {e}")
    except PermissionError:
        raise PermissionError(f"Permission denied reading {config_path}")
    except Exception as e:
        raise IOError(f"Error loading configuration file: {e}")
    
    if not isinstance(config, dict):
        raise ValueError(f"Configuration file must contain a JSON object, got {type(config)}")
    
    return config


def get_default_config_path() -> str:
    """Get the default configuration file path."""
    script_dir = Path(__file__).parent
    return str(script_dir / "config.json")


def cmd_upload(args):
    """Upload an RDF TTL file to Fabric Ontology."""
    logger = logging.getLogger(__name__)
    
    # Load configuration
    config_path = args.config or get_default_config_path()
    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found: {config_path}")
        print("Please create a config.json file or specify one with --config")
        sys.exit(1)
    
    config_data = load_config(config_path)
    fabric_config = FabricConfig.from_dict(config_data)
    
    if not fabric_config.workspace_id or fabric_config.workspace_id == "YOUR_WORKSPACE_ID":
        print("Error: Please configure your Fabric workspace_id in config.json")
        sys.exit(1)
    
    # Setup logging from config
    log_config = config_data.get('logging', {})
    setup_logging(
        level=log_config.get('level', 'INFO'),
        log_file=log_config.get('file'),
    )
    
    # Parse the TTL file
    ttl_file = args.ttl_file
    if not os.path.exists(ttl_file):
        print(f"Error: TTL file not found: {ttl_file}")
        sys.exit(1)
    
    logger.info(f"Parsing TTL file: {ttl_file}")
    
    try:
        with open(ttl_file, 'r', encoding='utf-8') as f:
            ttl_content = f.read()
    except FileNotFoundError:
        print(f"Error: TTL file not found: {ttl_file}")
        sys.exit(1)
    except UnicodeDecodeError as e:
        print(f"Error: Failed to read TTL file due to encoding issue: {e}")
        print("Try converting the file to UTF-8 encoding")
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied reading file: {ttl_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading TTL file: {e}")
        sys.exit(1)
    
    if not ttl_content.strip():
        print(f"Error: TTL file is empty: {ttl_file}")
        sys.exit(1)
    
    # --- PRE-FLIGHT VALIDATION ---
    if not args.skip_validation:
        print("\n" + "=" * 60)
        print("PRE-FLIGHT VALIDATION")
        print("=" * 60)
        
        validation_report = validate_ttl_content(ttl_content, ttl_file)
        
        if validation_report.can_import_seamlessly:
            print("✓ Ontology can be imported seamlessly.")
            print(f"  Classes: {validation_report.summary.get('declared_classes', 0)}")
            print(f"  Properties: {validation_report.summary.get('declared_properties', 0)}")
        else:
            print("⚠ Issues detected that may affect conversion quality:\n")
            print(f"  Errors:   {validation_report.issues_by_severity.get('error', 0)}")
            print(f"  Warnings: {validation_report.issues_by_severity.get('warning', 0)}")
            print(f"  Info:     {validation_report.issues_by_severity.get('info', 0)}")
            print()
            
            # Show top issues
            warning_issues = [i for i in validation_report.issues if i.severity in (IssueSeverity.ERROR, IssueSeverity.WARNING)]
            if warning_issues:
                print("Key issues:")
                for issue in warning_issues[:5]:
                    icon = "✗" if issue.severity == IssueSeverity.ERROR else "⚠"
                    print(f"  {icon} {issue.message}")
                if len(warning_issues) > 5:
                    print(f"  ... and {len(warning_issues) - 5} more warnings/errors")
            
            print()
            
            # Ask user if they want to proceed (unless --force is specified)
            if not args.force:
                print("Some RDF/OWL constructs cannot be fully represented in Fabric Ontology.")
                confirm = input("Do you want to proceed with the import anyway? [y/N]: ")
                if confirm.lower() != 'y':
                    print("Import cancelled.")
                    
                    # Optionally save the validation report
                    if args.save_validation_report:
                        report_path = str(Path(ttl_file).with_suffix('.validation.json'))
                        validation_report.save_to_file(report_path)
                        print(f"Validation report saved to: {report_path}")
                    
                    sys.exit(0)
        
        print("=" * 60 + "\n")
    
    id_prefix = config_data.get('ontology', {}).get('id_prefix', 1000000000000)
    force_memory = getattr(args, 'force_memory', False)
    
    try:
        definition, extracted_name = parse_ttl_content(ttl_content, id_prefix, force_large_file=force_memory)
    except ValueError as e:
        logger.error(f"Invalid TTL content: {e}")
        print(f"Error: Invalid RDF/TTL content: {e}")
        sys.exit(1)
    except MemoryError as e:
        logger.error(f"Insufficient memory to parse TTL file: {e}")
        print(f"\nError: {e}")
        print("\nTip: Use --force-memory to bypass memory safety checks (use with caution).")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to parse TTL file: {e}", exc_info=True)
        print(f"Error parsing TTL file: {e}")
        sys.exit(1)
    
    if not definition or 'parts' not in definition:
        print("Error: Generated definition is invalid or empty")
        sys.exit(1)
    
    if not definition['parts']:
        print("Warning: No entity types or relationship types found in TTL file")
        logger.warning("Empty ontology definition generated")
    
    # Use provided name or extracted name
    ontology_name = args.name or extracted_name
    description = args.description or f"Imported from {os.path.basename(ttl_file)}"
    
    logger.info(f"Ontology name: {ontology_name}")
    logger.info(f"Definition has {len(definition['parts'])} parts")
    
    # Create Fabric client and upload
    client = FabricOntologyClient(fabric_config)
    
    try:
        # Use create_or_update for automatic incremental updates
        result = client.create_or_update_ontology(
            display_name=ontology_name,
            description=description,
            definition=definition,
            wait_for_completion=True,
        )
        
        print(f"Successfully processed ontology '{ontology_name}'")
        print(f"Ontology ID: {result.get('id', 'Unknown')}")
        print(f"Workspace ID: {result.get('workspaceId', fabric_config.workspace_id)}")
        
        # Generate import log if there were validation issues
        if not args.skip_validation and not validation_report.can_import_seamlessly:
            log_dir = log_config.get('file', 'logs/app.log')
            log_dir = os.path.dirname(log_dir) or 'logs'
            log_path = generate_import_log(validation_report, log_dir, ontology_name)
            print(f"\nImport log saved to: {log_path}")
            print("This log documents RDF/OWL constructs that could not be fully converted.")
        
    except FabricAPIError as e:
        logger.error(f"Fabric API error: {e}")
        print(f"Error: {e.message}")
        if e.error_code == "ItemDisplayNameAlreadyInUse":
            print("Hint: Use --update to update an existing ontology, or choose a different name with --name")
        sys.exit(1)


def cmd_validate(args):
    """Validate a TTL file for Fabric Ontology compatibility without uploading."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    ttl_file = args.ttl_file
    if not os.path.exists(ttl_file):
        print(f"Error: TTL file not found: {ttl_file}")
        sys.exit(1)
    
    print(f"Validating TTL file: {ttl_file}\n")
    
    try:
        with open(ttl_file, 'r', encoding='utf-8') as f:
            ttl_content = f.read()
    except UnicodeDecodeError as e:
        print(f"Error: Failed to read TTL file due to encoding issue: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading TTL file: {e}")
        sys.exit(1)
    
    # Run validation
    report = validate_ttl_content(ttl_content, ttl_file)
    
    # Display results
    if args.verbose:
        print(report.get_human_readable_summary())
    else:
        print("=" * 60)
        print("VALIDATION RESULT")
        print("=" * 60)
        
        if report.can_import_seamlessly:
            print("✓ This ontology can be imported SEAMLESSLY.")
            print("  No significant conversion issues detected.")
        else:
            print("✗ Issues detected that may affect conversion quality.")
            print()
            print(f"Total Issues: {report.total_issues}")
            print(f"  - Errors:   {report.issues_by_severity.get('error', 0)}")
            print(f"  - Warnings: {report.issues_by_severity.get('warning', 0)}")
            print(f"  - Info:     {report.issues_by_severity.get('info', 0)}")
        
        print()
        print("Ontology Statistics:")
        print(f"  Triples: {report.summary.get('total_triples', 0)}")
        print(f"  Classes: {report.summary.get('declared_classes', 0)}")
        print(f"  Properties: {report.summary.get('declared_properties', 0)}")
        
        if report.issues and not report.can_import_seamlessly:
            print()
            print("Issue Categories:")
            for category, count in sorted(report.issues_by_category.items(), key=lambda x: -x[1]):
                print(f"  - {category.replace('_', ' ').title()}: {count}")
    
    # Save report to file if requested
    if args.output:
        report.save_to_file(args.output)
        print(f"\nDetailed report saved to: {args.output}")
    elif args.save_report:
        output_path = str(Path(ttl_file).with_suffix('.validation.json'))
        report.save_to_file(output_path)
        print(f"\nDetailed report saved to: {output_path}")
    
    # Exit with appropriate code
    if report.can_import_seamlessly:
        sys.exit(0)
    elif report.issues_by_severity.get('error', 0) > 0:
        sys.exit(2)  # Errors present
    else:
        sys.exit(1)  # Only warnings


def cmd_list(args):
    """List all ontologies in the workspace."""
    logger = logging.getLogger(__name__)
    
    config_path = args.config or get_default_config_path()
    config_data = load_config(config_path)
    fabric_config = FabricConfig.from_dict(config_data)
    
    log_config = config_data.get('logging', {})
    setup_logging(level=log_config.get('level', 'INFO'))
    
    client = FabricOntologyClient(fabric_config)
    
    try:
        ontologies = client.list_ontologies()
        
        if not ontologies:
            print("No ontologies found in the workspace.")
            return
        
        print(f"\nFound {len(ontologies)} ontologies:\n")
        print(f"{'ID':<40} {'Name':<30} {'Description':<40}")
        print("-" * 110)
        
        for ont in ontologies:
            ont_id = ont.get('id', 'Unknown')
            name = ont.get('displayName', 'Unknown')[:30]
            desc = (ont.get('description', '') or '')[:40]
            print(f"{ont_id:<40} {name:<30} {desc:<40}")
        
    except FabricAPIError as e:
        logger.error(f"Fabric API error: {e}")
        print(f"Error: {e.message}")
        sys.exit(1)


def cmd_get(args):
    """Get details of a specific ontology."""
    logger = logging.getLogger(__name__)
    
    config_path = args.config or get_default_config_path()
    config_data = load_config(config_path)
    fabric_config = FabricConfig.from_dict(config_data)
    
    log_config = config_data.get('logging', {})
    setup_logging(level=log_config.get('level', 'INFO'))
    
    client = FabricOntologyClient(fabric_config)
    
    try:
        ontology = client.get_ontology(args.ontology_id)
        print("\nOntology Details:")
        print(json.dumps(ontology, indent=2))
        
        if args.with_definition:
            print("\nOntology Definition:")
            definition = client.get_ontology_definition(args.ontology_id)
            print(json.dumps(definition, indent=2))
        
    except FabricAPIError as e:
        logger.error(f"Fabric API error: {e}")
        print(f"Error: {e.message}")
        sys.exit(1)


def cmd_delete(args):
    """Delete an ontology."""
    logger = logging.getLogger(__name__)
    
    config_path = args.config or get_default_config_path()
    config_data = load_config(config_path)
    fabric_config = FabricConfig.from_dict(config_data)
    
    log_config = config_data.get('logging', {})
    setup_logging(level=log_config.get('level', 'INFO'))
    
    client = FabricOntologyClient(fabric_config)
    
    if not args.force:
        confirm = input(f"Are you sure you want to delete ontology {args.ontology_id}? [y/N]: ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return
    
    try:
        client.delete_ontology(args.ontology_id)
        print(f"Successfully deleted ontology {args.ontology_id}")
        
    except FabricAPIError as e:
        logger.error(f"Fabric API error: {e}")
        print(f"Error: {e.message}")
        sys.exit(1)


def cmd_test(args):
    """Test the program with a sample ontology."""
    logger = logging.getLogger(__name__)
    
    config_path = args.config or get_default_config_path()
    if os.path.exists(config_path):
        config_data = load_config(config_path)
        log_config = config_data.get('logging', {})
        setup_logging(level=log_config.get('level', 'INFO'))
    else:
        setup_logging()
    
    # Find sample TTL file in samples folder (check multiple locations)
    script_dir = Path(__file__).parent
    candidate_paths = [
        script_dir.parent / "samples" / "sample_ontology.ttl",  # project root / samples
        Path.cwd() / "samples" / "sample_ontology.ttl",         # current working dir / samples
        script_dir / "samples" / "sample_ontology.ttl",         # src/samples (fallback)
    ]
    sample_ttl = next((p for p in candidate_paths if p.exists()), None)
    
    if not sample_ttl:
        print("Error: Sample TTL file not found in expected locations:")
        for p in candidate_paths:
            print(f"  - {p}")
        sys.exit(1)
    
    print(f"Testing with sample ontology: {sample_ttl}\n")
    
    # Parse the sample TTL
    with open(sample_ttl, 'r', encoding='utf-8') as f:
        ttl_content = f.read()
    
    definition, ontology_name = parse_ttl_content(ttl_content)
    
    print(f"Ontology Name: {ontology_name}")
    print(f"Number of definition parts: {len(definition['parts'])}")
    print("\nDefinition Parts:")
    
    for part in definition['parts']:
        print(f"  - {part['path']}")
    
    print("\n--- Full Definition (JSON) ---\n")
    print(json.dumps(definition, indent=2))
    
    # Test Fabric connection if config exists
    if os.path.exists(config_path):
        config_data = load_config(config_path)
        fabric_config = FabricConfig.from_dict(config_data)
        
        if fabric_config.workspace_id and fabric_config.workspace_id != "YOUR_WORKSPACE_ID":
            print("\n--- Testing Fabric Connection ---\n")
            client = FabricOntologyClient(fabric_config)
            
            try:
                ontologies = client.list_ontologies()
                print(f"Successfully connected to Fabric. Found {len(ontologies)} existing ontologies.")
                
                if args.upload_test:
                    print("\nUploading test ontology...")
                    result = client.create_ontology(
                        display_name="Test_Manufacturing_Ontology",
                        description="Test ontology from RDF import tool",
                        definition=definition,
                    )
                    print(f"Successfully created test ontology: {result.get('id')}")
                    
            except FabricAPIError as e:
                print(f"Fabric API error: {e.message}")
        else:
            print("\nNote: Configure workspace_id in config.json to test Fabric connection.")
    else:
        print(f"\nNote: Create {config_path} to test Fabric connection.")


def cmd_convert(args):
    """Convert TTL to Fabric Ontology definition without uploading."""
    logger = logging.getLogger(__name__)
    setup_logging()
    
    ttl_file = args.ttl_file
    if not os.path.exists(ttl_file):
        print(f"Error: TTL file not found: {ttl_file}")
        sys.exit(1)
    
    print(f"Converting TTL file: {ttl_file}")
    
    try:
        with open(ttl_file, 'r', encoding='utf-8') as f:
            ttl_content = f.read()
    except UnicodeDecodeError as e:
        print(f"Error: Failed to read TTL file due to encoding issue: {e}")
        print("Try converting the file to UTF-8 encoding")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading TTL file: {e}")
        sys.exit(1)
    
    force_memory = getattr(args, 'force_memory', False)
    
    try:
        definition, ontology_name = parse_ttl_content(ttl_content, force_large_file=force_memory)
    except ValueError as e:
        print(f"Error: Invalid RDF/TTL content: {e}")
        sys.exit(1)
    except MemoryError as e:
        print(f"\nError: {e}")
        print("\nTip: Use --force-memory to bypass memory safety checks (use with caution).")
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing TTL file: {e}")
        sys.exit(1)
    
    output = {
        "displayName": ontology_name,
        "description": f"Converted from {os.path.basename(ttl_file)}",
        "definition": definition,
    }
    
    if args.output:
        output_path = args.output
    else:
        output_path = str(Path(ttl_file).with_suffix('.json'))
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, indent=2, fp=f)
    except PermissionError:
        print(f"Error: Permission denied writing to {output_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)
    
    print(f"Saved Fabric Ontology definition to: {output_path}")
    print(f"Ontology Name: {ontology_name}")
    print(f"Definition Parts: {len(definition['parts'])}")


def cmd_export(args):
    """Export an ontology from Fabric to TTL format."""
    # Setup logging using config if available
    config_path = args.config or get_default_config_path()
    if os.path.exists(config_path):
        config_data = load_config(config_path)
        log_config = config_data.get('logging', {})
        setup_logging(level=log_config.get('level', 'INFO'), log_file=log_config.get('file'))
    else:
        setup_logging()
    logger = logging.getLogger(__name__)

    # Load Fabric configuration from file
    config_file = args.config or get_default_config_path()
    try:
        fabric_config = FabricConfig.from_file(config_file)
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_file}")
        logger.error("Create config.json with your Azure credentials (see config.sample.json)")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    client = FabricOntologyClient(fabric_config)
    ontology_id = args.ontology_id
    
    print(f"Exporting ontology {ontology_id} to TTL format...")
    
    try:
        # Get ontology with definition
        ontology_info = client.get_ontology(ontology_id)
        definition = client.get_ontology_definition(ontology_id)
        
        if not definition:
            print("Error: Failed to get ontology definition")
            sys.exit(1)
        
        # Prepare Fabric definition structure
        fabric_definition = {
            "displayName": ontology_info.get("displayName", "exported_ontology"),
            "description": ontology_info.get("description", ""),
            "definition": definition
        }
        
        # Convert to TTL
        converter = FabricToTTLConverter()
        ttl_content = converter.convert(fabric_definition)
        
        # Determine output path
        if args.output:
            output_path = args.output
        else:
            safe_name = ontology_info.get("displayName", ontology_id).replace(" ", "_")
            output_path = f"{safe_name}_exported.ttl"
        
        # Write TTL file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ttl_content)
        
        print(f"Successfully exported ontology to: {output_path}")
        print(f"Ontology Name: {ontology_info.get('displayName', 'Unknown')}")
        print(f"Parts in definition: {len(definition.get('parts', []))}")
        
    except FabricAPIError as e:
        logger.error(f"API Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Export failed: {e}")
        sys.exit(1)


def cmd_compare(args):
    """Compare two TTL files for semantic equivalence."""
    setup_logging()
    
    ttl_file1 = args.ttl_file1
    ttl_file2 = args.ttl_file2
    
    # Validate files exist
    for ttl_file in [ttl_file1, ttl_file2]:
        if not os.path.isfile(ttl_file):
            print(f"Error: TTL file not found: {ttl_file}")
            sys.exit(1)
    
    try:
        with open(ttl_file1, 'r', encoding='utf-8') as f:
            ttl_content1 = f.read()
        with open(ttl_file2, 'r', encoding='utf-8') as f:
            ttl_content2 = f.read()
    except Exception as e:
        print(f"Error reading TTL files: {e}")
        sys.exit(1)
    
    print(f"Comparing:")
    print(f"  File 1: {ttl_file1}")
    print(f"  File 2: {ttl_file2}")
    print()
    
    comparison = compare_ontologies(ttl_content1, ttl_content2)
    
    if comparison["is_equivalent"]:
        print("✓ Ontologies are semantically EQUIVALENT")
    else:
        print("✗ Ontologies are NOT equivalent")
    
    print()
    print(f"Classes: {comparison['classes']['count1']} vs {comparison['classes']['count2']}")
    if comparison['classes']['only_in_first']:
        print(f"  Only in file 1: {comparison['classes']['only_in_first']}")
    if comparison['classes']['only_in_second']:
        print(f"  Only in file 2: {comparison['classes']['only_in_second']}")
    
    print(f"Datatype Properties: {comparison['datatype_properties']['count1']} vs {comparison['datatype_properties']['count2']}")
    if comparison['datatype_properties']['only_in_first']:
        print(f"  Only in file 1: {comparison['datatype_properties']['only_in_first']}")
    if comparison['datatype_properties']['only_in_second']:
        print(f"  Only in file 2: {comparison['datatype_properties']['only_in_second']}")
    
    print(f"Object Properties: {comparison['object_properties']['count1']} vs {comparison['object_properties']['count2']}")
    if comparison['object_properties']['only_in_first']:
        print(f"  Only in file 1: {comparison['object_properties']['only_in_first']}")
    if comparison['object_properties']['only_in_second']:
        print(f"  Only in file 2: {comparison['object_properties']['only_in_second']}")
    
    if args.verbose:
        print()
        print("Detailed comparison results:")
        print(json.dumps(comparison, indent=2))
    
    sys.exit(0 if comparison["is_equivalent"] else 1)


def cmd_roundtrip(args):
    """Test round-trip conversion: TTL -> Fabric -> TTL and compare."""
    # Setup logging using config if available
    config_path = args.config or get_default_config_path()
    if os.path.exists(config_path):
        config_data = load_config(config_path)
        log_config = config_data.get('logging', {})
        setup_logging(level=log_config.get('level', 'INFO'), log_file=log_config.get('file'))
    else:
        setup_logging()
    logger = logging.getLogger(__name__)
    
    ttl_file = args.ttl_file
    
    if not os.path.isfile(ttl_file):
        print(f"Error: TTL file not found: {ttl_file}")
        sys.exit(1)
    
    config = None
    config_file = args.config or get_default_config_path()
    if args.upload:
        try:
            config = FabricConfig.from_file(config_file)
        except FileNotFoundError:
            # If no config, do offline round-trip (without Fabric upload)
            config = None
            print("Note: No config found. Running offline round-trip test (TTL -> JSON -> TTL).")
        except ValueError as e:
            logger.error(f"Invalid configuration: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
    
    try:
        with open(ttl_file, 'r', encoding='utf-8') as f:
            original_ttl = f.read()
    except Exception as e:
        print(f"Error reading TTL file: {e}")
        sys.exit(1)
    
    print(f"Running round-trip test for: {ttl_file}")
    print()
    
    if config and args.upload:
        # Full round-trip with Fabric
        client = FabricOntologyClient(config)
        
        # Generate unique name
        import uuid
        test_name = f"RoundTrip_Test_{uuid.uuid4().hex[:8]}"
        
        print(f"1. Uploading to Fabric as '{test_name}'...")
        
        try:
            # Parse and upload
            definition, ontology_name = parse_ttl_content(original_ttl)
            ontology_id = client.create_ontology(
                display_name=test_name,
                definition={"parts": definition["parts"]},
                description="Round-trip test ontology"
            )
            print(f"   Created ontology ID: {ontology_id}")
            
            print("2. Fetching definition from Fabric...")
            fetched_def = client.get_ontology_definition(ontology_id)
            
            print("3. Converting back to TTL...")
            fabric_definition = {
                "displayName": test_name,
                "definition": fetched_def
            }
            converter = FabricToTTLConverter()
            exported_ttl = converter.convert(fabric_definition)
            
            print("4. Comparing original and exported TTL...")
            comparison = compare_ontologies(original_ttl, exported_ttl)
            
            if args.cleanup:
                print("5. Cleaning up - deleting test ontology...")
                client.delete_ontology(ontology_id)
                print("   Deleted test ontology")
            else:
                print(f"5. Test ontology retained: {ontology_id}")
            
        except Exception as e:
            logger.error(f"Round-trip test failed: {e}")
            sys.exit(1)
    else:
        # Offline round-trip
        print("1. Parsing original TTL...")
        definition, ontology_name = parse_ttl_content(original_ttl)
        print(f"   Found {len(definition['parts'])} parts")
        
        print("2. Creating Fabric definition structure...")
        fabric_definition = {
            "displayName": ontology_name,
            "definition": definition
        }
        
        print("3. Converting back to TTL...")
        converter = FabricToTTLConverter()
        exported_ttl = converter.convert(fabric_definition)
        
        print("4. Comparing original and exported TTL...")
        comparison = compare_ontologies(original_ttl, exported_ttl)
    
    # Save exported TTL if requested
    if args.save_export:
        export_path = str(Path(ttl_file).with_suffix('.exported.ttl'))
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write(exported_ttl)
        print(f"   Saved exported TTL to: {export_path}")
    
    print()
    if comparison["is_equivalent"]:
        print("✓ ROUND-TRIP SUCCESS: Ontologies are semantically equivalent")
    else:
        print("✗ ROUND-TRIP FAILED: Ontologies differ")
        
        if comparison['classes']['only_in_first'] or comparison['classes']['only_in_second']:
            print(f"  Classes: Lost {comparison['classes']['only_in_first']}, Gained {comparison['classes']['only_in_second']}")
        if comparison['datatype_properties']['only_in_first'] or comparison['datatype_properties']['only_in_second']:
            print(f"  Datatype Props: Lost {comparison['datatype_properties']['only_in_first']}, Gained {comparison['datatype_properties']['only_in_second']}")
        if comparison['object_properties']['only_in_first'] or comparison['object_properties']['only_in_second']:
            print(f"  Object Props: Lost {comparison['object_properties']['only_in_first']}, Gained {comparison['object_properties']['only_in_second']}")
    
    sys.exit(0 if comparison["is_equivalent"] else 1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="RDF TTL to Microsoft Fabric Ontology Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s upload samples\\sample_ontology.ttl
    %(prog)s upload my_ontology.ttl --name MyOntology --update
    %(prog)s list
    %(prog)s get 12345678-1234-1234-1234-123456789012
    %(prog)s convert samples\\sample_ontology.ttl --output fabric_definition.json
    %(prog)s export 12345678-1234-1234-1234-123456789012 --output exported.ttl
    %(prog)s compare original.ttl exported.ttl
    %(prog)s roundtrip samples\\sample_ontology.ttl --save-export
    %(prog)s roundtrip samples\\sample_ontology.ttl --upload --cleanup
    %(prog)s test
        """,
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate command (NEW)
    validate_parser = subparsers.add_parser('validate', help='Validate a TTL file for Fabric compatibility')
    validate_parser.add_argument('ttl_file', help='Path to the TTL file to validate')
    validate_parser.add_argument('--output', '-o', help='Output JSON report file path')
    validate_parser.add_argument('--save-report', '-s', action='store_true',
                                 help='Save detailed report to <ttl_file>.validation.json')
    validate_parser.add_argument('--verbose', '-v', action='store_true',
                                 help='Show detailed human-readable report')
    validate_parser.set_defaults(func=cmd_validate)
    
    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload a TTL file to Fabric Ontology')
    upload_parser.add_argument('ttl_file', help='Path to the TTL file to upload')
    upload_parser.add_argument('--config', '-c', help='Path to configuration file')
    upload_parser.add_argument('--name', '-n', help='Override ontology name')
    upload_parser.add_argument('--description', '-d', help='Ontology description')
    upload_parser.add_argument('--update', '-u', action='store_true', 
                               help='Update if ontology with same name exists')
    upload_parser.add_argument('--skip-validation', action='store_true',
                               help='Skip pre-flight validation check')
    upload_parser.add_argument('--force', '-f', action='store_true',
                               help='Proceed with import even if validation issues are found')
    upload_parser.add_argument('--force-memory', action='store_true',
                               help='Skip memory safety checks for very large files (use with caution)')
    upload_parser.add_argument('--save-validation-report', action='store_true',
                               help='Save validation report even if import is cancelled')
    upload_parser.set_defaults(func=cmd_upload)
    
    # List command
    list_parser = subparsers.add_parser('list', help='List ontologies in the workspace')
    list_parser.add_argument('--config', '-c', help='Path to configuration file')
    list_parser.set_defaults(func=cmd_list)
    
    # Get command
    get_parser = subparsers.add_parser('get', help='Get ontology details')
    get_parser.add_argument('ontology_id', help='Ontology ID')
    get_parser.add_argument('--config', '-c', help='Path to configuration file')
    get_parser.add_argument('--with-definition', action='store_true',
                            help='Also fetch the ontology definition')
    get_parser.set_defaults(func=cmd_get)
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete an ontology')
    delete_parser.add_argument('ontology_id', help='Ontology ID')
    delete_parser.add_argument('--config', '-c', help='Path to configuration file')
    delete_parser.add_argument('--force', '-f', action='store_true',
                               help='Skip confirmation prompt')
    delete_parser.set_defaults(func=cmd_delete)
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test with sample ontology')
    test_parser.add_argument('--config', '-c', help='Path to configuration file')
    test_parser.add_argument('--upload-test', action='store_true',
                             help='Also upload the test ontology to Fabric')
    test_parser.set_defaults(func=cmd_test)
    
    # Convert command
    convert_parser = subparsers.add_parser('convert', help='Convert TTL to Fabric format without uploading')
    convert_parser.add_argument('ttl_file', help='Path to the TTL file to convert')
    convert_parser.add_argument('--output', '-o', help='Output JSON file path')
    convert_parser.add_argument('--force-memory', action='store_true',
                               help='Skip memory safety checks for very large files (use with caution)')
    convert_parser.set_defaults(func=cmd_convert)
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export ontology from Fabric to TTL format')
    export_parser.add_argument('ontology_id', help='Ontology ID to export')
    export_parser.add_argument('--config', '-c', help='Path to configuration file')
    export_parser.add_argument('--output', '-o', help='Output TTL file path')
    export_parser.set_defaults(func=cmd_export)
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two TTL files for semantic equivalence')
    compare_parser.add_argument('ttl_file1', help='First TTL file')
    compare_parser.add_argument('ttl_file2', help='Second TTL file')
    compare_parser.add_argument('--verbose', '-v', action='store_true',
                                help='Show detailed comparison results')
    compare_parser.set_defaults(func=cmd_compare)
    
    # Round-trip command
    roundtrip_parser = subparsers.add_parser('roundtrip', help='Test round-trip: TTL -> Fabric -> TTL')
    roundtrip_parser.add_argument('ttl_file', help='TTL file to test')
    roundtrip_parser.add_argument('--config', '-c', help='Path to configuration file')
    roundtrip_parser.add_argument('--upload', '-u', action='store_true',
                                  help='Actually upload to Fabric (otherwise offline test)')
    roundtrip_parser.add_argument('--cleanup', action='store_true',
                                  help='Delete test ontology after round-trip')
    roundtrip_parser.add_argument('--save-export', '-s', action='store_true',
                                  help='Save the exported TTL file')
    roundtrip_parser.set_defaults(func=cmd_roundtrip)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == '__main__':
    main()
