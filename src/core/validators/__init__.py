"""
Centralized validation utilities for the RDF/DTDL Fabric Ontology Converter.

This package provides validators organized by concern:
- input.py: File path and content validation with security checks
- url.py: URL validation and SSRF protection
- rate_limiter.py: Rate limiting and resource guards for validation operations
- fabric_limits.py: Fabric API limits validation

Module Structure (refactored for maintainability):
- input.py: InputValidator - file/content validation with security
- url.py: URLValidator - SSRF protection for URLs
- rate_limiter.py: ValidationRateLimiter, ValidationContext - rate limiting
- fabric_limits.py: FabricLimitsValidator, EntityIdPartsInferrer - Fabric limits

Usage:
    # Imports from submodules
    from core.validators import InputValidator, URLValidator
    from core.validators import FabricLimitsValidator, EntityIdPartsInferrer
    
    # Or import specific submodules
    from core.validators.rate_limiter import ValidationRateLimiter
"""

# Import from submodules
from .input import InputValidator
from .url import URLValidator
from .rate_limiter import ValidationRateLimiter, ValidationContext
from .fabric_limits import (
    FabricLimitValidationError,
    FabricLimitsValidator,
    EntityIdPartsInferrer,
)

__all__ = [
    # Input validation
    'InputValidator',
    # URL validation
    'URLValidator',
    # Rate limiting
    'ValidationRateLimiter',
    'ValidationContext',
    # Fabric limits
    'FabricLimitValidationError',
    'FabricLimitsValidator',
    'EntityIdPartsInferrer',
]
