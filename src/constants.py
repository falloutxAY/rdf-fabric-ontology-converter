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
# Fabric API Limits
# ============================================================================

class FabricLimits:
    """
    Microsoft Fabric Ontology API limits and constraints.
    
    These limits are based on the Fabric Ontology API documentation and
    real-world testing. Values are conservative to ensure compatibility.
    
    Reference:
        https://learn.microsoft.com/en-us/rest/api/fabric/ontology
    """
    
    # Name length limits (characters) - standardized to 26 per validation-rules.yaml
    # Note: Names exceeding limit will be truncated with warning during import
    MAX_ENTITY_NAME_LENGTH: Final[int] = 26
    """Maximum length for entity type names."""
    
    MAX_PROPERTY_NAME_LENGTH: Final[int] = 26
    """Maximum length for property names."""
    
    MAX_RELATIONSHIP_NAME_LENGTH: Final[int] = 26
    """Maximum length for relationship type names."""
    
    MAX_NAMESPACE_LENGTH: Final[int] = 128
    """Maximum length for namespace names."""
    
    # ID format constraints
    MIN_ID_LENGTH: Final[int] = 1
    """Minimum length for IDs."""
    
    MAX_ID_LENGTH: Final[int] = 64
    """Maximum length for IDs."""
    
    # Definition size limits (KB)
    MAX_DEFINITION_SIZE_KB: Final[int] = 1024
    """Maximum total definition size (1 MB)."""
    
    WARN_DEFINITION_SIZE_KB: Final[int] = 768
    """Warning threshold for definition size (75% of max)."""
    
    # Count limits
    MAX_ENTITY_TYPES: Final[int] = 500
    """Maximum number of entity types per ontology."""
    
    MAX_RELATIONSHIP_TYPES: Final[int] = 500
    """Maximum number of relationship types per ontology."""
    
    MAX_PROPERTIES_PER_ENTITY: Final[int] = 200
    """Maximum properties per entity type."""
    
    MAX_ENTITY_ID_PARTS: Final[int] = 5
    """Maximum number of properties in entityIdParts."""
    
    # Inheritance limits
    MAX_INHERITANCE_DEPTH: Final[int] = 10
    """Maximum inheritance chain depth."""


# ============================================================================
# Entity ID Parts Configuration
# ============================================================================

class EntityIdPartsConfig:
    """
    Configuration for entityIdParts inference and behavior.
    
    entityIdParts defines which properties form the unique identity of an entity.
    This is crucial for Fabric to correctly identify and deduplicate entities.
    """
    
    # Inference strategies
    STRATEGY_AUTO: Final[str] = "auto"
    """Automatically infer from property names and types."""
    
    STRATEGY_FIRST_VALID: Final[str] = "first_valid"
    """Use the first valid (String/BigInt) property."""
    
    STRATEGY_EXPLICIT: Final[str] = "explicit"
    """Only set if explicitly configured."""
    
    STRATEGY_NONE: Final[str] = "none"
    """Never set entityIdParts automatically."""
    
    DEFAULT_STRATEGY: Final[str] = "auto"
    """Default inference strategy."""
    
    # Property name patterns for primary key detection (case-insensitive)
    PRIMARY_KEY_PATTERNS: Final[tuple[str, ...]] = (
        "id",
        "identifier",
        "pk",
        "primary_key",
        "primarykey",
        "key",
        "uuid",
        "guid",
        "oid",
        "object_id",
        "objectid",
        "entity_id",
        "entityid",
        "record_id",
        "recordid",
        "unique_id",
        "uniqueid",
    )
    """Patterns that indicate a property is a primary key."""
    
    # Valid types for entityIdParts (Fabric requirement)
    VALID_TYPES: Final[tuple[str, ...]] = ("String", "BigInt")
    """Only these Fabric types can be used in entityIdParts."""


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
