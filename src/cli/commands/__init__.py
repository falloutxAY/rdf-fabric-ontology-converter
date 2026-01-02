"""
CLI command implementations.

This package contains split command modules for better organization:
- base.py: Base command class and protocols
- common.py: Common commands (list, get, delete, test, compare)
- rdf.py: RDF/TTL-specific commands (validate, upload, convert, export)
- dtdl.py: DTDL-specific commands (validate, convert, upload/import)
"""

from .base import (
    BaseCommand,
    IValidator,
    IConverter,
    IFabricClient,
    print_conversion_summary,
)

from .common import (
    ListCommand,
    GetCommand,
    DeleteCommand,
    TestCommand,
    CompareCommand,
)

from .rdf import (
    ValidateCommand,
    UploadCommand,
    ConvertCommand,
    ExportCommand,
)

from .dtdl import (
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
