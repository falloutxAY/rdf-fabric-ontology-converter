"""
Centralized configuration constants for the RDF/DTDL Fabric Ontology Converter.

This module provides a single source of truth for all configuration constants,
default values, and limits used throughout the application.
"""

from enum import IntEnum
from typing import Final

# ============================================================================
# Exit Codes
# ============================================================================

class ExitCode(IntEnum):
    """Standard exit codes for CLI commands.
    
    Following Unix conventions:
    - 0: Success
    - 1: General error
    - 2: Validation/syntax error
    - 3+: Specific error categories
    """
    SUCCESS = 0
    ERROR = 1
    VALIDATION_ERROR = 2
    CONFIG_ERROR = 3
    API_ERROR = 4
    FILE_NOT_FOUND = 5
    PERMISSION_DENIED = 6
    CANCELLED = 7
    TIMEOUT = 8


# ============================================================================
# Memory Management
# ============================================================================

class MemoryLimits:
    """Memory management constants."""
    
    MAX_SAFE_FILE_MB: Final[int] = 500
    """Default maximum file size without explicit override (MB)."""
    
    MEMORY_MULTIPLIER: Final[float] = 3.5
    """RDFlib typically uses ~3-4x file size in memory."""
    
    MIN_AVAILABLE_MEMORY_MB: Final[int] = 512
    """Minimum available memory required before processing (MB)."""
    
    STREAMING_THRESHOLD_MB: Final[int] = 100
    """Files larger than this use streaming mode (MB)."""


# ============================================================================
# Processing Limits
# ============================================================================

class ProcessingLimits:
    """Processing and traversal limits."""
    
    DEFAULT_MAX_DEPTH: Final[int] = 10
    """Maximum depth for graph traversal."""
    
    MAX_INHERITANCE_DEPTH: Final[int] = 12
    """Maximum inheritance chain depth (DTDL spec limit)."""
    
    MAX_NESTED_DEPTH: Final[int] = 8
    """Maximum nesting depth for complex objects."""
    
    MAX_BATCH_SIZE: Final[int] = 100
    """Maximum items per batch operation."""
    
    MAX_PROPERTIES_PER_ENTITY: Final[int] = 500
    """Maximum properties per entity type."""
    
    MAX_RELATIONSHIPS_PER_ENTITY: Final[int] = 100
    """Maximum relationships per entity type."""


# ============================================================================
# API Configuration
# ============================================================================

class APIConfig:
    """Fabric API configuration constants."""
    
    DEFAULT_RATE_LIMIT: Final[int] = 100
    """Requests per minute."""
    
    DEFAULT_BURST_SIZE: Final[int] = 10
    """Maximum burst of requests."""
    
    DEFAULT_TIMEOUT_SECONDS: Final[int] = 30
    """Default HTTP request timeout."""
    
    MAX_POLL_ATTEMPTS: Final[int] = 60
    """Maximum polling attempts for async operations."""
    
    POLL_INTERVAL_SECONDS: Final[int] = 5
    """Seconds between poll attempts."""
    
    CIRCUIT_BREAKER_THRESHOLD: Final[int] = 5
    """Failures before circuit opens."""
    
    CIRCUIT_BREAKER_TIMEOUT: Final[int] = 60
    """Seconds before circuit resets."""


# ============================================================================
# ID Generation
# ============================================================================

class IDConfig:
    """ID generation configuration."""
    
    DEFAULT_ID_PREFIX: Final[int] = 1000000000000
    """Default starting prefix for generated IDs."""
    
    ID_LENGTH: Final[int] = 13
    """Length of numeric IDs."""
    
    ENTITY_ID_OFFSET: Final[int] = 0
    """Offset for entity type IDs."""
    
    RELATIONSHIP_ID_OFFSET: Final[int] = 100000000
    """Offset for relationship type IDs."""
    
    PROPERTY_ID_OFFSET: Final[int] = 1
    """Starting offset for property IDs within entities."""


# ============================================================================
# File Extensions
# ============================================================================

class FileExtensions:
    """Supported file extensions."""
    
    TTL_EXTENSIONS: Final[tuple] = ('.ttl', '.turtle', '.n3')
    """Valid RDF/TTL file extensions."""
    
    DTDL_EXTENSIONS: Final[tuple] = ('.json',)
    """Valid DTDL file extensions."""
    
    OUTPUT_EXTENSIONS: Final[tuple] = ('.json', '.ttl')
    """Valid output file extensions."""


# ============================================================================
# Namespace Defaults
# ============================================================================

class NamespaceConfig:
    """Namespace configuration defaults."""
    
    DEFAULT_NAMESPACE: Final[str] = "usertypes"
    """Default Fabric namespace."""
    
    DEFAULT_NAMESPACE_TYPE: Final[str] = "Custom"
    """Default namespace type."""
    
    DEFAULT_VISIBILITY: Final[str] = "Visible"
    """Default entity visibility."""


# ============================================================================
# Logging
# ============================================================================

class LoggingConfig:
    """Logging configuration."""
    
    DEFAULT_LOG_LEVEL: Final[str] = "INFO"
    """Default logging level."""
    
    LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    """Default log format string."""
    
    DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
    """Default date format for logs."""

    DEFAULT_FORMAT_STYLE: Final[str] = "text"
    """Human-readable formatter style."""

    JSON_DATE_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S.%fZ"
    """ISO-8601 timestamp format for structured logs."""
    
    SUPPORTED_FORMATS: Final[tuple[str, ...]] = ("text", "json")
    """Supported formatter styles."""
    
    MAX_LOG_FILE_MB: Final[int] = 10
    """Maximum log file size before rotation (MB)."""
    
    LOG_BACKUP_COUNT: Final[int] = 5
    """Number of backup log files to keep."""

    ROTATION_ENABLED: Final[bool] = True
    """Enable log rotation by default when a file handler is configured."""
