"""
Validation Rate Limiter.

Provides rate limiting and resource guards for validation operations.
"""

import logging
import threading
import time
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)


class ValidationRateLimiter:
    """
    Rate limiter and resource guard for local validation operations.
    
    Provides protection against resource exhaustion attacks by limiting:
    - Number of validation requests per time period
    - Maximum content size per validation
    - Maximum concurrent validations
    - Memory usage during validation
    
    This is useful when exposing validation as a service or endpoint,
    preventing denial-of-service through excessive validation requests.
    
    Usage:
        from core.validators import ValidationRateLimiter
        
        # Create limiter with default settings
        limiter = ValidationRateLimiter()
        
        # Check if validation is allowed
        allowed, reason = limiter.check_validation_allowed(content)
        if not allowed:
            raise ValueError(f"Validation not allowed: {reason}")
        
        # Use context manager for automatic tracking
        with limiter.validation_context() as ctx:
            if not ctx.allowed:
                raise ValueError(ctx.reason)
            # Perform validation
            result = validate_content(content)
    """
    
    # Default configuration
    DEFAULT_REQUESTS_PER_MINUTE = 30
    DEFAULT_MAX_CONTENT_SIZE_MB = 50
    DEFAULT_MAX_CONCURRENT = 5
    DEFAULT_MAX_MEMORY_PERCENT = 80
    
    def __init__(
        self,
        requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
        max_content_size_mb: float = DEFAULT_MAX_CONTENT_SIZE_MB,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        max_memory_percent: float = DEFAULT_MAX_MEMORY_PERCENT,
        enabled: bool = True,
    ):
        """
        Initialize the validation rate limiter.
        
        Args:
            requests_per_minute: Maximum validation requests per minute
            max_content_size_mb: Maximum content size in MB for single validation
            max_concurrent: Maximum concurrent validation operations
            max_memory_percent: Maximum system memory usage percent before rejecting
            enabled: Whether rate limiting is enabled
        """
        self.requests_per_minute = requests_per_minute
        self.max_content_size_mb = max_content_size_mb
        self.max_concurrent = max_concurrent
        self.max_memory_percent = max_memory_percent
        self.enabled = enabled
        
        # Internal state
        self._lock = threading.Lock()
        self._request_times: List[float] = []
        self._concurrent_count = 0
        
        # Statistics
        self._total_validations = 0
        self._rejected_rate_limit = 0
        self._rejected_size = 0
        self._rejected_memory = 0
        self._rejected_concurrent = 0
    
    def _cleanup_old_requests(self) -> None:
        """Remove request timestamps older than 1 minute."""
        cutoff = time.time() - 60
        self._request_times = [t for t in self._request_times if t > cutoff]
    
    def _get_memory_percent(self) -> float:
        """Get current system memory usage percentage."""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            # psutil not available - assume safe
            return 0.0
        except Exception:
            # Error getting memory - assume safe
            return 0.0
    
    def _get_content_size_mb(self, content: str) -> float:
        """Get content size in MB."""
        return len(content.encode('utf-8')) / (1024 * 1024)
    
    def check_rate_limit(self) -> tuple:
        """
        Check if request rate is within limits.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        if not self.enabled:
            return True, "Rate limiting disabled"
        
        with self._lock:
            self._cleanup_old_requests()
            
            if len(self._request_times) >= self.requests_per_minute:
                oldest = self._request_times[0]
                wait_time = 60 - (time.time() - oldest)
                return False, f"Rate limit exceeded. Try again in {wait_time:.1f} seconds"
            
            return True, "Within rate limit"
    
    def check_content_size(self, content: str) -> tuple:
        """
        Check if content size is within limits.
        
        Args:
            content: Content to validate
            
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        if not self.enabled:
            return True, "Size limiting disabled"
        
        size_mb = self._get_content_size_mb(content)
        
        if size_mb > self.max_content_size_mb:
            return False, (
                f"Content size ({size_mb:.2f} MB) exceeds maximum "
                f"({self.max_content_size_mb} MB)"
            )
        
        return True, f"Content size OK ({size_mb:.2f} MB)"
    
    def check_memory(self) -> tuple:
        """
        Check if system memory is within limits.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        if not self.enabled:
            return True, "Memory limiting disabled"
        
        memory_percent = self._get_memory_percent()
        
        if memory_percent > self.max_memory_percent:
            return False, (
                f"System memory usage ({memory_percent:.1f}%) exceeds maximum "
                f"({self.max_memory_percent}%). Try again later."
            )
        
        return True, f"Memory OK ({memory_percent:.1f}%)"
    
    def check_concurrent(self) -> tuple:
        """
        Check if concurrent validations are within limits.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        if not self.enabled:
            return True, "Concurrent limiting disabled"
        
        with self._lock:
            if self._concurrent_count >= self.max_concurrent:
                return False, (
                    f"Maximum concurrent validations ({self.max_concurrent}) reached. "
                    f"Try again later."
                )
            
            return True, f"Concurrent OK ({self._concurrent_count}/{self.max_concurrent})"
    
    def check_validation_allowed(self, content: str) -> tuple:
        """
        Check all limits for validation.
        
        Args:
            content: Content to validate
            
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        # Check rate limit
        allowed, reason = self.check_rate_limit()
        if not allowed:
            with self._lock:
                self._rejected_rate_limit += 1
            return False, reason
        
        # Check content size
        allowed, reason = self.check_content_size(content)
        if not allowed:
            with self._lock:
                self._rejected_size += 1
            return False, reason
        
        # Check memory
        allowed, reason = self.check_memory()
        if not allowed:
            with self._lock:
                self._rejected_memory += 1
            return False, reason
        
        # Check concurrent
        allowed, reason = self.check_concurrent()
        if not allowed:
            with self._lock:
                self._rejected_concurrent += 1
            return False, reason
        
        return True, "Validation allowed"
    
    def record_validation_start(self) -> None:
        """Record the start of a validation operation."""
        with self._lock:
            self._request_times.append(time.time())
            self._concurrent_count += 1
            self._total_validations += 1
    
    def record_validation_end(self) -> None:
        """Record the end of a validation operation."""
        with self._lock:
            self._concurrent_count = max(0, self._concurrent_count - 1)
    
    def validation_context(self) -> 'ValidationContext':
        """
        Context manager for validation operations.
        
        Returns:
            ValidationContext object
        """
        return ValidationContext(self)
    
    def get_statistics(self) -> dict:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self._lock:
            self._cleanup_old_requests()
            
            return {
                'enabled': self.enabled,
                'requests_per_minute': self.requests_per_minute,
                'max_content_size_mb': self.max_content_size_mb,
                'max_concurrent': self.max_concurrent,
                'max_memory_percent': self.max_memory_percent,
                'current_requests_in_window': len(self._request_times),
                'current_concurrent': self._concurrent_count,
                'current_memory_percent': self._get_memory_percent(),
                'total_validations': self._total_validations,
                'rejected_rate_limit': self._rejected_rate_limit,
                'rejected_size': self._rejected_size,
                'rejected_memory': self._rejected_memory,
                'rejected_concurrent': self._rejected_concurrent,
            }
    
    def reset(self) -> None:
        """Reset the rate limiter state."""
        with self._lock:
            self._request_times = []
            self._concurrent_count = 0
    
    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        with self._lock:
            self._total_validations = 0
            self._rejected_rate_limit = 0
            self._rejected_size = 0
            self._rejected_memory = 0
            self._rejected_concurrent = 0


class ValidationContext:
    """
    Context manager for validation operations with rate limiting.
    
    Automatically tracks validation start/end and provides
    access to whether validation is allowed.
    
    Usage:
        limiter = ValidationRateLimiter()
        
        with limiter.validation_context() as ctx:
            if not ctx.allowed:
                print(f"Validation blocked: {ctx.reason}")
                return
            
            # Perform validation
            result = validate(content)
    """
    
    def __init__(self, limiter: ValidationRateLimiter):
        """
        Initialize context.
        
        Args:
            limiter: ValidationRateLimiter instance
        """
        self.limiter = limiter
        self.allowed = False
        self.reason = ""
        self._started = False
    
    def check(self, content: str) -> 'ValidationContext':
        """
        Check if validation is allowed for content.
        
        Args:
            content: Content to validate
            
        Returns:
            self for method chaining
        """
        self.allowed, self.reason = self.limiter.check_validation_allowed(content)
        return self
    
    def __enter__(self) -> 'ValidationContext':
        """Enter context - record start if allowed."""
        if self.allowed:
            self.limiter.record_validation_start()
            self._started = True
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context - record end."""
        if self._started:
            self.limiter.record_validation_end()
        return None
