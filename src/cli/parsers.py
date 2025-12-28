"""
CLI argument parser configuration.

This module defines the argument parser structure for all CLI commands.
It centralizes all argument parsing logic and provides a clean interface
for the main entry point.
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
        description="RDF TTL to Microsoft Fabric Ontology Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s upload samples\\sample_supply_chain_ontology.ttl
    %(prog)s upload my_ontology.ttl --name MyOntology --update
    %(prog)s validate samples\\sample_foaf_ontology.ttl --verbose
    %(prog)s list
    %(prog)s get 12345678-1234-1234-1234-123456789012
    %(prog)s convert samples\\sample_supply_chain_ontology.ttl --output fabric_definition.json
    %(prog)s export 12345678-1234-1234-1234-123456789012 --output exported.ttl
    %(prog)s compare original.ttl exported.ttl
    %(prog)s test
        """,
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add all subparsers
    _add_validate_parser(subparsers)
    _add_upload_parser(subparsers)
    _add_list_parser(subparsers)
    _add_get_parser(subparsers)
    _add_delete_parser(subparsers)
    _add_test_parser(subparsers)
    _add_convert_parser(subparsers)
    _add_export_parser(subparsers)
    _add_compare_parser(subparsers)
    
    return parser


def _add_validate_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the validate command parser."""
    parser = subparsers.add_parser(
        'validate',
        help='Validate a TTL file for Fabric compatibility'
    )
    parser.add_argument('ttl_file', help='Path to the TTL file to validate')
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
        '--allow-relative-up',
        action='store_true',
        help="Permit '..' in path only if the resolved path stays within the current directory"
    )


def _add_upload_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the upload command parser."""
    parser = subparsers.add_parser(
        'upload',
        help='Upload a TTL file to Fabric Ontology'
    )
    parser.add_argument('ttl_file', help='Path to the TTL file to upload')
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


def _add_convert_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the convert command parser."""
    parser = subparsers.add_parser(
        'convert',
        help='Convert TTL to Fabric format without uploading'
    )
    parser.add_argument('ttl_file', help='Path to the TTL file to convert')
    parser.add_argument('--output', '-o', help='Output JSON file path')
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
        '--allow-relative-up',
        action='store_true',
        help="Permit '..' in path only if the resolved path stays within the current directory"
    )


def _add_export_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the export command parser."""
    parser = subparsers.add_parser(
        'export',
        help='Export ontology from Fabric to TTL format'
    )
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
