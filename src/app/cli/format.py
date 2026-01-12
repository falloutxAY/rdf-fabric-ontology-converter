"""
Format enumeration and dispatch helpers.

Provides a single point for branching between RDF and DTDL logic
in the unified CLI commands. Now integrated with the plugin system
for extensibility.
"""

from enum import Enum
from typing import Any, Callable, Dict, Optional, Set, Type
import logging

logger = logging.getLogger(__name__)


class Format(str, Enum):
    """Supported ontology formats."""
    RDF = "rdf"
    DTDL = "dtdl"
    CDM = "cdm"

    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# Service factory registry (legacy - maintained for backward compatibility)
# ---------------------------------------------------------------------------

_VALIDATOR_FACTORIES: Dict[Format, Callable[[], Any]] = {}
_CONVERTER_FACTORIES: Dict[Format, Callable[[], Any]] = {}
_UPLOADER_FACTORIES: Dict[Format, Callable[[], Any]] = {}

# Plugin manager instance (lazy loaded)
_plugin_manager: Optional[Any] = None


def _get_plugin_manager():
    """Get or create the plugin manager instance."""
    global _plugin_manager
    if _plugin_manager is None:
        try:
            from ..plugins import PluginManager
            _plugin_manager = PluginManager.get_instance()
            _plugin_manager.discover_plugins()
        except ImportError:
            logger.debug("Plugin system not available, using legacy factories")
            _plugin_manager = None
    return _plugin_manager


def register_validator(fmt: Format, factory: Callable[[], Any]) -> None:
    """Register a validator factory for a format."""
    _VALIDATOR_FACTORIES[fmt] = factory


def register_converter(fmt: Format, factory: Callable[[], Any]) -> None:
    """Register a converter factory for a format."""
    _CONVERTER_FACTORIES[fmt] = factory


def register_uploader(fmt: Format, factory: Callable[[], Any]) -> None:
    """Register an uploader factory for a format."""
    _UPLOADER_FACTORIES[fmt] = factory


def get_validator(fmt: Format) -> Any:
    """
    Return a validator instance for the given format.
    
    First attempts to use the plugin system, falls back to legacy factories.
    
    Raises:
        ValueError: If no validator is registered for the format.
    """
    # Try plugin system first
    manager = _get_plugin_manager()
    if manager:
        plugin = manager.get_plugin(fmt.value)
        if plugin:
            return plugin.get_validator()
    
    # Fall back to legacy factories
    factory = _VALIDATOR_FACTORIES.get(fmt)
    if factory is None:
        raise ValueError(f"No validator registered for format: {fmt}")
    return factory()


def get_converter(fmt: Format) -> Any:
    """
    Return a converter instance for the given format.
    
    First attempts to use the plugin system, falls back to legacy factories.
    
    Raises:
        ValueError: If no converter is registered for the format.
    """
    # Try plugin system first
    manager = _get_plugin_manager()
    if manager:
        plugin = manager.get_plugin(fmt.value)
        if plugin:
            return plugin.get_converter()
    
    # Fall back to legacy factories
    factory = _CONVERTER_FACTORIES.get(fmt)
    if factory is None:
        raise ValueError(f"No converter registered for format: {fmt}")
    return factory()


def get_uploader(fmt: Format) -> Any:
    """
    Return an uploader instance for the given format.
    
    Raises:
        ValueError: If no uploader is registered for the format.
    """
    factory = _UPLOADER_FACTORIES.get(fmt)
    if factory is None:
        raise ValueError(f"No uploader registered for format: {fmt}")
    return factory()


# ---------------------------------------------------------------------------
# Default registrations (lazy imports to avoid circular deps)
# ---------------------------------------------------------------------------

def _register_defaults() -> None:
    """Register default factories for RDF, DTDL, and CDM."""
    # RDF validators/converters
    def rdf_validator():
        from src.rdf import PreflightValidator
        return PreflightValidator()

    def rdf_converter():
        from src.rdf import RDFToFabricConverter
        return RDFToFabricConverter()

    register_validator(Format.RDF, rdf_validator)
    register_converter(Format.RDF, rdf_converter)

    # DTDL validators/converters
    def dtdl_validator():
        from dtdl.dtdl_validator import DTDLValidator
        return DTDLValidator()

    def dtdl_converter():
        from dtdl.dtdl_converter import DTDLToFabricConverter
        return DTDLToFabricConverter()

    register_validator(Format.DTDL, dtdl_validator)
    register_converter(Format.DTDL, dtdl_converter)

    # CDM validators/converters
    def cdm_validator():
        from src.formats.cdm import CDMValidator
        return CDMValidator()

    def cdm_converter():
        from src.formats.cdm import CDMToFabricConverter
        return CDMToFabricConverter()

    register_validator(Format.CDM, cdm_validator)
    register_converter(Format.CDM, cdm_converter)


# Auto-register on module load
_register_defaults()


# ---------------------------------------------------------------------------
# File extension helpers
# ---------------------------------------------------------------------------

RDF_EXTENSIONS = {
    ".ttl",
    ".rdf",
    ".owl",
    ".nt",
    ".n3",
    ".xml",
    ".trig",
    ".nq",
    ".nquads",
    ".trix",
    ".hext",
    ".jsonld",
    ".html",
    ".xhtml",
    ".htm",
}
DTDL_EXTENSIONS = {".json"}
CDM_EXTENSIONS = {".cdm.json", ".manifest.cdm.json"}


def infer_format_from_path(path: str) -> Format:
    """
    Attempt to infer the format from a file path extension.
    
    First tries the plugin system for extension mapping, then falls
    back to hardcoded extensions.
    
    Args:
        path: File or directory path.
        
    Returns:
        Inferred Format.
        
    Raises:
        ValueError: If format cannot be inferred.
    """
    from pathlib import Path as PathLib
    path_obj = PathLib(path)
    ext = path_obj.suffix.lower()
    filename = path_obj.name.lower()
    
    # Check for CDM compound extensions first (before plugin system)
    if filename.endswith('.manifest.cdm.json') or filename.endswith('.cdm.json'):
        return Format.CDM
    
    # Try plugin system first
    manager = _get_plugin_manager()
    if manager:
        plugin = manager.get_plugin_for_extension(ext)
        if plugin:
            format_name = plugin.format_name.lower()
            # Map to Format enum
            try:
                return Format(format_name)
            except ValueError:
                # Plugin format not in enum, but we found a plugin
                logger.debug(f"Plugin found for {ext} but format '{format_name}' not in enum")
    
    # Fall back to hardcoded extensions
    if ext in RDF_EXTENSIONS:
        return Format.RDF
    if ext in DTDL_EXTENSIONS:
        return Format.DTDL
    raise ValueError(
        f"Cannot infer format from extension '{ext}'. "
        f"Use --format to specify explicitly."
    )


def list_supported_formats() -> Dict[str, Dict[str, Any]]:
    """
    List all supported formats and their metadata.
    
    Returns:
        Dict mapping format names to their info.
    """
    result = {}
    
    # Get formats from plugin system
    manager = _get_plugin_manager()
    if manager:
        for plugin in manager.list_plugins():
            result[plugin.format_name] = {
                "display_name": plugin.display_name,
                "version": plugin.version,
                "extensions": list(plugin.file_extensions),
                "source": "plugin",
            }
    else:
        # Fall back to hardcoded formats
        result["rdf"] = {
            "display_name": "RDF (Turtle/RDF-XML)",
            "version": "1.0.0",
            "extensions": list(RDF_EXTENSIONS),
            "source": "builtin",
        }
        result["dtdl"] = {
            "display_name": "DTDL (Digital Twins Definition Language)",
            "version": "1.0.0",
            "extensions": list(DTDL_EXTENSIONS),
            "source": "builtin",
        }
        result["cdm"] = {
            "display_name": "CDM (Common Data Model)",
            "version": "1.0.0",
            "extensions": list(CDM_EXTENSIONS),
            "source": "builtin",
        }
    return result


def list_supported_extensions() -> Set[str]:
    """
    List all supported file extensions.
    
    Returns:
        Set of supported extensions.
    """
    manager = _get_plugin_manager()
    if manager:
        return manager.list_extensions()
    return RDF_EXTENSIONS | DTDL_EXTENSIONS | CDM_EXTENSIONS
