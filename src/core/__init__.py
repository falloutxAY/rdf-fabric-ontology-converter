"""
Core utilities and cross-cutting concerns for the RDF/DTDL Fabric Ontology Converter.

This module provides shared infrastructure components used across all format converters,
including:

- Fabric API client (FabricConfig, FabricOntologyClient, FabricAPIError)
- Rate limiting (TokenBucketRateLimiter, NoOpRateLimiter)
- Circuit breaker pattern (CircuitBreaker, CircuitState, CircuitBreakerOpenError)
- Cancellation handling (CancellationToken, CancellationTokenSource, setup_cancellation_handler)
- Memory management (MemoryManager)
- Input validation (InputValidator)
- Configuration constants (ExitCode, MemoryLimits, APIConfig, etc.)
- Authentication helpers (TokenManager, CredentialFactory)
- HTTP client utilities (RequestHandler, ResponseHandler)
- Long-running operation handling (LROHandler)

Usage:
    from core import FabricConfig, FabricOntologyClient, FabricAPIError
    from core import CircuitBreaker, CancellationToken, MemoryManager, InputValidator
    from core import ExitCode, APIConfig
    from core.rate_limiter import TokenBucketRateLimiter
    from core.cancellation import setup_cancellation_handler
    from core.validators import InputValidator
    from core.auth import TokenManager, CredentialFactory
    from core.http_client import RequestHandler, ResponseHandler
    from core.lro_handler import LROHandler
    from core.platform.fabric_client import FabricOntologyClient
"""

# Rate limiting
from .rate_limiter import (
    RateLimiter,
    TokenBucketRateLimiter,
    NoOpRateLimiter,
)

# Circuit breaker pattern
from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerOpenError,
    CircuitBreakerMetrics,
    CircuitBreakerRegistry,
    get_circuit_breaker,
    register_circuit_breaker,
    get_or_create_circuit_breaker,
)

# Cancellation handling
from .cancellation import (
    CancellationToken,
    CancellationTokenSource,
    OperationCancelledException,
    setup_cancellation_handler,
    restore_default_handler,
    get_global_token,
)

# Memory management
from .memory import MemoryManager

# Authentication helpers
from .auth import (
    TokenManager,
    CredentialFactory,
    AuthenticationError,
    FABRIC_SCOPE,
)

# HTTP client utilities
from .http_client import (
    RequestHandler,
    ResponseHandler,
    TransientAPIError,
    FabricAPIError,
    HttpMethod,
    is_transient_error,
    get_retry_wait_time,
    sanitize_display_name,
)

# Long-running operation handling
from .lro_handler import LROHandler

# Fabric API client - import directly from platform to avoid deprecation warning
from .platform.fabric_client import (
    FabricConfig,
    FabricOntologyClient,
    FabricAPIError,
    TransientAPIError as FabricTransientAPIError,
    RateLimitConfig,
    CircuitBreakerSettings,
)

# Input validation and Fabric limits
from .validators import (
    InputValidator,
    URLValidator,
    ValidationRateLimiter,
    FabricLimitsValidator,
    FabricLimitValidationError,
    EntityIdPartsInferrer,
)

# Compliance validation and conversion warnings
from .compliance import (
    ComplianceLevel,
    ConversionImpact,
    DTDLVersion,
    ComplianceIssue,
    ConversionWarning,
    ComplianceResult,
    ConversionReport,
    DTDLComplianceValidator,
    RDFOWLComplianceValidator,
    FabricComplianceChecker,
    ConversionReportGenerator,
    DTDL_LIMITS,
    OWL_CONSTRUCT_SUPPORT,
    DTDL_FEATURE_SUPPORT,
)

# Streaming engine for memory-efficient processing
from .streaming import (
    StreamFormat,
    StreamConfig,
    StreamStats,
    StreamResult,
    ChunkProcessor,
    StreamReader,
    StreamingEngine,
    RDFChunk,
    RDFPartialResult,
    RDFStreamReader,
    RDFChunkProcessor,
    RDFStreamAdapter,
    DTDLChunk,
    DTDLPartialResult,
    DTDLStreamReader,
    DTDLChunkProcessor,
    DTDLStreamAdapter,
    should_use_streaming,
    get_streaming_threshold,
)

# Re-export constants from parent module
try:
    from ..constants import (
        ExitCode,
        MemoryLimits,
        ProcessingLimits,
        APIConfig,
        IDConfig,
        FileExtensions,
        NamespaceConfig,
        LoggingConfig,
        FabricLimits,
        EntityIdPartsConfig,
    )
except ImportError:
    # Fallback if running standalone
    pass


__all__ = [
    # Rate limiting
    "RateLimiter",
    "TokenBucketRateLimiter",
    "NoOpRateLimiter",
    # Circuit breaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerOpenError",
    "CircuitBreakerMetrics",
    "CircuitBreakerRegistry",
    "get_circuit_breaker",
    "register_circuit_breaker",
    "get_or_create_circuit_breaker",
    # Cancellation
    "CancellationToken",
    "CancellationTokenSource",
    "OperationCancelledException",
    "setup_cancellation_handler",
    "restore_default_handler",
    "get_global_token",
    # Memory management
    "MemoryManager",
    # Authentication
    "TokenManager",
    "CredentialFactory",
    "AuthenticationError",
    "FABRIC_SCOPE",
    # HTTP client
    "RequestHandler",
    "ResponseHandler",
    "TransientAPIError",
    "FabricAPIError",
    "HttpMethod",
    "is_transient_error",
    "get_retry_wait_time",
    "sanitize_display_name",
    # LRO handling
    "LROHandler",
    # Fabric API client
    "FabricConfig",
    "FabricOntologyClient",
    "FabricAPIError",
    "FabricTransientAPIError",
    "RateLimitConfig",
    "CircuitBreakerSettings",
    # Input validation and Fabric limits
    "InputValidator",
    "URLValidator",
    "ValidationRateLimiter",
    "FabricLimitsValidator",
    "FabricLimitValidationError",
    "EntityIdPartsInferrer",
    # Compliance validation and conversion warnings
    "ComplianceLevel",
    "ConversionImpact",
    "DTDLVersion",
    "ComplianceIssue",
    "ConversionWarning",
    "ComplianceResult",
    "ConversionReport",
    "DTDLComplianceValidator",
    "RDFOWLComplianceValidator",
    "FabricComplianceChecker",
    "ConversionReportGenerator",
    "DTDL_LIMITS",
    "OWL_CONSTRUCT_SUPPORT",
    "DTDL_FEATURE_SUPPORT",
    # Streaming engine
    "StreamFormat",
    "StreamConfig",
    "StreamStats",
    "StreamResult",
    "ChunkProcessor",
    "StreamReader",
    "StreamingEngine",
    "RDFChunk",
    "RDFPartialResult",
    "RDFStreamReader",
    "RDFChunkProcessor",
    "RDFStreamAdapter",
    "DTDLChunk",
    "DTDLPartialResult",
    "DTDLStreamReader",
    "DTDLChunkProcessor",
    "DTDLStreamAdapter",
    "should_use_streaming",
    "get_streaming_threshold",
    # Constants
    "ExitCode",
    "MemoryLimits",
    "ProcessingLimits",
    "APIConfig",
    "IDConfig",
    "FileExtensions",
    "NamespaceConfig",
    "LoggingConfig",
    "FabricLimits",
    "EntityIdPartsConfig",
]
