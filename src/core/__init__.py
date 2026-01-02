"""
Core utilities and cross-cutting concerns for the RDF/DTDL Fabric Ontology Converter.

This module provides shared infrastructure components used across all format converters
and the Fabric client, including:

- Rate limiting (TokenBucketRateLimiter, NoOpRateLimiter)
- Circuit breaker pattern (CircuitBreaker, CircuitState, CircuitBreakerOpenError)
- Cancellation handling (CancellationToken, CancellationTokenSource, setup_cancellation_handler)
- Memory management (MemoryManager)
- Input validation (InputValidator)
- Configuration constants (ExitCode, MemoryLimits, APIConfig, etc.)

Usage:
    from core import CircuitBreaker, CancellationToken, MemoryManager, InputValidator
    from core import ExitCode, APIConfig
    from core.rate_limiter import TokenBucketRateLimiter
    from core.cancellation import setup_cancellation_handler
    from core.validators import InputValidator
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

# Input validation
from .validators import InputValidator

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
    # Input validation
    "InputValidator",
    # Constants
    "ExitCode",
    "MemoryLimits",
    "ProcessingLimits",
    "APIConfig",
    "IDConfig",
    "FileExtensions",
    "NamespaceConfig",
    "LoggingConfig",
]
