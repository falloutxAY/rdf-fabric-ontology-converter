"""
Plugin architecture for custom format converters.

This module provides a plugin system that allows users to add custom format
converters without modifying the core codebase. Plugins can be:
- Loaded from entry points (pip-installable packages)
- Loaded from a plugins directory
- Registered programmatically

Architecture:
    The plugin system uses abstract base classes to define interfaces that
    all converters must implement. This ensures consistency across built-in
    and custom converters.

Plugin Types:
    - FormatConverter: Convert from a source format to Fabric Ontology
    - FormatValidator: Validate files in a specific format
    - FormatExporter: Export Fabric Ontology to a specific format

Usage:
    # Register a custom converter programmatically
    from src.core.plugins import PluginRegistry, FormatConverter
    
    class MyCustomConverter(FormatConverter):
        format_name = "custom"
        file_extensions = [".custom", ".cst"]
        
        def convert(self, source, **options):
            # Implementation
            pass
    
    PluginRegistry.register_converter(MyCustomConverter())
    
    # Discover and load plugins from entry points
    PluginRegistry.discover_plugins()
    
    # List available converters
    print(PluginRegistry.list_converters())

Entry Points:
    Plugins can be registered via setuptools entry points in pyproject.toml:
    
    [project.entry-points."fabric_ontology.converters"]
    my_format = "mypackage.converters:MyFormatConverter"
    
    [project.entry-points."fabric_ontology.validators"]
    my_format = "mypackage.validators:MyFormatValidator"
    
    [project.entry-points."fabric_ontology.exporters"]
    my_format = "mypackage.exporters:MyFormatExporter"
"""

import logging
import importlib
import importlib.metadata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    Type,
    TypeVar,
    Union,
    runtime_checkable,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Plugin Type Definitions
# =============================================================================

class PluginType(Enum):
    """Types of plugins supported by the system."""
    CONVERTER = "converter"
    VALIDATOR = "validator"
    EXPORTER = "exporter"


class ConversionStatus(Enum):
    """Status of a conversion operation."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class PluginMetadata:
    """
    Metadata about a registered plugin.
    
    Attributes:
        name: Human-readable plugin name.
        format_name: Short identifier for the format (e.g., "rdf", "dtdl").
        version: Plugin version string.
        author: Plugin author or maintainer.
        description: Brief description of what the plugin does.
        file_extensions: List of file extensions this plugin handles.
        plugin_type: Type of plugin (converter, validator, exporter).
        source: Where the plugin was loaded from (entry_point, directory, programmatic).
    """
    name: str
    format_name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    file_extensions: List[str] = field(default_factory=list)
    plugin_type: PluginType = PluginType.CONVERTER
    source: str = "programmatic"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary for serialization."""
        return {
            "name": self.name,
            "format_name": self.format_name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "file_extensions": self.file_extensions,
            "plugin_type": self.plugin_type.value,
            "source": self.source,
        }


@dataclass
class ConversionContext:
    """
    Context passed to converters with configuration and callbacks.
    
    This context integrates with core infrastructure components to provide
    plugins with access to rate limiting, circuit breakers, cancellation,
    memory management, and input validation.
    
    Attributes:
        config: Configuration dictionary from config.json.
        progress_callback: Optional callback for progress reporting.
        cancel_check: Optional callback to check for cancellation.
        logger: Logger instance for the conversion.
        rate_limiter: Optional rate limiter for API calls.
        circuit_breaker: Optional circuit breaker for fault tolerance.
        cancellation_token: Optional cancellation token for graceful shutdown.
        memory_manager: Optional memory manager for large file processing.
        input_validator: Optional input validator for security checks.
    """
    config: Dict[str, Any] = field(default_factory=dict)
    progress_callback: Optional[Callable[[int, int, str], None]] = None
    cancel_check: Optional[Callable[[], bool]] = None
    logger: Optional[logging.Logger] = None
    # Core infrastructure integrations
    rate_limiter: Optional[Any] = None  # RateLimiter protocol
    circuit_breaker: Optional[Any] = None  # CircuitBreaker instance
    cancellation_token: Optional[Any] = None  # CancellationToken instance
    memory_manager: Optional[Any] = None  # MemoryManager instance
    input_validator: Optional[Any] = None  # InputValidator instance
    
    def report_progress(self, current: int, total: int, message: str = "") -> None:
        """Report progress if a callback is configured."""
        if self.progress_callback:
            self.progress_callback(current, total, message)
    
    def is_cancelled(self) -> bool:
        """
        Check if the operation has been cancelled.
        
        Checks both the cancel_check callback and the cancellation_token
        if either is configured.
        """
        if self.cancel_check and self.cancel_check():
            return True
        if self.cancellation_token:
            # CancellationToken.is_cancelled() is a method that returns bool
            return self.cancellation_token.is_cancelled()
        return False
    
    def throw_if_cancelled(self) -> None:
        """
        Raise OperationCancelledException if cancelled.
        
        Use this in loops for cooperative cancellation.
        """
        if self.cancellation_token:
            self.cancellation_token.throw_if_cancelled()
        elif self.is_cancelled():
            from .cancellation import OperationCancelledException
            raise OperationCancelledException("Operation cancelled by user")
    
    def acquire_rate_limit(self, tokens: int = 1) -> bool:
        """
        Acquire rate limit tokens before making API calls.
        
        Args:
            tokens: Number of tokens to acquire (default: 1).
        
        Returns:
            True if tokens were acquired, False if rate limited.
        """
        if self.rate_limiter:
            return self.rate_limiter.acquire(tokens)
        return True  # No rate limiter configured
    
    def call_with_circuit_breaker(
        self, 
        func: Callable[..., Any], 
        *args: Any, 
        **kwargs: Any
    ) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: The function to call.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.
        
        Returns:
            The function's return value.
        
        Raises:
            CircuitBreakerOpenError: If the circuit is open.
        """
        if self.circuit_breaker:
            return self.circuit_breaker.call(func, *args, **kwargs)
        return func(*args, **kwargs)
    
    def check_memory(self, file_size_mb: float = 0.0) -> bool:
        """
        Check if there's enough memory to proceed.
        
        Args:
            file_size_mb: Size of the file to process in MB. If 0, uses default check.
        
        Returns:
            True if memory is available, False if memory is low.
        """
        if self.memory_manager:
            # MemoryManager.check_memory_available returns (bool, str) tuple
            can_proceed, _ = self.memory_manager.check_memory_available(file_size_mb)
            return can_proceed
        return True  # No memory manager configured
    
    def validate_input(self, file_path: str, check_exists: bool = False) -> bool:
        """
        Validate an input file path for security issues.
        
        Args:
            file_path: Path to validate.
            check_exists: Whether to require the file to exist.
        
        Returns:
            True if the path is safe, raises exception otherwise.
        """
        if self.input_validator:
            self.input_validator.validate_file_path(
                file_path, 
                check_exists=check_exists
            )
            return True
        return True  # No validator configured
    
    def log(self, level: int, message: str) -> None:
        """Log a message using the configured logger."""
        if self.logger:
            self.logger.log(level, message)
    
    @classmethod
    def create_with_defaults(
        cls,
        config: Optional[Dict[str, Any]] = None,
        enable_rate_limiter: bool = False,
        enable_circuit_breaker: bool = False,
        enable_cancellation: bool = False,
        enable_memory_manager: bool = False,
    ) -> 'ConversionContext':
        """
        Create a context with default core infrastructure components.
        
        This factory method makes it easy to create a fully-configured
        context with the desired core utilities enabled.
        
        Args:
            config: Configuration dictionary.
            enable_rate_limiter: Enable rate limiting.
            enable_circuit_breaker: Enable circuit breaker.
            enable_cancellation: Enable cancellation support.
            enable_memory_manager: Enable memory management.
        
        Returns:
            Configured ConversionContext instance.
        
        Example:
            context = ConversionContext.create_with_defaults(
                enable_rate_limiter=True,
                enable_circuit_breaker=True,
            )
        """
        ctx = cls(config=config or {})
        
        if enable_rate_limiter:
            try:
                from .rate_limiter import TokenBucketRateLimiter
                rate_config = (config or {}).get("rate_limit", {})
                ctx.rate_limiter = TokenBucketRateLimiter(
                    rate=rate_config.get("rate", 10),
                    per=rate_config.get("per", 60),
                    burst=rate_config.get("burst"),
                )
            except ImportError:
                logger.warning("Rate limiter not available")
        
        if enable_circuit_breaker:
            try:
                from .circuit_breaker import CircuitBreaker
                cb_config = (config or {}).get("circuit_breaker", {})
                ctx.circuit_breaker = CircuitBreaker(
                    failure_threshold=cb_config.get("failure_threshold", 5),
                    recovery_timeout=cb_config.get("recovery_timeout", 60),
                    name="plugin_converter",
                )
            except ImportError:
                logger.warning("Circuit breaker not available")
        
        if enable_cancellation:
            try:
                from .cancellation import CancellationToken
                ctx.cancellation_token = CancellationToken()
            except ImportError:
                logger.warning("Cancellation token not available")
        
        if enable_memory_manager:
            try:
                from .memory import MemoryManager
                # MemoryManager uses class/static methods, pass the class itself
                ctx.memory_manager = MemoryManager
            except ImportError:
                logger.warning("Memory manager not available")
        
        return ctx


@dataclass
class ConversionOutput:
    """
    Output from a format converter.
    
    Attributes:
        status: Overall status of the conversion.
        entity_types: List of converted entity types.
        relationship_types: List of converted relationship types.
        warnings: Non-fatal warnings during conversion.
        errors: Fatal errors that occurred.
        metadata: Additional format-specific metadata.
        statistics: Conversion statistics (counts, timing, etc.).
    """
    status: ConversionStatus = ConversionStatus.SUCCESS
    entity_types: List[Any] = field(default_factory=list)
    relationship_types: List[Any] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_success(self) -> bool:
        """Check if conversion was fully successful."""
        return self.status == ConversionStatus.SUCCESS
    
    @property
    def has_warnings(self) -> bool:
        """Check if there were any warnings."""
        return len(self.warnings) > 0
    
    @property
    def has_errors(self) -> bool:
        """Check if there were any errors."""
        return len(self.errors) > 0


@dataclass
class ValidationOutput:
    """
    Output from a format validator.
    
    Attributes:
        is_valid: Whether the input is valid.
        errors: List of validation errors.
        warnings: List of validation warnings.
        info: Informational messages.
        metadata: Format-specific metadata extracted during validation.
    """
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class ExportOutput:
    """
    Output from a format exporter.
    
    Attributes:
        success: Whether the export was successful.
        content: The exported content (string or bytes).
        file_path: Path where the content was written (if applicable).
        warnings: Non-fatal warnings during export.
        errors: Fatal errors that occurred.
    """
    success: bool = True
    content: Optional[Union[str, bytes]] = None
    file_path: Optional[Path] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# =============================================================================
# Plugin Interfaces (Abstract Base Classes)
# =============================================================================

class FormatConverter(ABC):
    """
    Abstract base class for format converters.
    
    Implement this class to create a custom converter that transforms
    source files into Fabric Ontology format.
    
    Required Class Attributes:
        format_name: Short identifier for the format (e.g., "rdf", "dtdl").
        file_extensions: List of file extensions this converter handles.
    
    Optional Class Attributes:
        format_description: Human-readable description of the format.
        version: Converter version string.
        author: Converter author.
    
    Example:
        class JSONSchemaConverter(FormatConverter):
            format_name = "jsonschema"
            file_extensions = [".json", ".schema.json"]
            format_description = "JSON Schema to Fabric Ontology converter"
            
            def convert(self, source, context=None, **options):
                # Parse JSON Schema and convert to Fabric format
                pass
            
            def can_convert(self, source):
                # Check if source is a valid JSON Schema
                pass
    """
    
    # Required class attributes (to be overridden by subclasses)
    format_name: str = ""
    file_extensions: List[str] = []
    
    # Optional class attributes
    format_description: str = ""
    version: str = "1.0.0"
    author: str = ""
    
    @abstractmethod
    def convert(
        self,
        source: Union[str, Path, bytes],
        context: Optional[ConversionContext] = None,
        **options: Any
    ) -> ConversionOutput:
        """
        Convert source content to Fabric Ontology format.
        
        Args:
            source: Source content - can be:
                - str: File path or content string
                - Path: Path to source file
                - bytes: Raw file content
            context: Optional conversion context with config and callbacks.
            **options: Format-specific conversion options.
        
        Returns:
            ConversionOutput with entity types, relationship types, and status.
        
        Raises:
            ValueError: If source is invalid or cannot be parsed.
            PluginError: If conversion fails due to plugin issues.
        """
        pass
    
    def can_convert(self, source: Union[str, Path]) -> bool:
        """
        Check if this converter can handle the given source.
        
        Default implementation checks file extension. Override for
        content-based detection.
        
        Args:
            source: File path or content identifier.
        
        Returns:
            True if this converter can handle the source.
        """
        if isinstance(source, (str, Path)):
            path = Path(source) if isinstance(source, str) else source
            return path.suffix.lower() in [ext.lower() for ext in self.file_extensions]
        return False
    
    def get_metadata(self) -> PluginMetadata:
        """Get metadata about this converter."""
        return PluginMetadata(
            name=self.format_description or f"{self.format_name} converter",
            format_name=self.format_name,
            version=self.version,
            author=self.author,
            description=self.format_description,
            file_extensions=list(self.file_extensions),
            plugin_type=PluginType.CONVERTER,
        )


class FormatValidator(ABC):
    """
    Abstract base class for format validators.
    
    Implement this class to create a custom validator that checks
    files for correctness before conversion.
    
    Example:
        class JSONSchemaValidator(FormatValidator):
            format_name = "jsonschema"
            file_extensions = [".json", ".schema.json"]
            
            def validate(self, source, context=None, **options):
                # Validate JSON Schema structure and semantics
                pass
    """
    
    format_name: str = ""
    file_extensions: List[str] = []
    format_description: str = ""
    version: str = "1.0.0"
    author: str = ""
    
    @abstractmethod
    def validate(
        self,
        source: Union[str, Path, bytes],
        context: Optional[ConversionContext] = None,
        **options: Any
    ) -> ValidationOutput:
        """
        Validate source content.
        
        Args:
            source: Source content to validate.
            context: Optional context with config and callbacks.
            **options: Format-specific validation options.
        
        Returns:
            ValidationOutput with validity status and any errors/warnings.
        """
        pass
    
    def can_validate(self, source: Union[str, Path]) -> bool:
        """Check if this validator can handle the given source."""
        if isinstance(source, (str, Path)):
            path = Path(source) if isinstance(source, str) else source
            return path.suffix.lower() in [ext.lower() for ext in self.file_extensions]
        return False
    
    def get_metadata(self) -> PluginMetadata:
        """Get metadata about this validator."""
        return PluginMetadata(
            name=self.format_description or f"{self.format_name} validator",
            format_name=self.format_name,
            version=self.version,
            author=self.author,
            description=self.format_description,
            file_extensions=list(self.file_extensions),
            plugin_type=PluginType.VALIDATOR,
        )


class FormatExporter(ABC):
    """
    Abstract base class for format exporters.
    
    Implement this class to create a custom exporter that converts
    Fabric Ontology definitions to a specific output format.
    
    Example:
        class JSONSchemaExporter(FormatExporter):
            format_name = "jsonschema"
            file_extensions = [".json"]
            
            def export(self, entity_types, relationship_types, context=None, **options):
                # Convert Fabric definitions to JSON Schema
                pass
    """
    
    format_name: str = ""
    file_extensions: List[str] = []
    format_description: str = ""
    version: str = "1.0.0"
    author: str = ""
    
    @abstractmethod
    def export(
        self,
        entity_types: List[Any],
        relationship_types: List[Any],
        context: Optional[ConversionContext] = None,
        **options: Any
    ) -> ExportOutput:
        """
        Export Fabric Ontology definitions to target format.
        
        Args:
            entity_types: List of EntityType objects to export.
            relationship_types: List of RelationshipType objects to export.
            context: Optional context with config and callbacks.
            **options: Format-specific export options.
        
        Returns:
            ExportOutput with exported content and status.
        """
        pass
    
    def get_metadata(self) -> PluginMetadata:
        """Get metadata about this exporter."""
        return PluginMetadata(
            name=self.format_description or f"{self.format_name} exporter",
            format_name=self.format_name,
            version=self.version,
            author=self.author,
            description=self.format_description,
            file_extensions=list(self.file_extensions),
            plugin_type=PluginType.EXPORTER,
        )


# =============================================================================
# Plugin Exceptions
# =============================================================================

class PluginError(Exception):
    """Base exception for plugin-related errors."""
    pass


class PluginLoadError(PluginError):
    """Error loading a plugin."""
    pass


class PluginNotFoundError(PluginError):
    """Plugin not found in registry."""
    pass


class PluginValidationError(PluginError):
    """Plugin failed validation checks."""
    pass


# =============================================================================
# Plugin Registry
# =============================================================================

class PluginRegistry:
    """
    Central registry for format converter plugins.
    
    This singleton class manages plugin discovery, registration, and lookup.
    Plugins can be registered from:
    - Entry points (installed packages)
    - Plugin directory (local plugins)
    - Programmatic registration
    
    Usage:
        # Discover all plugins
        PluginRegistry.discover_plugins()
        
        # Get a converter by format name
        converter = PluginRegistry.get_converter("rdf")
        
        # List all available converters
        converters = PluginRegistry.list_converters()
        
        # Register a custom converter
        PluginRegistry.register_converter(MyConverter())
    """
    
    # Class-level registries (singleton pattern)
    _converters: Dict[str, FormatConverter] = {}
    _validators: Dict[str, FormatValidator] = {}
    _exporters: Dict[str, FormatExporter] = {}
    _extension_map: Dict[str, str] = {}  # extension -> format_name
    _discovered: bool = False
    _plugins_dir: Optional[Path] = None
    
    # Entry point group names
    CONVERTER_ENTRY_POINT = "fabric_ontology.converters"
    VALIDATOR_ENTRY_POINT = "fabric_ontology.validators"
    EXPORTER_ENTRY_POINT = "fabric_ontology.exporters"
    
    @classmethod
    def set_plugins_directory(cls, path: Union[str, Path]) -> None:
        """
        Set the directory to scan for local plugins.
        
        Args:
            path: Path to the plugins directory.
        """
        cls._plugins_dir = Path(path) if isinstance(path, str) else path
        logger.debug(f"Plugins directory set to: {cls._plugins_dir}")
    
    @classmethod
    def discover_plugins(cls, force: bool = False) -> Dict[str, List[str]]:
        """
        Discover and load plugins from all sources.
        
        Args:
            force: Force re-discovery even if already discovered.
        
        Returns:
            Dictionary with lists of discovered plugin names by type.
        """
        if cls._discovered and not force:
            return {
                "converters": list(cls._converters.keys()),
                "validators": list(cls._validators.keys()),
                "exporters": list(cls._exporters.keys()),
            }
        
        discovered = {
            "converters": [],
            "validators": [],
            "exporters": [],
        }
        
        # Discover from entry points
        entry_point_results = cls._discover_entry_points()
        for key in discovered:
            discovered[key].extend(entry_point_results.get(key, []))
        
        # Discover from plugins directory
        if cls._plugins_dir and cls._plugins_dir.exists():
            dir_results = cls._discover_plugins_directory()
            for key in discovered:
                discovered[key].extend(dir_results.get(key, []))
        
        cls._discovered = True
        logger.info(
            f"Plugin discovery complete: {len(discovered['converters'])} converters, "
            f"{len(discovered['validators'])} validators, {len(discovered['exporters'])} exporters"
        )
        
        return discovered
    
    @classmethod
    def _discover_entry_points(cls) -> Dict[str, List[str]]:
        """Discover plugins from setuptools entry points."""
        discovered: Dict[str, List[str]] = {
            "converters": [],
            "validators": [],
            "exporters": [],
        }
        
        # Map entry point groups to registration methods
        entry_point_config = [
            (cls.CONVERTER_ENTRY_POINT, cls._register_converter_internal, "converters"),
            (cls.VALIDATOR_ENTRY_POINT, cls._register_validator_internal, "validators"),
            (cls.EXPORTER_ENTRY_POINT, cls._register_exporter_internal, "exporters"),
        ]
        
        for group_name, register_fn, result_key in entry_point_config:
            try:
                # Python 3.10+ style
                try:
                    entry_points = importlib.metadata.entry_points(group=group_name)
                except TypeError:
                    # Python 3.9 fallback
                    eps = importlib.metadata.entry_points()
                    entry_points = eps.get(group_name, [])
                
                for ep in entry_points:
                    try:
                        plugin_class = ep.load()
                        plugin_instance = plugin_class() if isinstance(plugin_class, type) else plugin_class
                        register_fn(plugin_instance, source="entry_point")
                        discovered[result_key].append(ep.name)
                        logger.debug(f"Loaded {result_key[:-1]} plugin from entry point: {ep.name}")
                    except Exception as e:
                        logger.warning(f"Failed to load entry point {ep.name}: {e}")
            except Exception as e:
                logger.debug(f"Error discovering entry points for {group_name}: {e}")
        
        return discovered
    
    @classmethod
    def _discover_plugins_directory(cls) -> Dict[str, List[str]]:
        """Discover plugins from the plugins directory."""
        discovered: Dict[str, List[str]] = {
            "converters": [],
            "validators": [],
            "exporters": [],
        }
        
        if not cls._plugins_dir or not cls._plugins_dir.exists():
            return discovered
        
        import sys
        
        # Add plugins directory to path if not already there
        plugins_path = str(cls._plugins_dir)
        if plugins_path not in sys.path:
            sys.path.insert(0, plugins_path)
        
        # Look for Python files in the plugins directory
        for plugin_file in cls._plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            
            module_name = plugin_file.stem
            try:
                module = importlib.import_module(module_name)
                
                # Look for plugin classes in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type):
                        # Check if it's a converter
                        if (
                            issubclass(attr, FormatConverter) 
                            and attr is not FormatConverter
                            and hasattr(attr, 'format_name')
                            and attr.format_name
                        ):
                            instance = attr()
                            cls._register_converter_internal(instance, source="directory")
                            discovered["converters"].append(instance.format_name)
                            logger.debug(f"Loaded converter from directory: {instance.format_name}")
                        
                        # Check if it's a validator
                        elif (
                            issubclass(attr, FormatValidator)
                            and attr is not FormatValidator
                            and hasattr(attr, 'format_name')
                            and attr.format_name
                        ):
                            instance = attr()
                            cls._register_validator_internal(instance, source="directory")
                            discovered["validators"].append(instance.format_name)
                            logger.debug(f"Loaded validator from directory: {instance.format_name}")
                        
                        # Check if it's an exporter
                        elif (
                            issubclass(attr, FormatExporter)
                            and attr is not FormatExporter
                            and hasattr(attr, 'format_name')
                            and attr.format_name
                        ):
                            instance = attr()
                            cls._register_exporter_internal(instance, source="directory")
                            discovered["exporters"].append(instance.format_name)
                            logger.debug(f"Loaded exporter from directory: {instance.format_name}")
                            
            except Exception as e:
                logger.warning(f"Failed to load plugin from {plugin_file}: {e}")
        
        return discovered
    
    # -------------------------------------------------------------------------
    # Converter Registration and Lookup
    # -------------------------------------------------------------------------
    
    @classmethod
    def register_converter(cls, converter: FormatConverter) -> None:
        """
        Register a format converter.
        
        Args:
            converter: The converter instance to register.
        
        Raises:
            PluginValidationError: If the converter is invalid.
        """
        cls._validate_converter(converter)
        cls._register_converter_internal(converter, source="programmatic")
    
    @classmethod
    def _register_converter_internal(cls, converter: FormatConverter, source: str = "unknown") -> None:
        """Internal method to register a converter."""
        format_name = converter.format_name.lower()
        cls._converters[format_name] = converter
        
        # Update extension map
        for ext in converter.file_extensions:
            ext_lower = ext.lower()
            if ext_lower in cls._extension_map:
                logger.debug(
                    f"Extension {ext} already mapped to {cls._extension_map[ext_lower]}, "
                    f"overriding with {format_name}"
                )
            cls._extension_map[ext_lower] = format_name
        
        # Update metadata source
        metadata = converter.get_metadata()
        metadata.source = source
        
        logger.info(f"Registered converter: {format_name} ({source})")
    
    @classmethod
    def _validate_converter(cls, converter: FormatConverter) -> None:
        """Validate a converter before registration."""
        if not converter.format_name:
            raise PluginValidationError("Converter must have a format_name")
        if not converter.file_extensions:
            raise PluginValidationError("Converter must have at least one file_extension")
        if not hasattr(converter, 'convert') or not callable(converter.convert):
            raise PluginValidationError("Converter must implement convert() method")
    
    @classmethod
    def get_converter(cls, format_name: str) -> FormatConverter:
        """
        Get a converter by format name.
        
        Args:
            format_name: The format name (e.g., "rdf", "dtdl").
        
        Returns:
            The registered converter.
        
        Raises:
            PluginNotFoundError: If no converter is registered for the format.
        """
        format_lower = format_name.lower()
        if format_lower not in cls._converters:
            raise PluginNotFoundError(f"No converter registered for format: {format_name}")
        return cls._converters[format_lower]
    
    @classmethod
    def get_converter_for_file(cls, file_path: Union[str, Path]) -> Optional[FormatConverter]:
        """
        Get a converter based on file extension.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            The appropriate converter, or None if no match.
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path
        ext = path.suffix.lower()
        
        if ext in cls._extension_map:
            format_name = cls._extension_map[ext]
            return cls._converters.get(format_name)
        
        return None
    
    @classmethod
    def list_converters(cls) -> List[PluginMetadata]:
        """List all registered converters with their metadata."""
        return [c.get_metadata() for c in cls._converters.values()]
    
    @classmethod
    def has_converter(cls, format_name: str) -> bool:
        """Check if a converter is registered for the given format."""
        return format_name.lower() in cls._converters
    
    # -------------------------------------------------------------------------
    # Validator Registration and Lookup
    # -------------------------------------------------------------------------
    
    @classmethod
    def register_validator(cls, validator: FormatValidator) -> None:
        """Register a format validator."""
        cls._validate_validator(validator)
        cls._register_validator_internal(validator, source="programmatic")
    
    @classmethod
    def _register_validator_internal(cls, validator: FormatValidator, source: str = "unknown") -> None:
        """Internal method to register a validator."""
        format_name = validator.format_name.lower()
        cls._validators[format_name] = validator
        logger.info(f"Registered validator: {format_name} ({source})")
    
    @classmethod
    def _validate_validator(cls, validator: FormatValidator) -> None:
        """Validate a validator before registration."""
        if not validator.format_name:
            raise PluginValidationError("Validator must have a format_name")
        if not hasattr(validator, 'validate') or not callable(validator.validate):
            raise PluginValidationError("Validator must implement validate() method")
    
    @classmethod
    def get_validator(cls, format_name: str) -> FormatValidator:
        """Get a validator by format name."""
        format_lower = format_name.lower()
        if format_lower not in cls._validators:
            raise PluginNotFoundError(f"No validator registered for format: {format_name}")
        return cls._validators[format_lower]
    
    @classmethod
    def list_validators(cls) -> List[PluginMetadata]:
        """List all registered validators with their metadata."""
        return [v.get_metadata() for v in cls._validators.values()]
    
    @classmethod
    def has_validator(cls, format_name: str) -> bool:
        """Check if a validator is registered for the given format."""
        return format_name.lower() in cls._validators
    
    # -------------------------------------------------------------------------
    # Exporter Registration and Lookup
    # -------------------------------------------------------------------------
    
    @classmethod
    def register_exporter(cls, exporter: FormatExporter) -> None:
        """Register a format exporter."""
        cls._validate_exporter(exporter)
        cls._register_exporter_internal(exporter, source="programmatic")
    
    @classmethod
    def _register_exporter_internal(cls, exporter: FormatExporter, source: str = "unknown") -> None:
        """Internal method to register an exporter."""
        format_name = exporter.format_name.lower()
        cls._exporters[format_name] = exporter
        logger.info(f"Registered exporter: {format_name} ({source})")
    
    @classmethod
    def _validate_exporter(cls, exporter: FormatExporter) -> None:
        """Validate an exporter before registration."""
        if not exporter.format_name:
            raise PluginValidationError("Exporter must have a format_name")
        if not hasattr(exporter, 'export') or not callable(exporter.export):
            raise PluginValidationError("Exporter must implement export() method")
    
    @classmethod
    def get_exporter(cls, format_name: str) -> FormatExporter:
        """Get an exporter by format name."""
        format_lower = format_name.lower()
        if format_lower not in cls._exporters:
            raise PluginNotFoundError(f"No exporter registered for format: {format_name}")
        return cls._exporters[format_lower]
    
    @classmethod
    def list_exporters(cls) -> List[PluginMetadata]:
        """List all registered exporters with their metadata."""
        return [e.get_metadata() for e in cls._exporters.values()]
    
    @classmethod
    def has_exporter(cls, format_name: str) -> bool:
        """Check if an exporter is registered for the given format."""
        return format_name.lower() in cls._exporters
    
    # -------------------------------------------------------------------------
    # General Plugin Operations
    # -------------------------------------------------------------------------
    
    @classmethod
    def unregister(cls, format_name: str, plugin_type: Optional[PluginType] = None) -> bool:
        """
        Unregister a plugin.
        
        Args:
            format_name: The format name of the plugin.
            plugin_type: Specific type to unregister, or None for all types.
        
        Returns:
            True if any plugin was unregistered.
        """
        format_lower = format_name.lower()
        removed = False
        
        if plugin_type is None or plugin_type == PluginType.CONVERTER:
            if format_lower in cls._converters:
                converter = cls._converters.pop(format_lower)
                # Clean up extension map
                for ext in converter.file_extensions:
                    ext_lower = ext.lower()
                    if cls._extension_map.get(ext_lower) == format_lower:
                        del cls._extension_map[ext_lower]
                removed = True
                logger.info(f"Unregistered converter: {format_name}")
        
        if plugin_type is None or plugin_type == PluginType.VALIDATOR:
            if format_lower in cls._validators:
                del cls._validators[format_lower]
                removed = True
                logger.info(f"Unregistered validator: {format_name}")
        
        if plugin_type is None or plugin_type == PluginType.EXPORTER:
            if format_lower in cls._exporters:
                del cls._exporters[format_lower]
                removed = True
                logger.info(f"Unregistered exporter: {format_name}")
        
        return removed
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered plugins. Useful for testing."""
        cls._converters.clear()
        cls._validators.clear()
        cls._exporters.clear()
        cls._extension_map.clear()
        cls._discovered = False
        logger.info("Plugin registry cleared")
    
    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Get all file extensions supported by registered converters."""
        return list(cls._extension_map.keys())
    
    @classmethod
    def get_all_plugins(cls) -> Dict[str, List[PluginMetadata]]:
        """Get all registered plugins organized by type."""
        return {
            "converters": cls.list_converters(),
            "validators": cls.list_validators(),
            "exporters": cls.list_exporters(),
        }


# =============================================================================
# Built-in Plugin Wrappers
# =============================================================================

class RDFConverterPlugin(FormatConverter):
    """
    Built-in RDF/TTL converter wrapped as a plugin.
    
    This wraps the existing RDFToFabricConverter to make it available
    through the plugin system.
    """
    
    format_name = "rdf"
    file_extensions = [".ttl", ".rdf", ".owl", ".n3", ".nt"]
    format_description = "RDF/OWL/TTL to Fabric Ontology converter"
    version = "1.0.0"
    author = "Fabric Ontology Team"
    
    def __init__(self) -> None:
        self._converter = None
    
    def _get_converter(self) -> Any:
        """Lazy-load the RDF converter."""
        if self._converter is None:
            try:
                from ..rdf import RDFToFabricConverter
            except ImportError:
                from rdf import RDFToFabricConverter
            self._converter = RDFToFabricConverter()
        return self._converter
    
    def convert(
        self,
        source: Union[str, Path, bytes],
        context: Optional[ConversionContext] = None,
        **options: Any
    ) -> ConversionOutput:
        """Convert RDF/TTL content to Fabric Ontology format."""
        converter = self._get_converter()
        output = ConversionOutput()
        
        try:
            # Determine source type and convert
            if isinstance(source, bytes):
                content = source.decode('utf-8')
                result = converter.convert_to_fabric_definition(content)
            elif isinstance(source, Path) or (isinstance(source, str) and Path(source).exists()):
                result = converter.convert_file_to_fabric_definition(str(source))
            else:
                # Assume string content
                result = converter.convert_to_fabric_definition(source)
            
            # Map result to output
            output.entity_types = result.entity_types
            output.relationship_types = result.relationship_types
            output.warnings = result.warnings
            output.statistics = {
                "triple_count": result.triple_count,
                "entity_count": len(result.entity_types),
                "relationship_count": len(result.relationship_types),
                "skipped_count": len(result.skipped_items),
            }
            
            if result.skipped_items:
                output.status = ConversionStatus.PARTIAL
                for item in result.skipped_items:
                    output.warnings.append(f"Skipped {item.item_type}: {item.name} - {item.reason}")
            
        except Exception as e:
            output.status = ConversionStatus.FAILED
            output.errors.append(str(e))
            logger.error(f"RDF conversion failed: {e}")
        
        return output


class DTDLConverterPlugin(FormatConverter):
    """
    Built-in DTDL converter wrapped as a plugin.
    
    This wraps the existing DTDLToFabricConverter to make it available
    through the plugin system.
    """
    
    format_name = "dtdl"
    file_extensions = [".json"]
    format_description = "DTDL (Digital Twins Definition Language) to Fabric Ontology converter"
    version = "1.0.0"
    author = "Fabric Ontology Team"
    
    def __init__(self) -> None:
        self._converter = None
        self._parser = None
    
    def _get_converter(self) -> Any:
        """Lazy-load the DTDL converter."""
        if self._converter is None:
            try:
                from ..dtdl import DTDLToFabricConverter, DTDLParser
            except ImportError:
                from dtdl import DTDLToFabricConverter, DTDLParser
            self._converter = DTDLToFabricConverter()
            self._parser = DTDLParser()
        return self._converter
    
    def can_convert(self, source: Union[str, Path]) -> bool:
        """Check if source is a DTDL JSON file."""
        if isinstance(source, (str, Path)):
            path = Path(source) if isinstance(source, str) else source
            if path.suffix.lower() != '.json':
                return False
            
            # Try to detect DTDL content
            try:
                import json
                if path.exists():
                    with open(path, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                    # Check for DTDL markers
                    if isinstance(content, list):
                        content = content[0] if content else {}
                    return (
                        '@context' in content and 
                        ('dtmi:' in str(content.get('@context', '')) or 
                         'dtdl' in str(content.get('@context', '')).lower())
                    )
            except Exception:
                pass
        return False
    
    def convert(
        self,
        source: Union[str, Path, bytes],
        context: Optional[ConversionContext] = None,
        **options: Any
    ) -> ConversionOutput:
        """Convert DTDL content to Fabric Ontology format."""
        converter = self._get_converter()
        output = ConversionOutput()
        
        try:
            import json
            
            # Parse source
            if isinstance(source, bytes):
                content = json.loads(source.decode('utf-8'))
            elif isinstance(source, Path) or (isinstance(source, str) and Path(source).exists()):
                with open(source, 'r', encoding='utf-8') as f:
                    content = json.load(f)
            else:
                content = json.loads(source)
            
            # Parse DTDL
            interfaces = self._parser.parse(content)
            
            # Convert to Fabric
            result = converter.convert(interfaces)
            
            # Map result to output
            output.entity_types = result.entity_types
            output.relationship_types = result.relationship_types
            output.warnings = result.warnings
            output.statistics = {
                "interface_count": result.interface_count,
                "entity_count": len(result.entity_types),
                "relationship_count": len(result.relationship_types),
                "skipped_count": len(result.skipped_items),
            }
            
            if result.skipped_items:
                output.status = ConversionStatus.PARTIAL
                for item in result.skipped_items:
                    output.warnings.append(f"Skipped {item.item_type}: {item.name} - {item.reason}")
            
        except Exception as e:
            output.status = ConversionStatus.FAILED
            output.errors.append(str(e))
            logger.error(f"DTDL conversion failed: {e}")
        
        return output


def register_builtin_plugins() -> None:
    """
    Register the built-in RDF and DTDL converters as plugins.
    
    This is called automatically when the plugin system is first used,
    but can also be called explicitly.
    """
    try:
        if not PluginRegistry.has_converter("rdf"):
            PluginRegistry.register_converter(RDFConverterPlugin())
    except Exception as e:
        logger.debug(f"Could not register RDF plugin: {e}")
    
    try:
        if not PluginRegistry.has_converter("dtdl"):
            PluginRegistry.register_converter(DTDLConverterPlugin())
    except Exception as e:
        logger.debug(f"Could not register DTDL plugin: {e}")


# =============================================================================
# Module Initialization
# =============================================================================

# Auto-register built-in plugins when module is imported
# Deferred to avoid circular imports
_builtin_registered = False


def ensure_builtins_registered() -> None:
    """Ensure built-in plugins are registered."""
    global _builtin_registered
    if not _builtin_registered:
        register_builtin_plugins()
        _builtin_registered = True


__all__ = [
    # Types and Enums
    "PluginType",
    "ConversionStatus",
    # Data Classes
    "PluginMetadata",
    "ConversionContext",
    "ConversionOutput",
    "ValidationOutput",
    "ExportOutput",
    # Plugin Base Classes
    "FormatConverter",
    "FormatValidator",
    "FormatExporter",
    # Registry
    "PluginRegistry",
    # Built-in Plugins
    "RDFConverterPlugin",
    "DTDLConverterPlugin",
    # Exceptions
    "PluginError",
    "PluginLoadError",
    "PluginNotFoundError",
    "PluginValidationError",
    # Functions
    "register_builtin_plugins",
    "ensure_builtins_registered",
]
