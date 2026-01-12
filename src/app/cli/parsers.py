"""
CLI argument parser configuration.

This module defines the argument parser structure for all CLI commands.
It centralizes all argument parsing logic and provides a clean interface
for the main entry point.

Unified Command Structure:
    - validate --format {rdf,dtdl,cdm} <path>
    - convert  --format {rdf,dtdl,cdm} <path>
    - upload   --format {rdf,dtdl,cdm} <path>
    - export   <ontology_id>  (RDF only)
    - list / get / delete / compare / test  (common commands)
"""

import argparse
from typing import Callable, Dict, Optional


# ============================================================================
# Shared Flag Group Builders
# ============================================================================

def add_input_flags(parser: argparse.ArgumentParser) -> None:
    """Add common input-related flags."""
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively search directories for files'
    )
    parser.add_argument(
        '--allow-relative-up',
        action='store_true',
        help="Permit '..' in path only if the resolved path stays within the current directory"
    )


def add_output_flags(parser: argparse.ArgumentParser) -> None:
    """Add common output-related flags."""
    parser.add_argument(
        '--output', '-o',
        help='Output file or directory path'
    )
    parser.add_argument(
        '--save-report', '-s',
        action='store_true',
        help='Save detailed report to <path>.validation.json or similar'
    )


def add_performance_flags(parser: argparse.ArgumentParser) -> None:
    """Add common performance/streaming flags."""
    parser.add_argument(
        '--streaming',
        action='store_true',
        help='Use streaming mode for large files (>100MB) - processes in batches'
    )
    parser.add_argument(
        '--force-memory',
        action='store_true',
        help='Skip memory safety checks for very large files (use with caution)'
    )


def add_validation_flags(parser: argparse.ArgumentParser) -> None:
    """Add common validation-related flags."""
    parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='Continue even if parse errors occur'
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip pre-flight validation check'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Proceed even if validation issues are found'
    )


def add_fabric_config_flags(parser: argparse.ArgumentParser) -> None:
    """Add Fabric configuration flags."""
    parser.add_argument(
        '--config', '-c',
        help='Path to configuration file'
    )


def add_format_flag(parser: argparse.ArgumentParser, required: bool = True) -> None:
    """Add the --format selector flag."""
    parser.add_argument(
        '--format',
        choices=['rdf', 'dtdl', 'cdm'],
        required=required,
        help='Input format: rdf (TTL/RDF/OWL/JSON-LD), dtdl (Digital Twins JSON), or cdm (Common Data Model)'
    )


def add_ontology_name_flags(parser: argparse.ArgumentParser) -> None:
    """Add ontology naming flags (unified --ontology-name with --name alias)."""
    parser.add_argument(
        '--ontology-name', '-n',
        dest='ontology_name',
        help='Name for the ontology'
    )
    parser.add_argument(
        '--description', '-d',
        help='Ontology description'
    )


def add_dtdl_specific_flags(parser: argparse.ArgumentParser) -> None:
    """Add DTDL-specific conversion flags."""
    parser.add_argument(
        '--namespace',
        default='usertypes',
        help='Namespace for entity types (default: usertypes)'
    )
    parser.add_argument(
        '--component-mode',
        choices=['skip', 'separate', 'flatten'],
        default='skip',
        help=(
            "How to handle DTDL components: 'skip' ignores them, 'separate' creates "
            "child entity types with relationships, 'flatten' inlines component "
            "properties into the parent."
        )
    )
    parser.add_argument(
        '--command-mode',
        choices=['skip', 'entity', 'property'],
        default='skip',
        help=(
            "How to handle DTDL commands: 'skip' ignores them, 'entity' creates "
            "Fabric CommandType entities, 'property' stores a serialized command "
            "definition as a string property."
        )
    )
    parser.add_argument(
        '--save-mapping',
        action='store_true',
        help='Save DTMI to Fabric ID mapping file'
    )


# ============================================================================
# Main Parser Factory
# ============================================================================

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
    # Validate ontology files
    %(prog)s validate --format rdf samples/sample_supply_chain_ontology.ttl --verbose
    %(prog)s validate --format dtdl models/ --recursive
    
    # Convert to Fabric format (without uploading)
    %(prog)s convert --format rdf ontology.ttl --output fabric_def.json
    %(prog)s convert --format dtdl models/ --ontology-name MyModel --save-mapping
    
    # Upload to Fabric
    %(prog)s upload --format rdf ontology.ttl --ontology-name MyOntology
    %(prog)s upload --format dtdl models/ --ontology-name MyDTDL --dry-run
    
    # Export from Fabric to TTL
    %(prog)s export 12345678-1234-1234-1234-123456789012 --output exported.ttl
    
    # Workspace commands
    %(prog)s list
    %(prog)s get 12345678-1234-1234-1234-123456789012
    %(prog)s delete 12345678-1234-1234-1234-123456789012 --force
    %(prog)s compare original.ttl exported.ttl
    %(prog)s test
        """,
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Unified commands
    _add_validate_parser(subparsers)
    _add_convert_parser(subparsers)
    _add_upload_parser(subparsers)
    _add_export_parser(subparsers)
    
    # Common commands (no format needed)
    _add_list_parser(subparsers)
    _add_get_parser(subparsers)
    _add_delete_parser(subparsers)
    _add_test_parser(subparsers)
    _add_compare_parser(subparsers)
    
    return parser


# ============================================================================
# Unified Command Parsers
# ============================================================================

def _add_validate_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the unified validate command parser."""
    parser = subparsers.add_parser(
        'validate',
        help='Validate ontology files (RDF or DTDL)'
    )
    parser.add_argument('path', help='Path to the file or directory to validate')
    add_format_flag(parser)
    add_input_flags(parser)
    add_output_flags(parser)
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed human-readable report'
    )
    parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='Continue validation even if parse errors occur'
    )


def _add_convert_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the unified convert command parser."""
    parser = subparsers.add_parser(
        'convert',
        help='Convert ontology files to Fabric format (without uploading)'
    )
    parser.add_argument('path', help='Path to the file or directory to convert')
    add_format_flag(parser)
    add_input_flags(parser)
    add_output_flags(parser)
    add_performance_flags(parser)
    add_ontology_name_flags(parser)
    add_dtdl_specific_flags(parser)


def _add_upload_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the unified upload command parser."""
    parser = subparsers.add_parser(
        'upload',
        help='Upload ontology to Microsoft Fabric'
    )
    parser.add_argument('path', help='Path to the file or directory to upload')
    add_format_flag(parser)
    add_input_flags(parser)
    add_output_flags(parser)
    add_performance_flags(parser)
    add_validation_flags(parser)
    add_fabric_config_flags(parser)
    add_ontology_name_flags(parser)
    add_dtdl_specific_flags(parser)
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Convert but do not upload (saves to file instead)'
    )
    parser.add_argument(
        '--update', '-u',
        action='store_true',
        help='Update if ontology with same name exists'
    )


def _add_export_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the export command parser (RDF only)."""
    parser = subparsers.add_parser(
        'export',
        help='Export ontology from Fabric to TTL format (RDF only)'
    )
    parser.add_argument('ontology_id', help='Ontology ID to export')
    add_fabric_config_flags(parser)
    parser.add_argument('--output', '-o', help='Output TTL file path')


# ============================================================================
# Common Command Parsers
# ============================================================================


def _add_list_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the list command parser."""
    parser = subparsers.add_parser(
        'list',
        help='List ontologies in the workspace'
    )
    add_fabric_config_flags(parser)


def _add_get_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the get command parser."""
    parser = subparsers.add_parser(
        'get',
        help='Get ontology details'
    )
    parser.add_argument('ontology_id', help='Ontology ID')
    add_fabric_config_flags(parser)
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
    add_fabric_config_flags(parser)
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
    add_fabric_config_flags(parser)
    parser.add_argument(
        '--upload-test',
        action='store_true',
        help='Also upload the test ontology to Fabric'
    )


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
