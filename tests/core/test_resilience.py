"""
Consolidated resilience tests for rate limiting, circuit breaker, and cancellation.

This module contains all resilience-related tests:
- TokenBucketRateLimiter and NoOpRateLimiter
- CircuitBreaker state transitions and error handling
- CancellationToken and CancellationTokenSource
- Signal handling for graceful shutdown

Run specific test categories:
    pytest -m resilience                    # All resilience tests
    pytest -m "resilience and unit"         # Unit tests only
    pytest -m "resilience and integration"  # Integration tests only
"""

import pytest
import time
import threading
import signal
from unittest.mock import patch, MagicMock, Mock

import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.core import (
    TokenBucketRateLimiter,
    NoOpRateLimiter,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerMetrics,
    CircuitState,
    CircuitBreakerRegistry,
    CancellationToken,
    CancellationTokenSource,
    OperationCancelledException,
    setup_cancellation_handler,
    restore_default_handler,
    get_global_token,
)


# =============================================================================
# RATE LIMITER TESTS
# =============================================================================

@pytest.mark.resilience
@pytest.mark.unit
class TestTokenBucketRateLimiter:
    """Tests for TokenBucketRateLimiter class."""
    
    def test_init_default_values(self):
        """Test default initialization."""
        limiter = TokenBucketRateLimiter()
        assert limiter.rate == 10
        assert limiter.per == 60
        assert limiter.capacity == 10  # burst defaults to rate
        assert limiter.tokens == 10.0  # starts full
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        limiter = TokenBucketRateLimiter(rate=5, per=30, burst=10)
        assert limiter.rate == 5
        assert limiter.per == 30
        assert limiter.capacity == 10
        assert limiter.tokens == 10.0
    
    def test_init_invalid_rate(self):
        """Test initialization with invalid rate."""
        with pytest.raises(ValueError, match="rate must be positive"):
            TokenBucketRateLimiter(rate=0)
        with pytest.raises(ValueError, match="rate must be positive"):
            TokenBucketRateLimiter(rate=-1)
    
    def test_init_invalid_per(self):
        """Test initialization with invalid per."""
        with pytest.raises(ValueError, match="per must be positive"):
            TokenBucketRateLimiter(per=0)
    
    def test_init_invalid_burst(self):
        """Test initialization with invalid burst."""
        with pytest.raises(ValueError, match="burst capacity must be positive"):
            TokenBucketRateLimiter(burst=0)
    
    def test_tokens_per_second(self):
        """Test tokens per second calculation."""
        limiter = TokenBucketRateLimiter(rate=60, per=60)
        assert limiter.tokens_per_second == 1.0
        
        limiter2 = TokenBucketRateLimiter(rate=10, per=60)
        assert abs(limiter2.tokens_per_second - 0.1667) < 0.01
    
    def test_acquire_immediate(self):
        """Test immediate token acquisition."""
        limiter = TokenBucketRateLimiter(rate=10, per=60, burst=10)
        
        start = time.time()
        result = limiter.acquire()
        elapsed = time.time() - start
        
        assert result is True
        assert elapsed < 0.1
        assert limiter.tokens == 9.0
    
    def test_acquire_multiple_immediate(self):
        """Test multiple immediate acquisitions."""
        limiter = TokenBucketRateLimiter(rate=10, per=60, burst=5)
        
        for i in range(5):
            assert limiter.acquire() is True
            assert limiter.tokens <= 5 - i
            assert limiter.tokens >= 4 - i - 0.1
    
    def test_acquire_exceeds_capacity(self):
        """Test acquiring more tokens than capacity."""
        limiter = TokenBucketRateLimiter(rate=5, per=60, burst=5)
        
        with pytest.raises(ValueError, match="Cannot acquire 10 tokens"):
            limiter.acquire(tokens=10)
    
    def test_acquire_with_timeout_success(self):
        """Test acquire with timeout that succeeds."""
        limiter = TokenBucketRateLimiter(rate=10, per=60, burst=10)
        
        result = limiter.acquire(timeout=1.0)
        assert result is True
    
    def test_acquire_with_timeout_failure(self):
        """Test acquire with timeout that fails."""
        limiter = TokenBucketRateLimiter(rate=1, per=60, burst=1)
        
        limiter.acquire()
        
        start = time.time()
        result = limiter.acquire(timeout=0.1)
        elapsed = time.time() - start
        
        assert result is False
        assert elapsed >= 0.1
        assert elapsed < 0.3
    
    def test_try_acquire_success(self):
        """Test try_acquire when tokens available."""
        limiter = TokenBucketRateLimiter(rate=10, per=60, burst=10)
        
        assert limiter.try_acquire() is True
        assert limiter.tokens == 9.0
    
    def test_try_acquire_failure(self):
        """Test try_acquire when no tokens available."""
        limiter = TokenBucketRateLimiter(rate=10, per=60, burst=1)
        
        assert limiter.try_acquire() is True
        
        start = time.time()
        assert limiter.try_acquire() is False
        elapsed = time.time() - start
        
        assert elapsed < 0.01
    
    @pytest.mark.slow
    def test_token_refill(self):
        """Test token refill over time."""
        limiter = TokenBucketRateLimiter(rate=10, per=1, burst=10)
        
        for _ in range(10):
            limiter.acquire()
        
        assert limiter.tokens < 1
        
        time.sleep(0.2)
        
        available = limiter.get_available_tokens()
        assert available >= 1.5
        assert available <= 3.0
    
    def test_get_available_tokens(self):
        """Test getting available tokens."""
        limiter = TokenBucketRateLimiter(rate=10, per=60, burst=10)
        
        assert abs(limiter.get_available_tokens() - 10.0) < 0.01
        
        limiter.acquire()
        available = limiter.get_available_tokens()
        assert available >= 8.9
        assert available <= 9.1
    
    def test_get_wait_time_no_wait(self):
        """Test get_wait_time when tokens available."""
        limiter = TokenBucketRateLimiter(rate=10, per=60, burst=10)
        
        assert limiter.get_wait_time() == 0.0
    
    def test_get_wait_time_with_wait(self):
        """Test get_wait_time when waiting required."""
        limiter = TokenBucketRateLimiter(rate=10, per=60, burst=1)
        
        limiter.acquire()
        
        wait_time = limiter.get_wait_time()
        assert wait_time > 5.0
        assert wait_time < 7.0
    
    def test_reset(self):
        """Test resetting the rate limiter."""
        limiter = TokenBucketRateLimiter(rate=10, per=60, burst=10)
        
        for _ in range(10):
            limiter.acquire()
        
        assert limiter.tokens < 1
        
        limiter.reset()
        
        assert limiter.tokens == 10.0
    
    def test_get_statistics(self):
        """Test getting rate limiter statistics."""
        limiter = TokenBucketRateLimiter(rate=10, per=60, burst=15)
        
        for _ in range(5):
            limiter.acquire()
        
        stats = limiter.get_statistics()
        
        assert stats['rate'] == 10
        assert stats['per_seconds'] == 60
        assert stats['burst_capacity'] == 15
        assert stats['total_requests'] == 5
        assert 'current_tokens' in stats
        assert 'times_waited' in stats
        assert 'total_wait_time_seconds' in stats
        assert 'average_wait_time_seconds' in stats
    
    def test_repr(self):
        """Test string representation."""
        limiter = TokenBucketRateLimiter(rate=10, per=60, burst=15)
        repr_str = repr(limiter)
        
        assert 'TokenBucketRateLimiter' in repr_str
        assert 'rate=10' in repr_str
        assert 'per=60' in repr_str
        assert 'burst=15' in repr_str


@pytest.mark.resilience
@pytest.mark.unit
class TestTokenBucketRateLimiterThreadSafety:
    """Thread safety tests for TokenBucketRateLimiter."""
    
    def test_concurrent_acquire(self):
        """Test concurrent token acquisition from multiple threads."""
        limiter = TokenBucketRateLimiter(rate=100, per=1, burst=100)
        
        acquired_count = [0]
        lock = threading.Lock()
        
        def acquire_tokens():
            for _ in range(10):
                if limiter.try_acquire():
                    with lock:
                        acquired_count[0] += 1
        
        threads = [threading.Thread(target=acquire_tokens) for _ in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert acquired_count[0] == 100
    
    @pytest.mark.slow
    def test_concurrent_refill_and_acquire(self):
        """Test concurrent refill and acquire operations."""
        limiter = TokenBucketRateLimiter(rate=100, per=1, burst=10)
        
        errors = []
        
        def acquire_repeatedly():
            try:
                for _ in range(20):
                    limiter.acquire(timeout=1.0)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=acquire_repeatedly) for _ in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors occurred: {errors}"


@pytest.mark.resilience
@pytest.mark.unit
class TestNoOpRateLimiter:
    """Tests for NoOpRateLimiter class."""
    
    def test_acquire_always_succeeds(self):
        """Test that acquire always returns True."""
        limiter = NoOpRateLimiter()
        
        for _ in range(1000):
            assert limiter.acquire() is True
    
    def test_try_acquire_always_succeeds(self):
        """Test that try_acquire always returns True."""
        limiter = NoOpRateLimiter()
        
        for _ in range(1000):
            assert limiter.try_acquire() is True
    
    def test_get_available_tokens_infinite(self):
        """Test that available tokens is infinite."""
        limiter = NoOpRateLimiter()
        
        assert limiter.get_available_tokens() == float('inf')
    
    def test_get_wait_time_zero(self):
        """Test that wait time is always zero."""
        limiter = NoOpRateLimiter()
        
        assert limiter.get_wait_time() == 0.0
        assert limiter.get_wait_time(100) == 0.0
    
    def test_reset_noop(self):
        """Test that reset does nothing."""
        limiter = NoOpRateLimiter()
        limiter.reset()
    
    def test_get_statistics(self):
        """Test statistics for NoOpRateLimiter."""
        limiter = NoOpRateLimiter()
        stats = limiter.get_statistics()
        
        assert stats['rate'] == 'unlimited'
        assert stats['current_tokens'] == float('inf')
    
    def test_repr(self):
        """Test string representation."""
        limiter = NoOpRateLimiter()
        assert repr(limiter) == "NoOpRateLimiter()"


@pytest.mark.resilience
@pytest.mark.integration
class TestRateLimitConfigIntegration:
    """Integration tests for rate limiting with FabricConfig."""
    
    def test_rate_limit_config_from_dict_default(self):
        """Test RateLimitConfig default values."""
        from src.core import RateLimitConfig
        
        config = RateLimitConfig.from_dict(None)
        
        assert config.enabled is True
        assert config.requests_per_minute == 10
        assert config.burst is None
    
    def test_rate_limit_config_from_dict_custom(self):
        """Test RateLimitConfig with custom values."""
        from src.core import RateLimitConfig
        
        config = RateLimitConfig.from_dict({
            'enabled': False,
            'requests_per_minute': 20,
            'burst': 30
        })
        
        assert config.enabled is False
        assert config.requests_per_minute == 20
        assert config.burst == 30
    
    def test_fabric_config_includes_rate_limit(self):
        """Test that FabricConfig includes rate limit settings."""
        from src.core import FabricConfig
        
        config = FabricConfig.from_dict({
            'fabric': {
                'workspace_id': 'test-workspace',
                'rate_limit': {
                    'enabled': True,
                    'requests_per_minute': 15,
                    'burst': 25
                }
            }
        })
        
        assert config.rate_limit.enabled is True
        assert config.rate_limit.requests_per_minute == 15
        assert config.rate_limit.burst == 25
    
    def test_fabric_config_default_rate_limit(self):
        """Test FabricConfig with default rate limit."""
        from src.core import FabricConfig
        
        config = FabricConfig.from_dict({
            'fabric': {
                'workspace_id': 'test-workspace'
            }
        })
        
        assert config.rate_limit.enabled is True
        assert config.rate_limit.requests_per_minute == 10
    
    def test_client_creates_rate_limiter_enabled(self):
        """Test client creates rate limiter when enabled."""
        from src.core import FabricConfig, FabricOntologyClient
        
        config = FabricConfig(
            workspace_id='12345678-1234-1234-1234-123456789012'
        )
        
        with patch.object(FabricOntologyClient, '_get_credential'):
            client = FabricOntologyClient(config)
        
        assert isinstance(client.rate_limiter, TokenBucketRateLimiter)
        assert client.rate_limiter.rate == 10
        assert client.rate_limiter.capacity == 10
    
    def test_client_creates_noop_limiter_disabled(self):
        """Test client creates NoOpRateLimiter when disabled."""
        from src.core import FabricConfig, FabricOntologyClient, RateLimitConfig
        
        config = FabricConfig(
            workspace_id='12345678-1234-1234-1234-123456789012',
            rate_limit=RateLimitConfig(enabled=False)
        )
        
        with patch.object(FabricOntologyClient, '_get_credential'):
            client = FabricOntologyClient(config)
        
        assert isinstance(client.rate_limiter, NoOpRateLimiter)
    
    def test_client_get_rate_limit_statistics(self):
        """Test getting rate limit statistics from client."""
        from src.core import FabricConfig, FabricOntologyClient
        
        config = FabricConfig(
            workspace_id='12345678-1234-1234-1234-123456789012'
        )
        
        with patch.object(FabricOntologyClient, '_get_credential'):
            client = FabricOntologyClient(config)
        
        stats = client.get_rate_limit_statistics()
        
        assert 'rate' in stats
        assert 'total_requests' in stats
        assert 'times_waited' in stats


@pytest.mark.resilience
@pytest.mark.integration
class TestRateLimitRequestIntegration:
    """Integration tests for rate limiting in request handling."""
    
    def test_make_request_acquires_token(self):
        """Test that _make_request acquires rate limit token."""
        from src.core import FabricConfig, FabricOntologyClient
        
        config = FabricConfig(
            workspace_id='12345678-1234-1234-1234-123456789012'
        )
        
        with patch.object(FabricOntologyClient, '_get_credential'):
            client = FabricOntologyClient(config)
        
        with patch('core.platform.fabric_client.requests.request') as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_request.return_value = mock_response
            
            client._access_token = 'test-token'
            client._token_expires = time.time() + 3600
            
            client._make_request('GET', 'http://test.com', 'Test operation')
            
            mock_request.assert_called_once()
            
            stats = client.get_rate_limit_statistics()
            assert stats['total_requests'] >= 1


# =============================================================================
# CIRCUIT BREAKER TESTS
# =============================================================================

@pytest.mark.resilience
@pytest.mark.unit
class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig dataclass."""
    
    def test_default_values(self):
        """Test that default configuration values are set correctly."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.success_threshold == 2
        assert config.name == "default"
    
    def test_custom_values(self):
        """Test configuration with custom values."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=30.0,
            success_threshold=3,
            name="custom"
        )
        assert config.failure_threshold == 10
        assert config.recovery_timeout == 30.0
        assert config.success_threshold == 3
        assert config.name == "custom"
    
    def test_config_validation(self):
        """Test that config validates parameters."""
        with pytest.raises(ValueError):
            CircuitBreakerConfig(failure_threshold=0)
        
        with pytest.raises(ValueError):
            CircuitBreakerConfig(recovery_timeout=-1)
        
        with pytest.raises(ValueError):
            CircuitBreakerConfig(success_threshold=0)


@pytest.mark.resilience
@pytest.mark.unit
class TestCircuitBreakerMetrics:
    """Tests for CircuitBreakerMetrics dataclass."""
    
    def test_initial_metrics(self):
        """Test that initial metrics are zero."""
        metrics = CircuitBreakerMetrics()
        assert metrics.total_calls == 0
        assert metrics.failed_calls == 0
        assert metrics.successful_calls == 0
        assert len(metrics.state_changes) == 0
        assert metrics.last_failure_time is None
        assert metrics.last_success_time is None
    
    def test_metrics_to_dict(self):
        """Test metrics can be converted to dictionary."""
        metrics = CircuitBreakerMetrics()
        result = metrics.to_dict()
        assert "total_calls" in result
        assert "success_rate" in result


@pytest.mark.resilience
@pytest.mark.unit
class TestCircuitBreakerStates:
    """Tests for circuit breaker state transitions."""
    
    def test_initial_state_is_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
    
    def test_state_transitions_to_open_after_failures(self):
        """Test circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        
        def failing_func():
            raise ValueError("Test failure")
        
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
    
    def test_open_circuit_raises_immediately(self):
        """Test that OPEN circuit raises without calling function."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)
        
        call_count = 0
        def counting_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test failure")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(counting_func)
        
        assert cb.state == CircuitState.OPEN
        assert call_count == 2
        
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(counting_func)
        
        assert call_count == 2
    
    @pytest.mark.slow
    def test_circuit_transitions_to_half_open_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        def failing_func():
            raise ValueError("Test failure")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        time.sleep(0.15)
        
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
    
    @pytest.mark.slow
    def test_half_open_success_closes_circuit(self):
        """Test successful calls in HALF_OPEN state close the circuit."""
        cb = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2
        )
        
        fail = True
        def conditional_func():
            if fail:
                raise ValueError("Test failure")
            return "success"
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(conditional_func)
        
        assert cb.state == CircuitState.OPEN
        
        time.sleep(0.15)
        fail = False
        
        result = cb.call(conditional_func)
        assert result == "success"
        assert cb.state == CircuitState.HALF_OPEN
        
        result = cb.call(conditional_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
    
    @pytest.mark.slow
    def test_half_open_failure_reopens_circuit(self):
        """Test failure in HALF_OPEN state reopens the circuit."""
        cb = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2
        )
        
        def failing_func():
            raise ValueError("Test failure")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        time.sleep(0.15)
        
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN


@pytest.mark.resilience
@pytest.mark.unit
class TestCircuitBreakerExceptions:
    """Tests for exception handling in circuit breaker."""
    
    def test_monitored_exceptions_trigger_failure(self):
        """Test that monitored exceptions increment failure count."""
        cb = CircuitBreaker(
            failure_threshold=3,
            monitored_exceptions={ValueError, RuntimeError}
        )
        
        def value_error_func():
            raise ValueError("monitored")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(value_error_func)
        
        assert cb.failure_count == 2
    
    def test_unmonitored_exceptions_pass_through(self):
        """Test that unmonitored exceptions don't increment failure count."""
        cb = CircuitBreaker(
            failure_threshold=3,
            monitored_exceptions={ValueError}
        )
        
        def type_error_func():
            raise TypeError("not monitored")
        
        for _ in range(5):
            with pytest.raises(TypeError):
                cb.call(type_error_func)
        
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_default_monitors_all_exceptions(self):
        """Test that default config monitors all exceptions."""
        cb = CircuitBreaker(failure_threshold=2)
        
        for i in range(2):
            with pytest.raises(Exception):
                if i == 0:
                    cb.call(lambda: 1/0)
                else:
                    cb.call(lambda: {}['x'])
        
        assert cb.state == CircuitState.OPEN


@pytest.mark.resilience
@pytest.mark.unit
class TestCircuitBreakerMetricsTracking:
    """Tests for metrics collection."""
    
    def test_metrics_track_calls(self):
        """Test that metrics track total calls."""
        cb = CircuitBreaker(failure_threshold=10)
        
        cb.call(lambda: "success")
        cb.call(lambda: "success")
        
        assert cb.metrics.total_calls == 2
        assert cb.metrics.successful_calls == 2
        assert cb.metrics.failed_calls == 0
    
    def test_metrics_track_failures(self):
        """Test that metrics track failures."""
        cb = CircuitBreaker(failure_threshold=5)
        
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        
        assert cb.metrics.failed_calls == 3
        assert cb.metrics.last_failure_time is not None
    
    @pytest.mark.slow
    def test_metrics_track_state_changes(self):
        """Test that metrics track state changes."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        def failing():
            raise ValueError("fail")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(failing)
        
        assert len(cb.metrics.state_changes) == 1
        
        time.sleep(0.15)
        with pytest.raises(ValueError):
            cb.call(failing)
        
        assert len(cb.metrics.state_changes) == 3


@pytest.mark.resilience
@pytest.mark.unit
class TestCircuitBreakerReset:
    """Tests for circuit breaker reset functionality."""
    
    def test_reset_closes_circuit(self):
        """Test that reset() closes an open circuit."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)
        
        def failing():
            raise ValueError("fail")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(failing)
        
        assert cb.state == CircuitState.OPEN
        
        cb.reset()
        
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb._success_count == 0
    
    def test_reset_allows_immediate_calls(self):
        """Test that after reset, calls succeed immediately."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)
        
        fail = True
        def conditional():
            if fail:
                raise ValueError("fail")
            return "success"
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(conditional)
        
        assert cb.state == CircuitState.OPEN
        
        cb.reset()
        fail = False
        
        result = cb.call(conditional)
        assert result == "success"


@pytest.mark.resilience
@pytest.mark.unit
class TestCircuitBreakerTimeUntilRecovery:
    """Tests for get_remaining_timeout method."""
    
    def test_returns_zero_when_closed(self):
        """Test get_remaining_timeout returns 0 when closed."""
        cb = CircuitBreaker(failure_threshold=5)
        assert cb.get_remaining_timeout() == 0
    
    def test_returns_positive_when_open(self):
        """Test get_remaining_timeout returns positive value when open."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)
        
        def failing():
            raise ValueError("fail")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(failing)
        
        recovery_time = cb.get_remaining_timeout()
        assert 59.0 < recovery_time <= 60.0
    
    @pytest.mark.slow
    def test_decreases_over_time(self):
        """Test get_remaining_timeout decreases over time."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
        
        def failing():
            raise ValueError("fail")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(failing)
        
        time1 = cb.get_remaining_timeout()
        time.sleep(0.2)
        time2 = cb.get_remaining_timeout()
        
        assert time2 < time1


@pytest.mark.resilience
@pytest.mark.unit
class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry."""
    
    def test_get_nonexistent_returns_none(self):
        """Test getting nonexistent circuit breaker returns None."""
        registry = CircuitBreakerRegistry()
        assert registry.get("nonexistent") is None
    
    def test_get_or_create(self):
        """Test get_or_create creates if not exists."""
        registry = CircuitBreakerRegistry()
        
        cb = registry.get_or_create("auto", failure_threshold=3)
        
        assert cb is not None
        assert cb.config.name == "auto"
        assert cb.config.failure_threshold == 3
        
        cb2 = registry.get_or_create("auto", failure_threshold=10)
        assert cb2 is cb
    
    def test_reset_all(self):
        """Test resetting all circuit breakers."""
        registry = CircuitBreakerRegistry()
        
        cb1 = registry.get_or_create("one", failure_threshold=2)
        cb2 = registry.get_or_create("two", failure_threshold=2)
        
        def failing():
            raise ValueError("fail")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb1.call(failing)
            with pytest.raises(ValueError):
                cb2.call(failing)
        
        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.OPEN
        
        registry.reset_all()
        
        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED


@pytest.mark.resilience
@pytest.mark.unit
class TestCircuitBreakerThreadSafety:
    """Tests for thread safety of circuit breaker operations."""
    
    def test_concurrent_calls(self):
        """Test circuit breaker handles concurrent calls correctly."""
        cb = CircuitBreaker(failure_threshold=10)
        results = []
        errors = []
        
        def worker():
            try:
                result = cb.call(lambda: threading.current_thread().name)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(results) == 20
        assert len(errors) == 0
    
    def test_concurrent_failures(self):
        """Test circuit breaker handles concurrent failures correctly."""
        cb = CircuitBreaker(failure_threshold=50, recovery_timeout=60.0)
        
        def failing_worker():
            for _ in range(10):
                try:
                    cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
                except (ValueError, CircuitBreakerOpenError):
                    pass
        
        threads = [threading.Thread(target=failing_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert cb.metrics.failed_calls <= 50
        assert cb.state == CircuitState.OPEN


@pytest.mark.resilience
@pytest.mark.unit
class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError exception."""
    
    def test_error_contains_remaining_time(self):
        """Test error message contains remaining time information."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0, name="test_circuit")
        
        def failing():
            raise ValueError("fail")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(failing)
        
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(lambda: "should not run")
        
        error = exc_info.value
        assert error.remaining_time > 0
        assert "test_circuit" in str(error)


@pytest.mark.resilience
@pytest.mark.integration
class TestFabricClientCircuitBreakerIntegration:
    """Tests for circuit breaker integration with FabricOntologyClient."""
    
    @patch('core.platform.fabric_client.requests.request')
    def test_client_initializes_circuit_breaker(self, mock_request):
        """Test that FabricOntologyClient initializes circuit breaker from config."""
        from src.core import FabricConfig, FabricOntologyClient, CircuitBreakerSettings
        
        config = FabricConfig(
            workspace_id="12345678-1234-1234-1234-123456789012",
            circuit_breaker=CircuitBreakerSettings(
                enabled=True,
                failure_threshold=3,
                recovery_timeout=30.0,
                success_threshold=1
            )
        )
        
        client = FabricOntologyClient(config)
        
        assert client.circuit_breaker is not None
        assert client.circuit_breaker.config.failure_threshold == 3
        assert client.circuit_breaker.config.recovery_timeout == 30.0
    
    @patch('core.platform.fabric_client.requests.request')
    def test_client_without_circuit_breaker(self, mock_request):
        """Test that FabricOntologyClient works without circuit breaker."""
        from src.core import FabricConfig, FabricOntologyClient, CircuitBreakerSettings
        
        config = FabricConfig(
            workspace_id="12345678-1234-1234-1234-123456789012",
            circuit_breaker=CircuitBreakerSettings(enabled=False)
        )
        
        client = FabricOntologyClient(config)
        assert client.circuit_breaker is None
    
    def test_circuit_breaker_status_method(self):
        """Test get_circuit_breaker_status method."""
        from src.core import FabricConfig, FabricOntologyClient, CircuitBreakerSettings
        
        config = FabricConfig(
            workspace_id="12345678-1234-1234-1234-123456789012",
            circuit_breaker=CircuitBreakerSettings(enabled=True)
        )
        
        client = FabricOntologyClient(config)
        status = client.get_circuit_breaker_status()
        
        assert status['enabled'] is True
        assert status['state'] == 'CLOSED'
        assert status['failure_count'] == 0
    
    def test_circuit_breaker_disabled_status(self):
        """Test status when circuit breaker is disabled."""
        from src.core import FabricConfig, FabricOntologyClient, CircuitBreakerSettings
        
        config = FabricConfig(
            workspace_id="12345678-1234-1234-1234-123456789012",
            circuit_breaker=CircuitBreakerSettings(enabled=False)
        )
        
        client = FabricOntologyClient(config)
        status = client.get_circuit_breaker_status()
        
        assert status == {'enabled': False}
    
    def test_reset_circuit_breaker_method(self):
        """Test reset_circuit_breaker method."""
        from src.core import FabricConfig, FabricOntologyClient, CircuitBreakerSettings
        
        config = FabricConfig(
            workspace_id="12345678-1234-1234-1234-123456789012",
            circuit_breaker=CircuitBreakerSettings(
                enabled=True,
                failure_threshold=2
            )
        )
        
        client = FabricOntologyClient(config)
        
        client.circuit_breaker._failure_count = 10
        client.circuit_breaker._state = CircuitState.OPEN
        
        assert client.get_circuit_breaker_status()['state'] == 'OPEN'
        
        result = client.reset_circuit_breaker()
        
        assert result is True
        assert client.get_circuit_breaker_status()['state'] == 'CLOSED'


@pytest.mark.resilience
@pytest.mark.integration
class TestCircuitBreakerConfigFromDict:
    """Tests for CircuitBreakerSettings.from_dict method."""
    
    def test_from_dict_with_all_values(self):
        """Test creating settings from dict with all values."""
        from src.core import CircuitBreakerSettings
        
        settings = CircuitBreakerSettings.from_dict({
            'enabled': True,
            'failure_threshold': 10,
            'recovery_timeout': 120.0,
            'success_threshold': 5
        })
        
        assert settings.enabled is True
        assert settings.failure_threshold == 10
        assert settings.recovery_timeout == 120.0
        assert settings.success_threshold == 5
    
    def test_from_dict_with_defaults(self):
        """Test creating settings from empty dict uses defaults."""
        from src.core import CircuitBreakerSettings
        
        settings = CircuitBreakerSettings.from_dict({})
        
        assert settings.enabled is True
        assert settings.failure_threshold == 5
        assert settings.recovery_timeout == 60.0
        assert settings.success_threshold == 2
    
    def test_from_dict_with_none(self):
        """Test creating settings from None uses defaults."""
        from src.core import CircuitBreakerSettings
        
        settings = CircuitBreakerSettings.from_dict(None)
        
        assert settings.enabled is True
        assert settings.failure_threshold == 5


# =============================================================================
# CANCELLATION TESTS
# =============================================================================

@pytest.mark.resilience
@pytest.mark.unit
class TestOperationCancelledException:
    """Tests for OperationCancelledException."""
    
    def test_basic_exception(self):
        """Test basic exception creation."""
        exc = OperationCancelledException()
        assert str(exc) == "Operation was cancelled"
        assert exc.message == "Operation was cancelled"
        assert exc.operation is None
    
    def test_exception_with_custom_message(self):
        """Test exception with custom message."""
        exc = OperationCancelledException("Custom cancellation message")
        assert "Custom cancellation message" in str(exc)
        assert exc.message == "Custom cancellation message"
    
    def test_exception_with_operation(self):
        """Test exception with operation name."""
        exc = OperationCancelledException("Cancelled", operation="upload")
        assert "upload" in str(exc)
        assert exc.operation == "upload"
    
    def test_exception_is_raisable(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(OperationCancelledException) as exc_info:
            raise OperationCancelledException("Test cancel")
        
        assert exc_info.value.message == "Test cancel"


@pytest.mark.resilience
@pytest.mark.unit
class TestCancellationToken:
    """Tests for CancellationToken class."""
    
    def test_initial_state(self):
        """Test that token starts in non-cancelled state."""
        token = CancellationToken()
        assert token.is_cancelled() is False
        assert token.cancel_reason is None
    
    def test_cancel_changes_state(self):
        """Test that cancel() changes the state."""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled() is True
    
    def test_cancel_with_reason(self):
        """Test cancellation with reason."""
        token = CancellationToken()
        token.cancel(reason="User pressed Ctrl+C")
        assert token.is_cancelled() is True
        assert token.cancel_reason == "User pressed Ctrl+C"
    
    def test_cancel_idempotent(self):
        """Test that multiple cancel() calls are safe."""
        token = CancellationToken()
        token.cancel("First")
        token.cancel("Second")
        assert token.is_cancelled() is True
        assert token.cancel_reason == "First"
    
    def test_throw_if_cancelled_when_not_cancelled(self):
        """Test throw_if_cancelled() does nothing when not cancelled."""
        token = CancellationToken()
        token.throw_if_cancelled()
        token.throw_if_cancelled("some operation")
    
    def test_throw_if_cancelled_when_cancelled(self):
        """Test throw_if_cancelled() raises when cancelled."""
        token = CancellationToken()
        token.cancel()
        
        with pytest.raises(OperationCancelledException):
            token.throw_if_cancelled()
    
    def test_throw_if_cancelled_with_operation(self):
        """Test throw_if_cancelled() includes operation name."""
        token = CancellationToken()
        token.cancel()
        
        with pytest.raises(OperationCancelledException) as exc_info:
            token.throw_if_cancelled("upload ontology")
        
        assert exc_info.value.operation == "upload ontology"
    
    def test_callback_executed_on_cancel(self):
        """Test that registered callbacks are called on cancel."""
        token = CancellationToken()
        callback_called = [False]
        
        def on_cancel():
            callback_called[0] = True
        
        token.register_callback(on_cancel)
        token.cancel()
        
        assert callback_called[0] is True
    
    def test_multiple_callbacks_executed(self):
        """Test that all callbacks are executed in order."""
        token = CancellationToken()
        call_order = []
        
        token.register_callback(lambda: call_order.append(1))
        token.register_callback(lambda: call_order.append(2))
        token.register_callback(lambda: call_order.append(3))
        
        token.cancel()
        
        assert call_order == [1, 2, 3]
    
    def test_callback_exception_does_not_prevent_others(self):
        """Test that callback exceptions don't prevent other callbacks."""
        token = CancellationToken()
        results = []
        
        def callback_ok():
            results.append("ok")
        
        def callback_error():
            raise RuntimeError("Callback failed")
        
        token.register_callback(callback_ok)
        token.register_callback(callback_error)
        token.register_callback(callback_ok)
        
        token.cancel()
        
        assert results == ["ok", "ok"]
    
    def test_unregister_callback(self):
        """Test callback unregistration."""
        token = CancellationToken()
        callback_called = [False]
        
        def on_cancel():
            callback_called[0] = True
        
        token.register_callback(on_cancel)
        result = token.unregister_callback(on_cancel)
        
        assert result is True
        token.cancel()
        assert callback_called[0] is False
    
    def test_unregister_nonexistent_callback(self):
        """Test unregistering callback that was never registered."""
        token = CancellationToken()
        
        def some_callback():
            pass
        
        result = token.unregister_callback(some_callback)
        assert result is False
    
    @pytest.mark.slow
    def test_wait_returns_true_when_cancelled(self):
        """Test wait() returns True when cancelled."""
        token = CancellationToken()
        
        def cancel_later():
            time.sleep(0.05)
            token.cancel()
        
        thread = threading.Thread(target=cancel_later)
        thread.start()
        
        result = token.wait(timeout=1.0)
        thread.join()
        
        assert result is True
    
    @pytest.mark.slow
    def test_wait_returns_false_on_timeout(self):
        """Test wait() returns False on timeout."""
        token = CancellationToken()
        
        result = token.wait(timeout=0.05)
        
        assert result is False
        assert token.is_cancelled() is False
    
    def test_reset_clears_cancelled_state(self):
        """Test reset() clears the cancelled state."""
        token = CancellationToken()
        token.cancel("some reason")
        
        assert token.is_cancelled() is True
        assert token.cancel_reason == "some reason"
        
        token.reset()
        
        assert token.is_cancelled() is False
        assert token.cancel_reason is None
    
    @pytest.mark.slow
    def test_thread_safety(self):
        """Test thread safety of cancel and is_cancelled."""
        token = CancellationToken()
        results = []
        
        def checker():
            for _ in range(100):
                results.append(token.is_cancelled())
                time.sleep(0.001)
        
        def canceller():
            time.sleep(0.05)
            token.cancel()
        
        threads = [
            threading.Thread(target=checker),
            threading.Thread(target=checker),
            threading.Thread(target=canceller),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert False in results
        assert True in results


@pytest.mark.resilience
@pytest.mark.unit
class TestCancellationTokenSource:
    """Tests for CancellationTokenSource class."""
    
    def test_source_has_token(self):
        """Test that source provides a token."""
        source = CancellationTokenSource()
        assert source.token is not None
        assert isinstance(source.token, CancellationToken)
    
    def test_source_cancel_cancels_token(self):
        """Test that cancelling source cancels its token."""
        source = CancellationTokenSource()
        
        assert source.is_cancelled() is False
        assert source.token.is_cancelled() is False
        
        source.cancel()
        
        assert source.is_cancelled() is True
        assert source.token.is_cancelled() is True
    
    def test_linked_token_cancelled_with_parent(self):
        """Test that linked tokens are cancelled with parent."""
        source = CancellationTokenSource()
        child = source.create_linked_token()
        
        assert child.is_cancelled() is False
        
        source.cancel("parent cancelled")
        
        assert child.is_cancelled() is True
        assert child.cancel_reason == "parent cancelled"
    
    def test_multiple_linked_tokens(self):
        """Test multiple linked tokens."""
        source = CancellationTokenSource()
        children = [source.create_linked_token() for _ in range(5)]
        
        source.cancel()
        
        for child in children:
            assert child.is_cancelled() is True


@pytest.mark.resilience
@pytest.mark.unit
class TestSignalHandler:
    """Tests for signal handler setup."""
    
    def test_setup_returns_token(self):
        """Test that setup returns a cancellation token."""
        try:
            token = setup_cancellation_handler(show_message=False)
            assert isinstance(token, CancellationToken)
            assert token.is_cancelled() is False
        finally:
            restore_default_handler()
    
    def test_get_global_token(self):
        """Test get_global_token returns the setup token."""
        try:
            token = setup_cancellation_handler(show_message=False)
            global_token = get_global_token()
            assert global_token is token
        finally:
            restore_default_handler()
    
    def test_restore_handler(self):
        """Test that restore_default_handler works."""
        original_handler = signal.getsignal(signal.SIGINT)
        
        try:
            setup_cancellation_handler(show_message=False)
            assert signal.getsignal(signal.SIGINT) != original_handler
            
            restore_default_handler()
            assert signal.getsignal(signal.SIGINT) == original_handler
        finally:
            signal.signal(signal.SIGINT, original_handler)


@pytest.mark.resilience
@pytest.mark.integration
class TestFabricClientCancellation:
    """Tests for cancellation integration with FabricOntologyClient."""
    
    def test_create_ontology_checks_cancellation(self):
        """Test that create_ontology checks cancellation token."""
        from src.core import FabricConfig, FabricOntologyClient
        
        config = FabricConfig(
            workspace_id="12345678-1234-1234-1234-123456789012",
            tenant_id="test-tenant",
            use_interactive_auth=False
        )
        
        with patch('core.platform.fabric_client.DefaultAzureCredential'):
            client = FabricOntologyClient(config)
            client._access_token = "mock-token"
            client._token_expires = time.time() + 3600
        
        token = CancellationToken()
        token.cancel()
        
        with pytest.raises(OperationCancelledException):
            client.create_ontology(
                display_name="TestOntology",
                definition={"parts": []},
                cancellation_token=token
            )
    
    def test_update_ontology_definition_checks_cancellation(self):
        """Test that update_ontology_definition checks cancellation token."""
        from src.core import FabricConfig, FabricOntologyClient
        
        config = FabricConfig(
            workspace_id="12345678-1234-1234-1234-123456789012",
            tenant_id="test-tenant",
            use_interactive_auth=False
        )
        
        with patch('core.platform.fabric_client.DefaultAzureCredential'):
            client = FabricOntologyClient(config)
            client._access_token = "mock-token"
            client._token_expires = time.time() + 3600
        
        token = CancellationToken()
        token.cancel()
        
        with pytest.raises(OperationCancelledException):
            client.update_ontology_definition(
                ontology_id="test-id",
                definition={"parts": []},
                cancellation_token=token
            )
    
    def test_create_or_update_checks_cancellation(self):
        """Test that create_or_update_ontology checks cancellation token."""
        from src.core import FabricConfig, FabricOntologyClient
        
        config = FabricConfig(
            workspace_id="12345678-1234-1234-1234-123456789012",
            tenant_id="test-tenant",
            use_interactive_auth=False
        )
        
        with patch('core.platform.fabric_client.DefaultAzureCredential'):
            client = FabricOntologyClient(config)
            client._access_token = "mock-token"
            client._token_expires = time.time() + 3600
        
        token = CancellationToken()
        token.cancel()
        
        with pytest.raises(OperationCancelledException):
            client.create_or_update_ontology(
                display_name="TestOntology",
                definition={"parts": []},
                cancellation_token=token
            )
    
    def test_wait_for_operation_checks_cancellation_immediately(self):
        """Test that _wait_for_operation checks cancellation immediately."""
        from src.core import FabricConfig, FabricOntologyClient
        
        config = FabricConfig(
            workspace_id="12345678-1234-1234-1234-123456789012",
            tenant_id="test-tenant",
            use_interactive_auth=False
        )
        
        with patch('core.platform.fabric_client.DefaultAzureCredential'):
            client = FabricOntologyClient(config)
            client._access_token = "mock-token"
            client._token_expires = time.time() + 3600
        
        token = CancellationToken()
        token.cancel()
        
        with pytest.raises(OperationCancelledException):
            client._wait_for_operation(
                "https://api.fabric.microsoft.com/operations/test",
                retry_after=1,
                max_retries=10,
                cancellation_token=token
            )


@pytest.mark.resilience
@pytest.mark.integration
class TestCancellationScenarios:
    """Integration tests for common cancellation scenarios."""
    
    @pytest.mark.slow
    def test_interruptible_loop(self):
        """Test cancelling an interruptible processing loop."""
        token = CancellationToken()
        processed = []
        
        def process_items(items, token):
            for item in items:
                token.throw_if_cancelled()
                processed.append(item)
                time.sleep(0.01)
        
        items = list(range(100))
        
        def cancel_later():
            time.sleep(0.05)
            token.cancel()
        
        cancel_thread = threading.Thread(target=cancel_later)
        cancel_thread.start()
        
        with pytest.raises(OperationCancelledException):
            process_items(items, token)
        
        cancel_thread.join()
        
        assert len(processed) > 0
        assert len(processed) < len(items)
    
    def test_cleanup_callback_executed(self):
        """Test that cleanup callbacks are executed on cancellation."""
        token = CancellationToken()
        cleanup_performed = [False]
        resource_id = ["resource-123"]
        
        def cleanup():
            cleanup_performed[0] = True
            resource_id[0] = None
        
        token.register_callback(cleanup)
        
        token.cancel()
        
        assert cleanup_performed[0] is True
        assert resource_id[0] is None
    
    def test_nested_operations_with_linked_tokens(self):
        """Test nested operations using linked tokens."""
        source = CancellationTokenSource()
        
        outer_cancelled = [False]
        inner_cancelled = [False]
        
        def outer_operation(token):
            token.register_callback(lambda: outer_cancelled.__setitem__(0, True))
            
            child = CancellationTokenSource()
            child.token.register_callback(lambda: inner_cancelled.__setitem__(0, True))
            
            token.register_callback(lambda: child.cancel())
            
            return child.token
        
        inner_token = outer_operation(source.token)
        
        source.cancel()
        
        assert outer_cancelled[0] is True
        assert inner_cancelled[0] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
