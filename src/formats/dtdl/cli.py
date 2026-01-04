"""
Legacy DTDL CLI entry point (deprecated).

This module intentionally raises an informative error to direct users to the
unified CLI commands under ``src/app/cli``. It is kept only to provide a
clear runtime message for anyone invoking ``python -m src.dtdl.cli``.
"""

raise ImportError(
    "The legacy 'src.dtdl.cli' entry point has been removed. Use the unified "
    "CLI commands (e.g., `python -m src.main convert --format dtdl ...`) instead."
)

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List

import logging

try:  # Prefer absolute import when running via src.main
    from cli.helpers import setup_logging
except ImportError:  # pragma: no cover - fallback when running as package
    from ..cli.helpers import setup_logging  # type: ignore

setup_logging()
logger = logging.getLogger(__name__)


def validate_command(args: argparse.Namespace) -> int:
    """
    Validate DTDL files/folders.
    
    Returns:
        0 on success, 1 on validation errors, 2 on parse errors
    """
    from .dtdl_parser import DTDLParser, ParseError
    from .dtdl_validator import DTDLValidator
    
    path = Path(args.path)
    parser = DTDLParser()
    validator = DTDLValidator()
    
    logger.info(f"Validating DTDL at: {path}")
    
    try:
        if path.is_file():
            result = parser.parse_file(str(path))
        elif path.is_dir():
            result = parser.parse_directory(str(path), recursive=args.recursive)
        else:
            logger.error(f"Path does not exist: {path}")
            return 2
    except ParseError as e:
        logger.error(f"Parse error: {e}")
        return 2
    except Exception as e:
        logger.error(f"Unexpected error parsing: {e}")
        return 2
    
    if result.errors:
        logger.error(f"Found {len(result.errors)} parse errors:")
        for error in result.errors:
            logger.error(f"  - {error}")
        if not args.continue_on_error:
            return 2
    
    logger.info(f"Parsed {len(result.interfaces)} interfaces")
    
    # Validate
    validation_result = validator.validate(result.interfaces)
    
    if validation_result.errors:
        logger.error(f"Found {len(validation_result.errors)} validation errors:")
        for error in validation_result.errors:
            logger.error(f"  - [{error.level.value}] {error.dtmi}: {error.message}")
        return 1
    
    if validation_result.warnings:
        logger.warning(f"Found {len(validation_result.warnings)} warnings:")
        for warning in validation_result.warnings:
            logger.warning(f"  - {warning.dtmi}: {warning.message}")
    
    logger.info("Validation successful!")
    
    if args.verbose:
        for interface in result.interfaces:
            logger.info(f"  Interface: {interface.dtmi}")
            logger.info(f"    Properties: {len(interface.properties)}")
            logger.info(f"    Telemetries: {len(interface.telemetries)}")
            logger.info(f"    Relationships: {len(interface.relationships)}")
            logger.info(f"    Components: {len(interface.components)}")
            logger.info(f"    Commands: {len(interface.commands)}")
    
    return 0


def convert_command(args: argparse.Namespace) -> int:
    """
    Convert DTDL to Fabric Ontology JSON format.
    
    Returns:
        0 on success, 1 on conversion errors, 2 on parse errors
    """
    from .dtdl_parser import DTDLParser
    from .dtdl_validator import DTDLValidator
    from .dtdl_converter import DTDLToFabricConverter
    
    path = Path(args.path)
    use_streaming = getattr(args, 'streaming', False)
    force_memory = getattr(args, 'force_memory', False)
    
    # Check file size for streaming suggestion
    if path.is_file():
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > 100 and not use_streaming and not force_memory:
            logger.warning(f"Large file detected ({file_size_mb:.1f} MB). Consider using --streaming.")
    
    logger.info(f"Converting DTDL at: {path}")
    
    # Use streaming mode if requested
    if use_streaming:
        return _convert_with_streaming(args, path)
    
    parser = DTDLParser()
    validator = DTDLValidator()
    converter = DTDLToFabricConverter(
        namespace=args.namespace,
        flatten_components=args.flatten_components,
        include_commands=args.include_commands,
    )
    
    # Parse
    try:
        if path.is_file():
            result = parser.parse_file(str(path))
        else:
            result = parser.parse_directory(str(path), recursive=args.recursive)
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return 2
    
    if result.errors and not args.skip_validation:
        logger.error(f"Parse errors found. Use --skip-validation to proceed anyway.")
        return 2
    
    # Validate (unless skipped)
    if not args.skip_validation:
        validation_result = validator.validate(result.interfaces)
        if validation_result.errors:
            logger.error(f"Validation errors found. Use --skip-validation to proceed anyway.")
            return 1
    
    # Convert
    logger.info(f"Converting {len(result.interfaces)} interfaces...")
    conversion_result = converter.convert(result.interfaces)
    
    # Generate output
    output_path = Path(args.output) if args.output else Path("fabric_ontology.json")
    
    definition = converter.to_fabric_definition(
        conversion_result,
        ontology_name=args.ontology_name or path.stem
    )
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(definition, f, indent=2)
    
    logger.info(f"Conversion complete!")
    logger.info(f"  Entity types: {len(conversion_result.entity_types)}")
    logger.info(f"  Relationship types: {len(conversion_result.relationship_types)}")
    logger.info(f"  Skipped items: {len(conversion_result.skipped_items)}")
    logger.info(f"  Output: {output_path}")
    
    # Save DTMI mapping for reference
    if args.save_mapping:
        mapping_path = output_path.with_suffix('.mapping.json')
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(converter.get_dtmi_mapping(), f, indent=2)
        logger.info(f"  DTMI mapping saved to: {mapping_path}")
    
    return 0


def _convert_with_streaming(args: argparse.Namespace, path: Path) -> int:
    """
    Convert DTDL files using streaming mode for memory efficiency.
    
    Args:
        args: Command arguments
        path: Path to DTDL file or directory
        
    Returns:
        0 on success, non-zero on error
    """
    try:
        from ..core.streaming import (
            StreamingEngine,
            DTDLStreamReader,
            DTDLChunkProcessor,
            StreamConfig,
        )
    except ImportError:
        try:
            from core.streaming import (
                StreamingEngine,
                DTDLStreamReader,
                DTDLChunkProcessor,
                StreamConfig,
            )
        except ImportError:
            logger.error("Streaming module not available. Try without --streaming.")
            return 1
    
    logger.info("Using streaming mode for conversion...")
    
    # Configure streaming
    config = StreamConfig(
        chunk_size=10000,
        memory_threshold_mb=100.0,
        enable_progress=True,
    )
    
    # Create streaming engine
    engine = StreamingEngine(
        reader=DTDLStreamReader(),
        processor=DTDLChunkProcessor(
            namespace=args.namespace,
            flatten_components=args.flatten_components,
        ),
        config=config
    )
    
    def progress_callback(items_processed: int) -> None:
        if items_processed % 1000 == 0:
            logger.info(f"  Processed {items_processed:,} items...")
    
    try:
        result = engine.process_file(
            str(path),
            progress_callback=progress_callback
        )
        
        if not result.success:
            logger.error(f"Streaming conversion failed: {result.error}")
            return 1
        
        # Generate output
        output_path = Path(args.output) if args.output else Path("fabric_ontology.json")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result.data, f, indent=2)
        
        logger.info(f"Streaming conversion complete!")
        logger.info(result.stats.get_summary())
        logger.info(f"  Output: {output_path}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Streaming conversion error: {e}")
        return 1


def upload_command(args: argparse.Namespace) -> int:
    """
    Upload converted DTDL definition to Fabric Ontology.
    
    Returns:
        0 on success, 1 on upload errors
    """
    # Import Fabric client
    try:
        from ..core.platform.fabric_client import FabricOntologyClient
    except ImportError:
        try:
            from core.platform.fabric_client import FabricOntologyClient
        except ImportError:
            logger.error("Could not import FabricOntologyClient. Ensure platform/fabric_client.py is available.")
            return 1
    
    definition_path = Path(args.definition)
    if not definition_path.exists():
        logger.error(f"Definition file not found: {definition_path}")
        return 1
    
    with open(definition_path, 'r', encoding='utf-8') as f:
        definition = json.load(f)
    
    logger.info(f"Uploading to Fabric Ontology: {args.ontology_name}")
    
    # Initialize client
    client = FabricOntologyClient(
        workspace_id=args.workspace_id,
        verbose=args.verbose,
    )
    
    try:
        if args.update_existing:
            # Try to find and update existing ontology
            ontologies = client.list_ontologies()
            existing = next(
                (o for o in ontologies if o.get('displayName') == args.ontology_name),
                None
            )
            
            if existing:
                ontology_id = existing['id']
                logger.info(f"Updating existing ontology: {ontology_id}")
                client.update_ontology_definition(ontology_id, definition)
            else:
                logger.info("Creating new ontology (no existing match found)")
                ontology_id = client.create_ontology(args.ontology_name, definition)
        else:
            ontology_id = client.create_ontology(args.ontology_name, definition)
        
        logger.info(f"Upload successful! Ontology ID: {ontology_id}")
        return 0
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return 1


def import_command(args: argparse.Namespace) -> int:
    """
    Combined validate + convert + upload.
    
    Returns:
        0 on success, non-zero on errors
    """
    from .dtdl_parser import DTDLParser
    from .dtdl_validator import DTDLValidator
    from .dtdl_converter import DTDLToFabricConverter
    
    path = Path(args.path)
    use_streaming = getattr(args, 'streaming', False)
    force_memory = getattr(args, 'force_memory', False)
    
    logger.info(f"=== DTDL Import: {path} ===")
    
    # Check file size for streaming suggestion
    if path.is_file():
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > 100 and not use_streaming and not force_memory:
            logger.warning(f"Large file detected ({file_size_mb:.1f} MB). Consider using --streaming.")
    
    # Use streaming mode if requested
    if use_streaming:
        return _import_with_streaming(args, path)
    
    # Step 1: Parse
    logger.info("Step 1: Parsing DTDL files...")
    parser = DTDLParser()
    
    try:
        if path.is_file():
            result = parser.parse_file(str(path))
        else:
            result = parser.parse_directory(str(path), recursive=args.recursive)
    except Exception as e:
        logger.error(f"Parse failed: {e}")
        return 2
    
    if result.errors:
        logger.error(f"Parse errors: {len(result.errors)}")
        for error in result.errors[:5]:  # Show first 5
            logger.error(f"  - {error}")
        return 2
    
    logger.info(f"  Parsed {len(result.interfaces)} interfaces")
    
    # Step 2: Validate
    logger.info("Step 2: Validating...")
    validator = DTDLValidator()
    validation_result = validator.validate(result.interfaces)
    
    if validation_result.errors:
        logger.error(f"Validation errors: {len(validation_result.errors)}")
        for error in validation_result.errors[:5]:
            logger.error(f"  - {error.message}")
        return 1
    
    logger.info("  Validation passed")
    
    # Step 3: Convert
    logger.info("Step 3: Converting to Fabric format...")
    converter = DTDLToFabricConverter(
        namespace=args.namespace or "usertypes",
        flatten_components=args.flatten_components,
    )
    
    conversion_result = converter.convert(result.interfaces)
    definition = converter.to_fabric_definition(
        conversion_result,
        ontology_name=args.ontology_name or path.stem
    )
    
    logger.info(f"  Converted {len(conversion_result.entity_types)} entity types")
    logger.info(f"  Converted {len(conversion_result.relationship_types)} relationship types")
    
    # Step 4: Upload (if not dry-run)
    if args.dry_run:
        logger.info("Step 4: Dry run - skipping upload")
        
        # Save to file instead
        output_path = Path(args.output or f"{args.ontology_name or path.stem}_fabric.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(definition, f, indent=2)
        logger.info(f"  Definition saved to: {output_path}")
    else:
        logger.info("Step 4: Uploading to Fabric...")
        
        try:
            from ..core.platform.fabric_client import FabricOntologyClient, FabricConfig
        except ImportError:
            try:
                from core.platform.fabric_client import FabricOntologyClient, FabricConfig
            except ImportError:
                logger.error("Could not import FabricOntologyClient")
                return 1
        
        # Load config from file
        config_path = args.config if hasattr(args, 'config') and args.config else str(Path(__file__).parent.parent / "config.json")
        try:
            config = FabricConfig.from_file(config_path)
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            logger.error("Please create a config.json file with your Fabric workspace settings")
            return 1
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return 1
        
        client = FabricOntologyClient(config)
        
        try:
            result = client.create_ontology(
                display_name=args.ontology_name or path.stem,
                description=f"Imported from DTDL: {path.name}",
                definition=definition
            )
            ontology_id = result.get('id') if isinstance(result, dict) else result
            logger.info(f"  Upload successful! Ontology ID: {ontology_id}")
        except Exception as e:
            logger.error(f"  Upload failed: {e}")
            return 1
    
    logger.info("=== Import complete ===")
    return 0


def _import_with_streaming(args: argparse.Namespace, path: Path) -> int:
    """
    Import DTDL files using streaming mode for memory efficiency.
    
    Args:
        args: Command arguments
        path: Path to DTDL file or directory
        
    Returns:
        0 on success, non-zero on error
    """
    try:
        from ..core.streaming import (
            StreamingEngine,
            DTDLStreamReader,
            DTDLChunkProcessor,
            StreamConfig,
        )
    except ImportError:
        try:
            from core.streaming import (
                StreamingEngine,
                DTDLStreamReader,
                DTDLChunkProcessor,
                StreamConfig,
            )
        except ImportError:
            logger.error("Streaming module not available. Try without --streaming.")
            return 1
    
    logger.info("Using streaming mode for import...")
    
    # Configure streaming
    config = StreamConfig(
        chunk_size=10000,
        memory_threshold_mb=100.0,
        enable_progress=True,
    )
    
    # Create streaming engine
    engine = StreamingEngine(
        reader=DTDLStreamReader(),
        processor=DTDLChunkProcessor(
            namespace=getattr(args, 'namespace', 'usertypes') or 'usertypes',
            flatten_components=getattr(args, 'flatten_components', False),
        ),
        config=config
    )
    
    def progress_callback(items_processed: int) -> None:
        if items_processed % 1000 == 0:
            logger.info(f"  Processed {items_processed:,} items...")
    
    try:
        result = engine.process_file(
            str(path),
            progress_callback=progress_callback
        )
        
        if not result.success:
            logger.error(f"Streaming conversion failed: {result.error}")
            return 1
        
        definition = result.data
        logger.info(f"Streaming conversion complete!")
        logger.info(result.stats.get_summary())
        
    except Exception as e:
        logger.error(f"Streaming conversion error: {e}")
        return 1
    
    # Handle dry-run or upload
    if getattr(args, 'dry_run', False):
        logger.info("Dry run - skipping upload")
        output_path = Path(args.output or f"{args.ontology_name or path.stem}_fabric.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(definition, f, indent=2)
        logger.info(f"  Definition saved to: {output_path}")
    else:
        logger.info("Uploading to Fabric...")
        
        try:
            from ..core.platform.fabric_client import FabricOntologyClient, FabricConfig
        except ImportError:
            try:
                from core.platform.fabric_client import FabricOntologyClient, FabricConfig
            except ImportError:
                logger.error("Could not import FabricOntologyClient")
                return 1
        
        config_path = args.config if hasattr(args, 'config') and args.config else str(Path(__file__).parent.parent / "config.json")
        try:
            fabric_config = FabricConfig.from_file(config_path)
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            return 1
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return 1
        
        client = FabricOntologyClient(fabric_config)
        
        try:
            result = client.create_ontology(
                display_name=args.ontology_name or path.stem,
                description=f"Imported from DTDL: {path.name}",
                definition=definition
            )
            ontology_id = result.get('id') if isinstance(result, dict) else result
            logger.info(f"  Upload successful! Ontology ID: {ontology_id}")
        except Exception as e:
            logger.error(f"  Upload failed: {e}")
            return 1
    
    logger.info("=== Import complete ===")
    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog='dtdl-cli',
        description='DTDL to Microsoft Fabric Ontology import tools'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # dtdl-validate command
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate DTDL files/folders'
    )
    validate_parser.add_argument(
        'path',
        help='Path to DTDL file or directory'
    )
    validate_parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively process subdirectories'
    )
    validate_parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='Continue validation even with parse errors'
    )
    
    # dtdl-convert command
    convert_parser = subparsers.add_parser(
        'convert',
        help='Convert DTDL to Fabric Ontology JSON'
    )
    convert_parser.add_argument(
        'path',
        help='Path to DTDL file or directory'
    )
    convert_parser.add_argument(
        '--output', '-o',
        help='Output file path (default: fabric_ontology.json)'
    )
    convert_parser.add_argument(
        '--ontology-name', '-n',
        help='Name for the ontology'
    )
    convert_parser.add_argument(
        '--namespace',
        default='usertypes',
        help='Namespace for entity types'
    )
    convert_parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively process subdirectories'
    )
    convert_parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip validation step'
    )
    convert_parser.add_argument(
        '--include-commands',
        action='store_true',
        help='Include commands as properties'
    )
    convert_parser.add_argument(
        '--save-mapping',
        action='store_true',
        help='Save DTMI to Fabric ID mapping file'
    )
    convert_parser.add_argument(
        '--streaming', '-s',
        action='store_true',
        help='Use streaming mode for large files (>100MB)'
    )
    convert_parser.add_argument(
        '--force-memory',
        action='store_true',
        help='Skip memory safety checks'
    )
    
    # dtdl-upload command
    upload_parser = subparsers.add_parser(
        'upload',
        help='Upload definition to Fabric Ontology'
    )
    upload_parser.add_argument(
        'definition',
        help='Path to Fabric definition JSON file'
    )
    upload_parser.add_argument(
        '--ontology-name', '-n',
        required=True,
        help='Name for the ontology'
    )
    upload_parser.add_argument(
        '--workspace-id', '-w',
        help='Fabric workspace ID'
    )
    upload_parser.add_argument(
        '--update-existing', '-u',
        action='store_true',
        help='Update existing ontology if found'
    )
    
    # dtdl-import command (combined)
    import_parser = subparsers.add_parser(
        'import',
        help='Validate, convert, and upload DTDL to Fabric'
    )
    import_parser.add_argument(
        'path',
        help='Path to DTDL file or directory'
    )
    import_parser.add_argument(
        '--ontology-name', '-n',
        help='Name for the ontology'
    )
    import_parser.add_argument(
        '--namespace',
        default='usertypes',
        help='Namespace for entity types'
    )
    import_parser.add_argument(
        '--workspace-id', '-w',
        help='Fabric workspace ID'
    )
    import_parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively process subdirectories'
    )
    import_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate and convert only, do not upload'
    )
    import_parser.add_argument(
        '--output', '-o',
        help='Output file path for dry-run mode'
    )
    import_parser.add_argument(
        '--config', '-c',
        help='Path to config.json file (default: src/config.json)'
    )
    import_parser.add_argument(
        '--streaming', '-s',
        action='store_true',
        help='Use streaming mode for large files (>100MB)'
    )
    import_parser.add_argument(
        '--force-memory',
        action='store_true',
        help='Skip memory safety checks'
    )
    
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.command == 'validate':
        return validate_command(args)
    elif args.command == 'convert':
        return convert_command(args)
    elif args.command == 'upload':
        return upload_command(args)
    elif args.command == 'import':
        return import_command(args)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
