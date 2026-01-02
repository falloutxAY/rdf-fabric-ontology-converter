"""
CLI argument parser configuration.

This module defines the argument parser structure for all CLI commands.
It centralizes all argument parsing logic and provides a clean interface
for the main entry point.

Command Naming Convention:
    - RDF commands: rdf-validate, rdf-convert, rdf-upload, rdf-export
    - DTDL commands: dtdl-validate, dtdl-convert, dtdl-upload
"""

import argparse
from typing import Callable, Dict, Optional


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create and configure the main argument parser.
    
    Returns:
        Configured ArgumentParser with all subcommands.
    """
    parser = argparse.ArgumentParser(
        description="RDF/DTDL to Microsoft Fabric Ontology Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # RDF/TTL Commands (use rdf- prefix)
    %(prog)s rdf-upload samples\\sample_supply_chain_ontology.ttl
    %(prog)s rdf-upload my_ontology.ttl --name MyOntology --update
    %(prog)s rdf-validate samples\\sample_foaf_ontology.ttl --verbose
    %(prog)s rdf-convert samples\\sample_supply_chain_ontology.ttl --output fabric_definition.json
    %(prog)s rdf-export 12345678-1234-1234-1234-123456789012 --output exported.ttl
    
    # DTDL Commands (use dtdl- prefix)
    %(prog)s dtdl-validate models/ --recursive
    %(prog)s dtdl-convert models/ --output fabric_definition.json
    %(prog)s dtdl-upload models/ --ontology-name MyDTDL
    
    # Other Commands
    %(prog)s list
    %(prog)s get 12345678-1234-1234-1234-123456789012
    %(prog)s compare original.ttl exported.ttl
    %(prog)s test
        """,
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add RDF subparsers
    _add_rdf_validate_parser(subparsers)
    _add_rdf_upload_parser(subparsers)
    _add_rdf_convert_parser(subparsers)
    _add_rdf_export_parser(subparsers)
    
    # Add common commands (no prefix needed)
    _add_list_parser(subparsers)
    _add_get_parser(subparsers)
    _add_delete_parser(subparsers)
    _add_test_parser(subparsers)
    _add_compare_parser(subparsers)
    
    # DTDL commands
    _add_dtdl_validate_parser(subparsers)
    _add_dtdl_convert_parser(subparsers)
    _add_dtdl_upload_parser(subparsers)
    
    return parser


def _add_rdf_validate_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the rdf-validate command parser."""
    parser = subparsers.add_parser(
        'rdf-validate',
        help='Validate a TTL file for Fabric compatibility'
    )
    _configure_validate_parser(parser)


def _configure_validate_parser(parser: argparse.ArgumentParser) -> None:
    """Configure common arguments for validate command."""
    parser.add_argument('ttl_file', help='Path to the TTL file or directory to validate')
    parser.add_argument(
        '--output', '-o',
        help='Output JSON report file path'
    )
    parser.add_argument(
        '--save-report', '-s',
        action='store_true',
        help='Save detailed report to <ttl_file>.validation.json'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed human-readable report'
    )
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively search directories for TTL files'
    )
    parser.add_argument(
        '--allow-relative-up',
        action='store_true',
        help="Permit '..' in path only if the resolved path stays within the current directory"
    )


def _add_rdf_upload_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the rdf-upload command parser."""
    parser = subparsers.add_parser(
        'rdf-upload',
        help='Upload a TTL file to Fabric Ontology'
    )
    _configure_upload_parser(parser)


def _configure_upload_parser(parser: argparse.ArgumentParser) -> None:
    """Configure common arguments for upload command."""
    parser.add_argument('ttl_file', help='Path to the TTL file or directory to upload')
    parser.add_argument('--config', '-c', help='Path to configuration file')
    parser.add_argument('--name', '-n', help='Override ontology name')
    parser.add_argument('--description', '-d', help='Ontology description')
    parser.add_argument(
        '--update', '-u',
        action='store_true',
        help='Update if ontology with same name exists'
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip pre-flight validation check'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Proceed with import even if validation issues are found'
    )
    parser.add_argument(
        '--streaming', '-s',
        action='store_true',
        help='Use streaming mode for large files (>100MB) - processes in batches'
    )
    parser.add_argument(
        '--force-memory',
        action='store_true',
        help='Skip memory safety checks for very large files (use with caution)'
    )
    parser.add_argument(
        '--save-validation-report',
        action='store_true',
        help='Save validation report even if import is cancelled'
    )
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively search directories for TTL files (batch upload)'
    )
    parser.add_argument(
        '--allow-relative-up',
        action='store_true',
        help="Permit '..' in path only if the resolved path stays within the current directory"
    )


def _add_list_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the list command parser."""
    parser = subparsers.add_parser(
        'list',
        help='List ontologies in the workspace'
    )
    parser.add_argument('--config', '-c', help='Path to configuration file')


def _add_get_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the get command parser."""
    parser = subparsers.add_parser(
        'get',
        help='Get ontology details'
    )
    parser.add_argument('ontology_id', help='Ontology ID')
    parser.add_argument('--config', '-c', help='Path to configuration file')
    parser.add_argument(
        '--with-definition',
        action='store_true',
        help='Also fetch the ontology definition'
    )


def _add_delete_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the delete command parser."""
    parser = subparsers.add_parser(
        'delete',
        help='Delete an ontology'
    )
    parser.add_argument('ontology_id', help='Ontology ID')
    parser.add_argument('--config', '-c', help='Path to configuration file')
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Skip confirmation prompt'
    )


def _add_test_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the test command parser."""
    parser = subparsers.add_parser(
        'test',
        help='Test with sample ontology'
    )
    parser.add_argument('--config', '-c', help='Path to configuration file')
    parser.add_argument(
        '--upload-test',
        action='store_true',
        help='Also upload the test ontology to Fabric'
    )


def _add_rdf_convert_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the rdf-convert command parser."""
    parser = subparsers.add_parser(
        'rdf-convert',
        help='Convert TTL to Fabric format without uploading'
    )
    _configure_convert_parser(parser)


def _configure_convert_parser(parser: argparse.ArgumentParser) -> None:
    """Configure common arguments for convert command."""
    parser.add_argument('ttl_file', help='Path to the TTL file or directory to convert')
    parser.add_argument('--output', '-o', help='Output JSON file path or directory')
    parser.add_argument(
        '--streaming', '-s',
        action='store_true',
        help='Use streaming mode for large files (>100MB) - processes in batches for lower memory usage'
    )
    parser.add_argument(
        '--force-memory',
        action='store_true',
        help='Skip memory safety checks for very large files (use with caution)'
    )
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively search directories for TTL files (batch conversion)'
    )
    parser.add_argument(
        '--allow-relative-up',
        action='store_true',
        help="Permit '..' in path only if the resolved path stays within the current directory"
    )


def _add_rdf_export_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the rdf-export command parser."""
    parser = subparsers.add_parser(
        'rdf-export',
        help='Export ontology from Fabric to TTL format'
    )
    _configure_export_parser(parser)


def _configure_export_parser(parser: argparse.ArgumentParser) -> None:
    """Configure common arguments for export command."""
    parser.add_argument('ontology_id', help='Ontology ID to export')
    parser.add_argument('--config', '-c', help='Path to configuration file')
    parser.add_argument('--output', '-o', help='Output TTL file path')


def _add_compare_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the compare command parser."""
    parser = subparsers.add_parser(
        'compare',
        help='Compare two TTL files for semantic equivalence'
    )
    parser.add_argument('ttl_file1', help='First TTL file')
    parser.add_argument('ttl_file2', help='Second TTL file')
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed comparison results'
    )
    parser.add_argument(
        '--allow-relative-up',
        action='store_true',
        help="Permit '..' in path only if the resolved path stays within the current directory"
    )


# ============================================================================
# DTDL Command Parsers
# ============================================================================

def _add_dtdl_validate_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the dtdl-validate command parser."""
    parser = subparsers.add_parser(
        'dtdl-validate',
        help='Validate DTDL files or directory'
    )
    parser.add_argument('path', help='Path to DTDL file or directory')
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively search directories for DTDL files'
    )
    parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='Continue validation even if parse errors occur'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed interface information'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output JSON report file path'
    )
    parser.add_argument(
        '--save-report', '-s',
        action='store_true',
        help='Save detailed report to <path>.validation.json'
    )


def _add_dtdl_convert_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the dtdl-convert command parser."""
    parser = subparsers.add_parser(
        'dtdl-convert',
        help='Convert DTDL to Fabric JSON format without uploading'
    )
    parser.add_argument('path', help='Path to DTDL file or directory')
    parser.add_argument(
        '--output', '-o',
        help='Output JSON file path (default: <ontology_name>_fabric.json)'
    )
    parser.add_argument(
        '--ontology-name', '-n',
        help='Name for the ontology (default: directory/file name)'
    )
    parser.add_argument(
        '--namespace',
        default='usertypes',
        help='Namespace for entity types (default: usertypes)'
    )
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively search directories for DTDL files'
    )
    parser.add_argument(
        '--flatten-components',
        action='store_true',
        help='Flatten component properties into parent entity'
    )
    parser.add_argument(
        '--save-mapping',
        action='store_true',
        help='Save DTMI to Fabric ID mapping file'
    )
    parser.add_argument(
        '--streaming', '-s',
        action='store_true',
        help='Use streaming mode for large files (>100MB)'
    )
    parser.add_argument(
        '--force-memory',
        action='store_true',
        help='Skip memory safety checks for very large files'
    )


def _add_dtdl_upload_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the dtdl-upload command parser (validate + convert + upload)."""
    parser = subparsers.add_parser(
        'dtdl-upload',
        help='Import DTDL models to Fabric Ontology (validate + convert + upload)'
    )
    _configure_dtdl_upload_parser(parser)


def _configure_dtdl_upload_parser(parser: argparse.ArgumentParser) -> None:
    """Configure common arguments for dtdl-upload command."""
    parser.add_argument('path', help='Path to DTDL file or directory')
    parser.add_argument('--config', '-c', help='Path to configuration file')
    parser.add_argument(
        '--ontology-name', '-n',
        help='Name for the ontology (default: directory/file name)'
    )
    parser.add_argument(
        '--namespace',
        default='usertypes',
        help='Namespace for entity types (default: usertypes)'
    )
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively search directories for DTDL files'
    )
    parser.add_argument(
        '--flatten-components',
        action='store_true',
        help='Flatten component properties into parent entity'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Convert but do not upload (saves to file instead)'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file path for dry-run mode'
    )
    parser.add_argument(
        '--streaming', '-s',
        action='store_true',
        help='Use streaming mode for large files (>100MB)'
    )
    parser.add_argument(
        '--force-memory',
        action='store_true',
        help='Skip memory safety checks for very large files'
    )
