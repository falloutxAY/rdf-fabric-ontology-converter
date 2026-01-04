"""
Base Plugin Class - Abstract base for ontology format plugins.

This module defines the OntologyPlugin abstract base class that all
format plugins must implement.

Usage:
    from plugins.base import OntologyPlugin
    
    class MyFormatPlugin(OntologyPlugin):
        @property
        def format_name(self) -> str:
            return "myformat"
        
        @property
        def display_name(self) -> str:
            return "My Custom Format"
        
        @property
        def file_extensions(self) -> Set[str]:
            return {".myf", ".myformat"}
        
        def get_parser(self) -> ParserProtocol:
            return MyFormatParser()
        
        def get_validator(self) -> ValidatorProtocol:
            return MyFormatValidator()
        
        def get_converter(self) -> ConverterProtocol:
            return MyFormatConverter()

Lifecycle:
    Plugins can implement lifecycle callbacks to be notified of conversion events:
    
    class MyFormatPlugin(OntologyPlugin):
        def get_lifecycle(self) -> Optional[PluginLifecycle]:
            return MyLifecycle()
    
    class MyLifecycle(PluginLifecycle):
        def on_register(self, plugin: OntologyPlugin) -> None:
            print(f"Plugin {plugin.format_name} registered")
        
        def on_convert_start(self, file_path: str, options: Dict[str, Any]) -> None:
            print(f"Starting conversion of {file_path}")
        
        def on_convert_complete(
            self, file_path: str, result: Any, success: bool
        ) -> None:
            status = "succeeded" if success else "failed"
            print(f"Conversion {status} for {file_path}")
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Set, Type, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import for type hints only
    from formats.base import FormatPipeline
from .protocols import (
    ParserProtocol,
    ValidatorProtocol,
    ConverterProtocol,
    ExporterProtocol,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Plugin Lifecycle Events (P3.2)
# =============================================================================


class PluginLifecycleProtocol(Protocol):
    """
    Protocol for plugin lifecycle event handlers.
    
    Implement this protocol to receive notifications about plugin
    registration and conversion events.
    """
    
    def on_register(self, plugin: "OntologyPlugin") -> None:
        """Called when the plugin is registered with the manager."""
        ...
    
    def on_unregister(self, plugin: "OntologyPlugin") -> None:
        """Called when the plugin is unregistered from the manager."""
        ...
    
    def on_convert_start(
        self, file_path: str, options: Dict[str, Any]
    ) -> None:
        """Called before a conversion begins."""
        ...
    
    def on_convert_complete(
        self, file_path: str, result: Any, success: bool, error: Optional[Exception] = None
    ) -> None:
        """Called after a conversion completes (success or failure)."""
        ...
    
    def on_validate_start(self, file_path: str) -> None:
        """Called before validation begins."""
        ...
    
    def on_validate_complete(
        self, file_path: str, result: Any, success: bool
    ) -> None:
        """Called after validation completes."""
        ...


@dataclass
class PluginLifecycle:
    """
    Plugin lifecycle event handler with callback support.
    
    Provides a flexible way to handle plugin events through either
    method overriding or callback registration.
    
    Example using callbacks:
        lifecycle = PluginLifecycle()
        lifecycle.register_callback("on_convert_start", my_start_handler)
        lifecycle.register_callback("on_convert_complete", my_complete_handler)
    
    Example using inheritance:
        class MyLifecycle(PluginLifecycle):
            def on_convert_start(self, file_path: str, options: Dict[str, Any]) -> None:
                logger.info(f"Converting: {file_path}")
    
    Attributes:
        callbacks: Dictionary mapping event names to callback lists.
    """
    
    callbacks: Dict[str, List[Callable[..., None]]] = field(
        default_factory=lambda: {
            "on_register": [],
            "on_unregister": [],
            "on_convert_start": [],
            "on_convert_complete": [],
            "on_validate_start": [],
            "on_validate_complete": [],
        }
    )
    
    def register_callback(
        self, event: str, callback: Callable[..., None]
    ) -> None:
        """
        Register a callback for a lifecycle event.
        
        Args:
            event: Event name (e.g., "on_convert_start").
            callback: Callable to invoke when event occurs.
            
        Raises:
            ValueError: If event name is not recognized.
        """
        if event not in self.callbacks:
            raise ValueError(
                f"Unknown event: {event}. Valid events: {list(self.callbacks.keys())}"
            )
        self.callbacks[event].append(callback)
    
    def unregister_callback(
        self, event: str, callback: Callable[..., None]
    ) -> bool:
        """
        Unregister a callback for a lifecycle event.
        
        Args:
            event: Event name.
            callback: The callback to remove.
            
        Returns:
            True if callback was found and removed, False otherwise.
        """
        if event in self.callbacks and callback in self.callbacks[event]:
            self.callbacks[event].remove(callback)
            return True
        return False
    
    def _invoke_callbacks(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Invoke all callbacks for an event."""
        for callback in self.callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Lifecycle callback error for {event}: {e}")
    
    def on_register(self, plugin: "OntologyPlugin") -> None:
        """
        Called when the plugin is registered with the manager.
        
        Args:
            plugin: The plugin being registered.
        """
        self._invoke_callbacks("on_register", plugin)
    
    def on_unregister(self, plugin: "OntologyPlugin") -> None:
        """
        Called when the plugin is unregistered from the manager.
        
        Args:
            plugin: The plugin being unregistered.
        """
        self._invoke_callbacks("on_unregister", plugin)
    
    def on_convert_start(
        self, file_path: str, options: Dict[str, Any]
    ) -> None:
        """
        Called before a conversion begins.
        
        Args:
            file_path: Path to the file being converted.
            options: Conversion options dictionary.
        """
        self._invoke_callbacks("on_convert_start", file_path, options)
    
    def on_convert_complete(
        self,
        file_path: str,
        result: Any,
        success: bool,
        error: Optional[Exception] = None,
    ) -> None:
        """
        Called after a conversion completes.
        
        Args:
            file_path: Path to the file that was converted.
            result: The conversion result (or None on failure).
            success: Whether conversion succeeded.
            error: The exception if conversion failed.
        """
        self._invoke_callbacks("on_convert_complete", file_path, result, success, error)
    
    def on_validate_start(self, file_path: str) -> None:
        """
        Called before validation begins.
        
        Args:
            file_path: Path to the file being validated.
        """
        self._invoke_callbacks("on_validate_start", file_path)
    
    def on_validate_complete(
        self, file_path: str, result: Any, success: bool
    ) -> None:
        """
        Called after validation completes.
        
        Args:
            file_path: Path to the file that was validated.
            result: The validation result.
            success: Whether validation passed.
        """
        self._invoke_callbacks("on_validate_complete", file_path, result, success)


class OntologyPlugin(ABC):
    """
    Abstract base class for ontology format plugins.
    
    Each plugin represents a single ontology format (e.g., RDF, DTDL, JSON-LD)
    and provides implementations for parsing, validating, and converting
    that format to Microsoft Fabric Ontology format.
    
    Required Properties:
        format_name: Unique identifier for CLI (e.g., "rdf", "dtdl")
        display_name: Human-readable name (e.g., "RDF/OWL TTL")
        file_extensions: Supported file extensions (e.g., {".ttl", ".rdf"})
    
    Required Methods:
        get_parser(): Returns parser for this format
        get_validator(): Returns validator for this format
        get_converter(): Returns converter to Fabric format
    
    Optional Methods:
        get_exporter(): Returns exporter from Fabric format (reverse conversion)
        get_type_mappings(): Returns type mapping dictionary
        register_cli_arguments(): Add format-specific CLI arguments
        get_streaming_adapter(): Return streaming adapter for large files
    
    Example:
        >>> class ExamplePlugin(OntologyPlugin):
        ...     @property
        ...     def format_name(self) -> str:
        ...         return "example"
        ...
        ...     @property
        ...     def display_name(self) -> str:
        ...         return "Example Format"
        ...
        ...     @property
        ...     def file_extensions(self) -> Set[str]:
        ...         return {".ex"}
        ...
        ...     def get_parser(self):
        ...         return ExampleParser()
        ...
        ...     def get_validator(self):
        ...         return ExampleValidator()
        ...
        ...     def get_converter(self):
        ...         return ExampleConverter()
    """
    
    # =========================================================================
    # Required Abstract Properties
    # =========================================================================
    
    @property
    @abstractmethod
    def format_name(self) -> str:
        """
        Unique identifier for this format.
        
        Used in CLI commands (--format <name>) and internal registration.
        Should be lowercase, alphanumeric, no spaces.
        
        Examples: "rdf", "dtdl", "shacl"
        """
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Human-readable format name.
        
        Used in help text, error messages, and UI.
        
        Examples: "RDF/OWL TTL", "DTDL v4", "SHACL"
        """
        pass
    
    @property
    @abstractmethod
    def file_extensions(self) -> Set[str]:
        """
        Set of supported file extensions.
        
        Extensions should include the leading dot and be lowercase.
        
        Examples: {".ttl", ".rdf", ".owl"}, {".json"}, {".shacl"}
        """
        pass
    
    # =========================================================================
    # Required Abstract Methods
    # =========================================================================
    
    @abstractmethod
    def get_parser(self) -> ParserProtocol:
        """
        Get a parser instance for this format.
        
        The parser is responsible for reading and parsing files
        in this format into an internal representation.
        
        Returns:
            Parser instance implementing ParserProtocol.
        """
        pass
    
    @abstractmethod
    def get_validator(self) -> ValidatorProtocol:
        """
        Get a validator instance for this format.
        
        The validator checks format-specific rules and produces
        a ValidationResult.
        
        Returns:
            Validator instance implementing ValidatorProtocol.
        """
        pass
    
    @abstractmethod
    def get_converter(self) -> ConverterProtocol:
        """
        Get a converter instance for this format.
        
        The converter transforms parsed content into
        Fabric Ontology format (EntityType, RelationshipType).
        
        Returns:
            Converter instance implementing ConverterProtocol.
        """
        pass

    def create_pipeline(self) -> FormatPipeline:
        """Return a ready-to-use pipeline description for this format."""
        from formats.base import FormatPipeline  # Local import to avoid circular dependency

        return FormatPipeline(
            format_name=self.format_name,
            parser=self.get_parser(),
            validator=self.get_validator(),
            converter=self.get_converter(),
            exporter=self.get_exporter(),
        )
    
    # =========================================================================
    # Optional Properties
    # =========================================================================
    
    @property
    def version(self) -> str:
        """
        Plugin version string.
        
        Follows semantic versioning (MAJOR.MINOR.PATCH).
        
        Returns:
            Version string (default: "1.0.0").
        """
        return "1.0.0"
    
    @property
    def min_converter_version(self) -> str:
        """
        Minimum converter version required for this plugin.
        
        Override this if your plugin requires specific converter features
        that were introduced in a particular version.
        
        Returns:
            Minimum version string (default: "1.0.0").
        """
        return "1.0.0"
    
    @property
    def max_converter_version(self) -> Optional[str]:
        """
        Maximum converter version supported by this plugin.
        
        Override this if your plugin is incompatible with newer versions.
        Returns None if there's no upper limit (default behavior).
        
        Returns:
            Maximum version string or None.
        """
        return None
    
    @property
    def supported_fabric_versions(self) -> List[str]:
        """
        List of Fabric API versions supported by this plugin.
        
        Override this to specify which Fabric API versions your plugin
        can work with. This helps ensure compatibility and allows the
        system to warn users about potential issues.
        
        Common versions:
        - "v1": Initial Fabric Ontology API
        - "v2": Extended API with additional features
        
        Returns:
            List of supported version strings (default: ["v1"]).
            
        Example:
            @property
            def supported_fabric_versions(self) -> List[str]:
                return ["v1", "v2"]  # Supports both v1 and v2 APIs
        """
        return ["v1"]
    
    @property
    def author(self) -> str:
        """
        Plugin author information.
        
        Returns:
            Author name or organization (default: "Unknown").
        """
        return "Unknown"
    
    @property
    def description(self) -> str:
        """
        Plugin description.
        
        Returns:
            Description string (default: class docstring or empty).
        """
        return self.__class__.__doc__ or ""
    
    @property
    def documentation_url(self) -> Optional[str]:
        """
        URL to plugin documentation.
        
        Returns:
            URL string or None.
        """
        return None
    
    @property
    def supports_streaming(self) -> bool:
        """
        Whether this plugin supports streaming for large files.
        
        Returns:
            True if streaming is supported (default: False).
        """
        return False
    
    @property
    def supports_export(self) -> bool:
        """
        Whether this plugin supports export (Fabric -> this format).
        
        Returns:
            True if export is supported (default: False).
        """
        return self.get_exporter() is not None
    
    @property
    def dependencies(self) -> List[str]:
        """
        List of Python package dependencies.
        
        Returns:
            List of package names (e.g., ["rdflib", "jsonld"]).
        """
        return []
    
    # =========================================================================
    # Optional Methods
    # =========================================================================
    
    def get_exporter(self) -> Optional[ExporterProtocol]:
        """
        Get an exporter instance for reverse conversion.
        
        The exporter transforms Fabric Ontology format back into
        this format.
        
        Returns:
            Exporter instance or None if not supported.
        """
        return None
    
    def get_type_mappings(self) -> Dict[str, str]:
        """
        Get format-specific type mappings to Fabric types.
        
        Override to provide custom type mappings. These will be
        registered with the global TypeMappingRegistry.
        
        Returns:
            Dict mapping source types to Fabric types.
            
        Example:
            {
                "http://www.w3.org/2001/XMLSchema#string": "String",
                "http://www.w3.org/2001/XMLSchema#integer": "BigInt",
            }
        """
        return {}
    
    def get_streaming_adapter(self) -> Optional[Any]:
        """
        Get a streaming adapter for processing large files.
        
        Override to provide a streaming implementation that can
        process files without loading entirely into memory.
        
        Returns:
            Streaming adapter or None if not supported.
        """
        return None
    
    def get_lifecycle(self) -> Optional[PluginLifecycle]:
        """
        Get a lifecycle handler for this plugin.
        
        Override to provide lifecycle callbacks for plugin events
        like registration, conversion start/complete, etc.
        
        Returns:
            PluginLifecycle instance or None if not using lifecycle events.
        
        Example:
            def get_lifecycle(self) -> Optional[PluginLifecycle]:
                lifecycle = PluginLifecycle()
                lifecycle.register_callback("on_convert_start", self._log_start)
                lifecycle.register_callback("on_convert_complete", self._log_complete)
                return lifecycle
        """
        return None
    
    def register_cli_arguments(self, parser: Any) -> None:
        """
        Register format-specific CLI arguments.
        
        Override to add arguments specific to this format
        (e.g., DTDL's --component-mode / --command-mode).
        
        Args:
            parser: argparse.ArgumentParser subparser.
        """
        pass
    
    def initialize(self) -> None:
        """
        Initialize the plugin.
        
        Called when the plugin is first loaded. Override to
        perform any setup needed before the plugin is used.
        
        Raises:
            RuntimeError: If initialization fails.
        """
        pass
    
    def cleanup(self) -> None:
        """
        Clean up plugin resources.
        
        Called when the plugin is unloaded. Override to
        release any resources held by the plugin.
        """
        pass
    
    def check_dependencies(self) -> List[str]:
        """
        Check if required dependencies are available.
        
        Returns:
            List of missing dependency names.
        """
        import re
        missing = []
        for dep in self.dependencies:
            # Extract package name from version specifier (e.g., "rdflib>=6.0.0" -> "rdflib")
            package_name = re.split(r'[<>=!~\[]', dep)[0].strip()
            try:
                __import__(package_name)
            except ImportError:
                missing.append(dep)
        return missing
    
    def check_version_compatibility(self, converter_version: str) -> bool:
        """
        Check if this plugin is compatible with the given converter version.
        
        Uses semantic versioning comparison to determine if the plugin
        can work with the specified converter version.
        
        Args:
            converter_version: The converter version string (e.g., "1.2.3").
        
        Returns:
            True if compatible, False otherwise.
        
        Example:
            >>> plugin = RDFPlugin()
            >>> plugin.check_version_compatibility("1.0.0")
            True
            >>> plugin.check_version_compatibility("0.9.0")
            False  # Below min_converter_version
        """
        try:
            from packaging import version
            cv = version.parse(converter_version)
            min_v = version.parse(self.min_converter_version)
            
            if cv < min_v:
                logger.warning(
                    f"Plugin '{self.format_name}' requires converter >= {self.min_converter_version}, "
                    f"but got {converter_version}"
                )
                return False
            
            if self.max_converter_version:
                max_v = version.parse(self.max_converter_version)
                if cv > max_v:
                    logger.warning(
                        f"Plugin '{self.format_name}' only supports converter <= {self.max_converter_version}, "
                        f"but got {converter_version}"
                    )
                    return False
            
            return True
        except ImportError:
            # Fallback to simple string comparison if packaging not available
            logger.debug("packaging module not available, using simple version comparison")
            return converter_version >= self.min_converter_version
    
    def can_handle_extension(self, extension: str) -> bool:
        """
        Check if this plugin handles the given extension.
        
        Args:
            extension: File extension (with or without dot).
        
        Returns:
            True if the extension is handled.
        """
        ext = extension.lower() if extension.startswith('.') else f'.{extension.lower()}'
        return ext in self.file_extensions
    
    # =========================================================================
    # Built-in Methods
    # =========================================================================
    
    def matches_extension(self, file_path: str) -> bool:
        """
        Check if a file path matches this plugin's extensions.
        
        Args:
            file_path: Path to check.
        
        Returns:
            True if the extension matches.
        """
        from pathlib import Path
        ext = Path(file_path).suffix.lower()
        return ext in self.file_extensions
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get plugin information dictionary.
        
        Returns:
            Dict with plugin metadata.
        """
        return {
            "format_name": self.format_name,
            "display_name": self.display_name,
            "version": self.version,
            "min_converter_version": self.min_converter_version,
            "max_converter_version": self.max_converter_version,
            "author": self.author,
            "description": self.description,
            "file_extensions": list(self.file_extensions),
            "supports_streaming": self.supports_streaming,
            "supports_export": self.supports_export,
            "supports_lifecycle": self.get_lifecycle() is not None,
            "dependencies": self.dependencies,
            "documentation_url": self.documentation_url,
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(format={self.format_name!r}, version={self.version!r})"
    
    def __str__(self) -> str:
        return f"{self.display_name} (v{self.version})"


# =============================================================================
# Plugin Registration Decorator
# =============================================================================

_plugin_registry: Dict[str, Type[OntologyPlugin]] = {}


def register_plugin(cls: Type[OntologyPlugin]) -> Type[OntologyPlugin]:
    """
    Decorator to register a plugin class.
    
    Can be used to automatically register plugins when their module is imported.
    
    Usage:
        @register_plugin
        class MyPlugin(OntologyPlugin):
            ...
    """
    # Create temporary instance to get format_name
    try:
        instance = cls()
        _plugin_registry[instance.format_name.lower()] = cls
        logger.debug(f"Registered plugin class: {cls.__name__}")
    except Exception as e:
        logger.warning(f"Could not register plugin {cls.__name__}: {e}")
    return cls


def get_registered_plugins() -> Dict[str, Type[OntologyPlugin]]:
    """Get all registered plugin classes."""
    return _plugin_registry.copy()
