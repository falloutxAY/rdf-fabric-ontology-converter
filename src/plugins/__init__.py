"""
Plugin infrastructure for Fabric Ontology Converter.

This module provides the plugin system that allows extending the converter
with new ontology formats beyond the built-in RDF and DTDL.

Usage:
    from plugins import PluginManager, OntologyPlugin
    
    # Get plugin manager
    manager = PluginManager.get_instance()
    manager.discover_plugins()
    
    # Get a plugin
    rdf_plugin = manager.get_plugin("rdf")
    converter = rdf_plugin.get_converter()

Lifecycle Events:
    Plugins can implement lifecycle callbacks:
    
    from plugins import PluginLifecycle
    
    lifecycle = PluginLifecycle()
    lifecycle.register_callback("on_convert_start", my_handler)
"""

from .base import (
    OntologyPlugin,
    PluginLifecycle,
    PluginLifecycleProtocol,
    register_plugin,
    get_registered_plugins,
)
from .protocols import (
    # Type variables
    T,
    T_co,
    ValidationResultT,
    ConversionResultT,
    # Core protocols
    ParserProtocol,
    ValidatorProtocol,
    ConverterProtocol,
    ExporterProtocol,
    # Streaming protocols
    StreamingAdapterProtocol,
    StreamingParserProtocol,
    StreamingConverterProtocol,
    # Type checking utilities
    is_parser,
    is_validator,
    is_converter,
    is_exporter,
    is_streaming_parser,
    is_streaming_converter,
    is_streaming_adapter,
)
from .manager import (
    PluginManager,
    get_plugin_manager,
)

__all__ = [
    # Base class
    "OntologyPlugin",
    # Lifecycle
    "PluginLifecycle",
    "PluginLifecycleProtocol",
    # Registration
    "register_plugin",
    "get_registered_plugins",
    # Type variables
    "T",
    "T_co",
    "ValidationResultT",
    "ConversionResultT",
    # Core Protocols
    "ParserProtocol",
    "ValidatorProtocol",
    "ConverterProtocol",
    "ExporterProtocol",
    # Streaming Protocols
    "StreamingAdapterProtocol",
    "StreamingParserProtocol",
    "StreamingConverterProtocol",
    # Type checking utilities
    "is_parser",
    "is_validator",
    "is_converter",
    "is_exporter",
    "is_streaming_parser",
    "is_streaming_converter",
    "is_streaming_adapter",
    # Manager
    "PluginManager",
    "get_plugin_manager",
]
