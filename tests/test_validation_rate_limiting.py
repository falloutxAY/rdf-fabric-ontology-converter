"""
Tests for Validation Rate Limiting.

Tests cover:
- Request rate limiting
- Content size limits
- Memory usage limits
- Concurrent validation limits
- Rate limiter statistics
- Context manager usage

Source: Task 12 from review/07_PLAN_UPDATES.md
"""

import pytest
import time
import sys
import threading
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.validators import ValidationRateLimiter, ValidationContext


# =============================================================================
# BASIC RATE LIMITER TESTS
# =============================================================================

class TestValidationRateLimiterBasic:
    """Basic rate limiter functionality tests."""
    
    def test_create_default_limiter(self):
        """Test creating a rate limiter with default settings."""
        limiter = ValidationRateLimiter()
        
        assert limiter.enabled is True
        assert limiter.requests_per_minute == 30
        assert limiter.max_content_size_mb == 50
        assert limiter.max_concurrent == 5
        assert limiter.max_memory_percent == 80
    
    def test_create_custom_limiter(self):
        """Test creating a rate limiter with custom settings."""
        limiter = ValidationRateLimiter(
            requests_per_minute=10,
            max_content_size_mb=25,
            max_concurrent=2,
            max_memory_percent=90,
        )
        
        assert limiter.requests_per_minute == 10
        assert limiter.max_content_size_mb == 25
        assert limiter.max_concurrent == 2
        assert limiter.max_memory_percent == 90
    
    def test_disabled_limiter_allows_all(self):
        """Test that disabled limiter allows all operations."""
        limiter = ValidationRateLimiter(enabled=False)
        
        # Even with large content, should be allowed
        large_content = "x" * (100 * 1024 * 1024)  # 100MB string
        
        allowed, reason = limiter.check_validation_allowed(large_content)
        
        assert allowed is True
    
    def test_statistics_tracking(self):
        """Test that statistics are properly tracked."""
        limiter = ValidationRateLimiter()
        
        # Perform some validations
        content = "test content"
        for _ in range(5):
            allowed, _ = limiter.check_validation_allowed(content)
            if allowed:
                limiter.record_validation_start()
                limiter.record_validation_end()
        
        stats = limiter.get_statistics()
        
        assert stats['total_validations'] == 5
        assert stats['enabled'] is True
    
    def test_reset_clears_state(self):
        """Test that reset clears the limiter state."""
        limiter = ValidationRateLimiter()
        
        # Record some requests
        for _ in range(5):
            limiter.record_validation_start()
        
        stats_before = limiter.get_statistics()
        assert stats_before['current_concurrent'] == 5
        
        limiter.reset()
        
        stats_after = limiter.get_statistics()
        assert stats_after['current_concurrent'] == 0
        assert stats_after['current_requests_in_window'] == 0


# =============================================================================
# RATE LIMIT TESTS
# =============================================================================

class TestRateLimiting:
    """Tests for request rate limiting."""
    
    def test_allows_requests_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = ValidationRateLimiter(requests_per_minute=10)
        content = "test content"
        
        # Should allow first 10 requests
        for i in range(10):
            allowed, reason = limiter.check_rate_limit()
            assert allowed is True, f"Request {i+1} should be allowed"
            limiter.record_validation_start()
    
    def test_blocks_requests_over_limit(self):
        """Test that requests over limit are blocked."""
        limiter = ValidationRateLimiter(requests_per_minute=5)
        content = "test content"
        
        # Use up the limit
        for _ in range(5):
            limiter.record_validation_start()
        
        # Next request should be blocked
        allowed, reason = limiter.check_rate_limit()
        
        assert allowed is False
        assert "rate limit" in reason.lower()
    
    def test_rate_limit_resets_after_time(self):
        """Test that rate limit resets after time window passes."""
        limiter = ValidationRateLimiter(requests_per_minute=2)
        
        # Use up the limit
        limiter.record_validation_start()
        limiter.record_validation_start()
        
        # Should be blocked
        allowed, _ = limiter.check_rate_limit()
        assert allowed is False
        
        # Manually clear old requests (simulating time passage)
        limiter._request_times = []
        
        # Should be allowed again
        allowed, _ = limiter.check_rate_limit()
        assert allowed is True


# =============================================================================
# CONTENT SIZE LIMIT TESTS
# =============================================================================

class TestContentSizeLimiting:
    """Tests for content size limiting."""
    
    def test_allows_small_content(self):
        """Test that small content is allowed."""
        limiter = ValidationRateLimiter(max_content_size_mb=10)
        
        # Small content (< 1KB)
        small_content = "x" * 1000
        
        allowed, reason = limiter.check_content_size(small_content)
        
        assert allowed is True
        assert "ok" in reason.lower()
    
    def test_blocks_large_content(self):
        """Test that content exceeding size limit is blocked."""
        limiter = ValidationRateLimiter(max_content_size_mb=1)
        
        # Large content (> 1MB)
        large_content = "x" * (2 * 1024 * 1024)  # 2MB
        
        allowed, reason = limiter.check_content_size(large_content)
        
        assert allowed is False
        assert "exceeds" in reason.lower()
        assert "size" in reason.lower()
    
    def test_size_calculation_accuracy(self):
        """Test that content size is calculated correctly."""
        limiter = ValidationRateLimiter()
        
        # Create exactly 1MB of content
        one_mb = "x" * (1024 * 1024)
        size = limiter._get_content_size_mb(one_mb)
        
        assert 0.99 <= size <= 1.01  # Allow small variance for encoding
    
    def test_tracks_rejected_size(self):
        """Test that rejected size requests are tracked."""
        limiter = ValidationRateLimiter(max_content_size_mb=1)
        
        large_content = "x" * (2 * 1024 * 1024)
        
        # Try to validate oversized content
        allowed, _ = limiter.check_validation_allowed(large_content)
        
        stats = limiter.get_statistics()
        assert stats['rejected_size'] == 1


# =============================================================================
# MEMORY LIMIT TESTS
# =============================================================================

class TestMemoryLimiting:
    """Tests for memory usage limiting."""
    
    def test_memory_check_returns_tuple(self):
        """Test that memory check returns proper tuple."""
        limiter = ValidationRateLimiter()
        
        allowed, reason = limiter.check_memory()
        
        assert isinstance(allowed, bool)
        assert isinstance(reason, str)
    
    def test_memory_check_with_high_threshold(self):
        """Test memory check with high threshold (should pass)."""
        limiter = ValidationRateLimiter(max_memory_percent=100)
        
        allowed, reason = limiter.check_memory()
        
        assert allowed is True
    
    def test_memory_percent_calculation(self):
        """Test that memory percentage is calculated."""
        limiter = ValidationRateLimiter()
        
        memory_percent = limiter._get_memory_percent()
        
        # Should be between 0 and 100
        assert 0 <= memory_percent <= 100


# =============================================================================
# CONCURRENT LIMIT TESTS
# =============================================================================

class TestConcurrentLimiting:
    """Tests for concurrent validation limiting."""
    
    def test_allows_within_concurrent_limit(self):
        """Test that concurrent validations within limit are allowed."""
        limiter = ValidationRateLimiter(max_concurrent=3)
        
        # Start 3 validations
        for _ in range(3):
            allowed, _ = limiter.check_concurrent()
            assert allowed is True
            limiter.record_validation_start()
    
    def test_blocks_over_concurrent_limit(self):
        """Test that concurrent validations over limit are blocked."""
        limiter = ValidationRateLimiter(max_concurrent=2)
        
        # Start 2 validations
        limiter.record_validation_start()
        limiter.record_validation_start()
        
        # Third should be blocked
        allowed, reason = limiter.check_concurrent()
        
        assert allowed is False
        assert "concurrent" in reason.lower()
    
    def test_allows_after_validation_ends(self):
        """Test that new validations are allowed after previous ones end."""
        limiter = ValidationRateLimiter(max_concurrent=1)
        
        # Start and end a validation
        limiter.record_validation_start()
        limiter.record_validation_end()
        
        # Should be allowed again
        allowed, _ = limiter.check_concurrent()
        assert allowed is True
    
    def test_concurrent_count_never_negative(self):
        """Test that concurrent count doesn't go negative."""
        limiter = ValidationRateLimiter()
        
        # Call end without start
        limiter.record_validation_end()
        limiter.record_validation_end()
        
        stats = limiter.get_statistics()
        assert stats['current_concurrent'] >= 0


# =============================================================================
# COMBINED CHECK TESTS
# =============================================================================

class TestCombinedChecks:
    """Tests for combined validation checks."""
    
    def test_check_all_limits_passes(self):
        """Test that check_validation_allowed passes when all limits OK."""
        limiter = ValidationRateLimiter()
        content = "small test content"
        
        allowed, reason = limiter.check_validation_allowed(content)
        
        assert allowed is True
    
    def test_check_all_limits_fails_on_size(self):
        """Test that check fails on size limit."""
        limiter = ValidationRateLimiter(max_content_size_mb=0.001)
        content = "x" * 10000  # ~10KB
        
        allowed, reason = limiter.check_validation_allowed(content)
        
        assert allowed is False
        assert "size" in reason.lower()
    
    def test_check_all_limits_fails_on_rate(self):
        """Test that check fails on rate limit."""
        limiter = ValidationRateLimiter(requests_per_minute=1)
        content = "test"
        
        # Use up rate limit
        limiter.record_validation_start()
        
        allowed, reason = limiter.check_validation_allowed(content)
        
        assert allowed is False
        assert "rate" in reason.lower()


# =============================================================================
# CONTEXT MANAGER TESTS
# =============================================================================

class TestValidationContext:
    """Tests for validation context manager."""
    
    def test_context_manager_basic_usage(self):
        """Test basic context manager usage."""
        limiter = ValidationRateLimiter()
        content = "test content"
        
        with limiter.validation_context() as ctx:
            ctx.check(content)
            assert ctx.allowed is True
    
    def test_context_tracks_start_end(self):
        """Test that context tracks validation start/end."""
        limiter = ValidationRateLimiter()
        content = "test content"
        
        stats_before = limiter.get_statistics()
        initial_count = stats_before['total_validations']
        
        ctx = limiter.validation_context()
        ctx.check(content)
        assert ctx.allowed is True
        
        with ctx:
            # Inside context after entering, should have one concurrent
            stats_during = limiter.get_statistics()
            assert stats_during['current_concurrent'] >= 1
        
        # After context, should be back to zero concurrent
        stats_after = limiter.get_statistics()
        assert stats_after['current_concurrent'] == 0
        assert stats_after['total_validations'] == initial_count + 1
    
    def test_context_does_not_track_if_not_allowed(self):
        """Test that context doesn't track if validation not allowed."""
        limiter = ValidationRateLimiter(max_content_size_mb=0.001)
        large_content = "x" * 10000
        
        initial_stats = limiter.get_statistics()
        
        with limiter.validation_context() as ctx:
            ctx.check(large_content)
            assert ctx.allowed is False
        
        final_stats = limiter.get_statistics()
        # Total validations should not increase (validation was rejected)
        assert final_stats['total_validations'] == initial_stats['total_validations']
    
    def test_context_handles_exceptions(self):
        """Test that context properly cleans up on exception."""
        limiter = ValidationRateLimiter()
        content = "test content"
        
        try:
            with limiter.validation_context() as ctx:
                ctx.check(content)
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Should still have cleaned up concurrent count
        stats = limiter.get_statistics()
        assert stats['current_concurrent'] == 0


# =============================================================================
# THREAD SAFETY TESTS
# =============================================================================

class TestThreadSafety:
    """Tests for thread safety."""
    
    def test_concurrent_access_safe(self):
        """Test that concurrent access is thread-safe."""
        limiter = ValidationRateLimiter(max_concurrent=100, requests_per_minute=1000)
        content = "test content"
        errors = []
        
        def worker():
            try:
                for _ in range(10):
                    allowed, _ = limiter.check_validation_allowed(content)
                    if allowed:
                        limiter.record_validation_start()
                        time.sleep(0.001)
                        limiter.record_validation_end()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=worker) for _ in range(10)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Thread errors: {errors}"
        
        # Should have proper cleanup
        stats = limiter.get_statistics()
        assert stats['current_concurrent'] == 0


# =============================================================================
# STATISTICS TESTS
# =============================================================================

class TestStatistics:
    """Tests for statistics reporting."""
    
    def test_statistics_complete(self):
        """Test that statistics include all expected fields."""
        limiter = ValidationRateLimiter()
        stats = limiter.get_statistics()
        
        expected_fields = [
            'enabled',
            'requests_per_minute',
            'max_content_size_mb',
            'max_concurrent',
            'max_memory_percent',
            'current_requests_in_window',
            'current_concurrent',
            'current_memory_percent',
            'total_validations',
            'rejected_rate_limit',
            'rejected_size',
            'rejected_memory',
            'rejected_concurrent',
        ]
        
        for field in expected_fields:
            assert field in stats, f"Missing field: {field}"
    
    def test_statistics_reset(self):
        """Test that statistics can be reset."""
        limiter = ValidationRateLimiter()
        
        # Generate some statistics
        limiter.record_validation_start()
        limiter.record_validation_end()
        
        stats_before = limiter.get_statistics()
        assert stats_before['total_validations'] > 0
        
        limiter.reset_statistics()
        
        stats_after = limiter.get_statistics()
        assert stats_after['total_validations'] == 0
        assert stats_after['rejected_rate_limit'] == 0


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
