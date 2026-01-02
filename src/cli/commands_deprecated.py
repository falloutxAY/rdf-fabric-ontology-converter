"""
CLI command handlers.

DEPRECATED: This module re-exports from the new commands/ package structure.
Import directly from cli.commands.* for new code.

The command implementations have been reorganized into:
- cli/commands/base.py: Base command class and protocols
- cli/commands/common.py: Common commands (list, get, delete, test, compare)
- cli/commands/rdf.py: RDF/TTL commands (validate, upload, convert, export)
- cli/commands/dtdl.py: DTDL commands (validate, convert, upload/import)
"""

# Re-export everything from the new package for backward compatibility
from .commands import (
    # Base
    BaseCommand,
    IValidator,
    IConverter,
    IFabricClient,
    print_conversion_summary,
    # Common
    ListCommand,
    GetCommand,
    DeleteCommand,
    TestCommand,
    CompareCommand,
    # RDF
    ValidateCommand,
    UploadCommand,
    ConvertCommand,
    ExportCommand,
    # DTDL
    DTDLValidateCommand,
    DTDLConvertCommand,
    DTDLImportCommand,
)


__all__ = [
    # Base
    'BaseCommand',
    'IValidator',
    'IConverter',
    'IFabricClient',
    'print_conversion_summary',
    # Common
    'ListCommand',
    'GetCommand',
    'DeleteCommand',
    'TestCommand',
    'CompareCommand',
    # RDF
    'ValidateCommand',
    'UploadCommand',
    'ConvertCommand',
    'ExportCommand',
    # DTDL
    'DTDLValidateCommand',
    'DTDLConvertCommand',
    'DTDLImportCommand',
]
