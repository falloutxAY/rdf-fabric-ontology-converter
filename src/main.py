#!/usr/bin/env python3
"""
RDF TTL to Microsoft Fabric Ontology Uploader

This is the main entry point for uploading RDF TTL and DTDL ontologies to Microsoft Fabric.

Usage:
    # Run as a module (recommended)
    python -m src.main <command> [options]
    
    # Or from the src directory
    cd src && python main.py <command> [options]
    
    # RDF/TTL Commands (use rdf- prefix)
    python -m src.main rdf-upload <ttl_file> [--config <config.json>] [--name <ontology_name>]
    python -m src.main rdf-validate <ttl_file> [--verbose]
    python -m src.main rdf-convert <ttl_file> [--output <output.json>]
    python -m src.main rdf-export <ontology_id> [--output <output.ttl>]
    
    # DTDL Commands (use dtdl- prefix)
    python -m src.main dtdl-validate <path> [--recursive]
    python -m src.main dtdl-convert <path> [--output <output.json>] [--ontology-name <name>]
    python -m src.main dtdl-upload <path> [--ontology-name <name>] [--config <config.json>]
    
    # Other Commands
    python -m src.main list [--config <config.json>]
    python -m src.main get <ontology_id> [--config <config.json>]
    python -m src.main delete <ontology_id> [--config <config.json>]
    python -m src.main test [--config <config.json>]
    python -m src.main compare <ttl_file1> <ttl_file2>

Note: Legacy command names (validate, upload, convert, export, dtdl-import) 
      are deprecated but still work for backward compatibility.

Architecture:
    This module provides the main entry point and delegates to the cli/ module
    which implements clean separation of concerns:
    - cli/commands.py: Command handlers (thin orchestration layer)
    - cli/parsers.py: Argument parsing configuration
    - cli/helpers.py: Shared utilities (logging, config loading)
"""

import sys
import warnings

# Use try/except for imports to support both module and direct execution
try:
    # When running as module: python -m src.main
    from .cli import (
        create_argument_parser,
        ValidateCommand,
        UploadCommand,
        ListCommand,
        GetCommand,
        DeleteCommand,
        TestCommand,
        ConvertCommand,
        ExportCommand,
        CompareCommand,
        # DTDL commands
        DTDLValidateCommand,
        DTDLConvertCommand,
        DTDLImportCommand,
    )
    from .cli.parsers import DEPRECATED_COMMANDS
except ImportError:
    # When running directly: python src/main.py (from project root)
    from cli import (
        create_argument_parser,
        ValidateCommand,
        UploadCommand,
        ListCommand,
        GetCommand,
        DeleteCommand,
        TestCommand,
        ConvertCommand,
        ExportCommand,
        CompareCommand,
        # DTDL commands
        DTDLValidateCommand,
        DTDLConvertCommand,
        DTDLImportCommand,
    )
    from cli.parsers import DEPRECATED_COMMANDS


# Command mapping from command name to Command class
COMMAND_MAP = {
    # RDF/TTL commands (new names with rdf- prefix)
    'rdf-validate': ValidateCommand,
    'rdf-upload': UploadCommand,
    'rdf-convert': ConvertCommand,
    'rdf-export': ExportCommand,
    
    # Deprecated aliases for backward compatibility
    'validate': ValidateCommand,
    'upload': UploadCommand,
    'convert': ConvertCommand,
    'export': ExportCommand,
    
    # Common commands (no prefix needed)
    'list': ListCommand,
    'get': GetCommand,
    'delete': DeleteCommand,
    'test': TestCommand,
    'compare': CompareCommand,
    
    # DTDL commands
    'dtdl-validate': DTDLValidateCommand,
    'dtdl-convert': DTDLConvertCommand,
    'dtdl-upload': DTDLImportCommand,
    
    # Deprecated alias
    'dtdl-import': DTDLImportCommand,
}


def main():
    """
    Main entry point for the CLI.
    
    Parses command-line arguments and dispatches to the appropriate
    command handler. Uses the Command pattern for clean separation
    of concerns.
    """
    parser = create_argument_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Check for deprecated command names and warn users
    if args.command in DEPRECATED_COMMANDS:
        new_command = DEPRECATED_COMMANDS[args.command]
        warnings.warn(
            f"Command '{args.command}' is deprecated and will be removed in a future version. "
            f"Use '{new_command}' instead.",
            DeprecationWarning,
            stacklevel=2
        )
        print(f"⚠️  Warning: '{args.command}' is deprecated. Please use '{new_command}' instead.")
    
    # Get the command class and instantiate it
    command_class = COMMAND_MAP.get(args.command)
    
    if command_class is None:
        print(f"Error: Unknown command '{args.command}'")
        parser.print_help()
        sys.exit(1)
    
    # Create and execute the command
    # Pass config_path if available in args
    config_path = getattr(args, 'config', None)
    command = command_class(config_path=config_path)
    
    exit_code = command.execute(args)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
