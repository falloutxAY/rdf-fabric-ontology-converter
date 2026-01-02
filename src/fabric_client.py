"""
Fabric Ontology API Client

This module provides functionality to interact with the Microsoft Fabric
Ontology API for creating, updating, and managing ontologies.
"""

import json
import time
import logging
import threading
from typing import Dict, Any, Optional, List, Union, Literal, cast
from dataclasses import dataclass, field

import requests
from azure.identity import (
    InteractiveBrowserCredential,
    ClientSecretCredential,
    DefaultAzureCredential,
    ChainedTokenCredential,
)
from azure.core.credentials import TokenCredential
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
    before_sleep_log,
)
from tqdm import tqdm

# Try relative imports first, then absolute for direct execution
try:
    from .rate_limiter import TokenBucketRateLimiter, NoOpRateLimiter
    from .cancellation import CancellationToken, OperationCancelledException
    from .circuit_breaker import (
        CircuitBreaker,
        CircuitBreakerConfig,
        CircuitBreakerOpenError,
        CircuitState,
    )
except ImportError:
    from rate_limiter import TokenBucketRateLimiter, NoOpRateLimiter
    from cancellation import CancellationToken, OperationCancelledException
    from circuit_breaker import (
        CircuitBreaker,
        CircuitBreakerConfig,
        CircuitBreakerOpenError,
        CircuitState,
    )

logger = logging.getLogger(__name__)

# Type aliases
HttpMethod = Literal["GET", "POST", "PATCH", "DELETE", "PUT"]
OntologyDefinition = Dict[str, Any]
OntologyInfo = Dict[str, Any]


class TransientAPIError(Exception):
    """Exception for transient API errors (429, 503) that should be retried.
    
    Microsoft Fabric uses HTTP 429 with a Retry-After header to indicate
    when the client should retry. This exception captures that information
    for use by retry logic.
    
    See: https://learn.microsoft.com/en-us/rest/api/fabric/articles/throttling
    """
    def __init__(self, status_code: int, retry_after: int = 5, message: str = ""):
        self.status_code = status_code
        self.retry_after = retry_after
        self.message = message
        super().__init__(f"Transient error (HTTP {status_code}): {message}")


def _is_transient_error(exception: BaseException) -> bool:
    """Check if exception is a transient error that should be retried."""
    if isinstance(exception, TransientAPIError):
        return True
    if isinstance(exception, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    return False


def _wait_for_retry_after(retry_state: Any) -> float:
    """
    Custom wait function that respects the Retry-After header from Fabric API.
    
    Microsoft Fabric returns a Retry-After header in 429 responses indicating
    how many seconds to wait before retrying. This function extracts that value
    and uses it, falling back to exponential backoff for other errors.
    
    Args:
        retry_state: The tenacity retry state object
        
    Returns:
        Number of seconds to wait before retrying
    """
    exception = retry_state.outcome.exception()
    
    # Honor Retry-After from TransientAPIError (429/503 responses)
    if isinstance(exception, TransientAPIError) and exception.retry_after:
        wait_time = float(exception.retry_after)
        logger.debug(f"Using Retry-After header value: {wait_time}s")
        return wait_time
    
    # Fall back to exponential backoff for other transient errors
    # Base: 2s, multiplier: 2x, max: 60s
    attempt = retry_state.attempt_number
    wait_time = min(2 * (2 ** (attempt - 1)), 60)
    logger.debug(f"Using exponential backoff: {wait_time}s (attempt {attempt})")
    return wait_time


@dataclass
class RateLimitConfig:
    """Configuration for API rate limiting.
    
    Microsoft Fabric throttles API requests on a per-user, per-API basis.
    While exact limits are not published, this configuration allows
    proactive rate limiting to minimize 429 responses.
    
    See: https://learn.microsoft.com/en-us/rest/api/fabric/articles/throttling
    """
    enabled: bool = True
    requests_per_minute: int = 10
    burst: Optional[int] = None  # Defaults to requests_per_minute if None
    
    @classmethod
    def from_dict(cls, config_dict: Optional[Dict[str, Any]]) -> 'RateLimitConfig':
        """Create RateLimitConfig from a dictionary."""
        if config_dict is None:
            return cls()
        return cls(
            enabled=config_dict.get('enabled', True),
            requests_per_minute=config_dict.get('requests_per_minute', 10),
            burst=config_dict.get('burst'),
        )


@dataclass
class CircuitBreakerSettings:
    """Configuration for circuit breaker pattern.
    
    The circuit breaker prevents cascading failures by failing fast when
    the Fabric API is experiencing issues. After a series of failures,
    the circuit opens and requests are rejected immediately until the
    API has time to recover.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests fail immediately
    - HALF_OPEN: Testing if API has recovered
    
    See: https://martinfowler.com/bliki/CircuitBreaker.html
    """
    enabled: bool = True
    failure_threshold: int = 5  # Number of failures before opening circuit
    recovery_timeout: float = 60.0  # Seconds before attempting recovery
    success_threshold: int = 2  # Successful calls needed to close circuit
    
    @classmethod
    def from_dict(cls, config_dict: Optional[Dict[str, Any]]) -> 'CircuitBreakerSettings':
        """Create CircuitBreakerSettings from a dictionary."""
        if config_dict is None:
            return cls()
        return cls(
            enabled=config_dict.get('enabled', True),
            failure_threshold=config_dict.get('failure_threshold', 5),
            recovery_timeout=config_dict.get('recovery_timeout', 60.0),
            success_threshold=config_dict.get('success_threshold', 2),
        )


@dataclass
class FabricConfig:
    """Configuration for Fabric API access."""
    workspace_id: str
    api_base_url: str = "https://api.fabric.microsoft.com/v1"
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    use_interactive_auth: bool = True
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    circuit_breaker: CircuitBreakerSettings = field(default_factory=CircuitBreakerSettings)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'FabricConfig':
        """Create FabricConfig from a dictionary."""
        fabric_config = config_dict.get('fabric', config_dict)
        rate_limit_config = RateLimitConfig.from_dict(
            fabric_config.get('rate_limit')
        )
        circuit_breaker_config = CircuitBreakerSettings.from_dict(
            fabric_config.get('circuit_breaker')
        )
        return cls(
            workspace_id=fabric_config.get('workspace_id', ''),
            api_base_url=fabric_config.get('api_base_url', 'https://api.fabric.microsoft.com/v1'),
            tenant_id=fabric_config.get('tenant_id'),
            client_id=fabric_config.get('client_id'),
            client_secret=fabric_config.get('client_secret'),
            use_interactive_auth=fabric_config.get('use_interactive_auth', True),
            rate_limit=rate_limit_config,
            circuit_breaker=circuit_breaker_config,
        )
    
    @classmethod
    def from_file(cls, config_path: str) -> 'FabricConfig':
        """Load configuration from a JSON file with path validation."""
        if not config_path:
            raise ValueError("config_path cannot be empty")
        
        if not isinstance(config_path, str):
            raise TypeError(f"config_path must be string, got {type(config_path)}")
        
        # Import InputValidator for path security checks
        from core.validators import InputValidator
        
        # Validate config path with security checks
        try:
            validated_path = InputValidator.validate_file_path(
                config_path,
                allowed_extensions=['.json'],
                check_exists=True,
                check_readable=True
            )
        except ValueError as e:
            # Re-raise with context about it being a config file
            raise ValueError(f"Invalid configuration file path: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}. "
                f"Please create a config.json file with your Fabric workspace settings."
            )
        
        try:
            with open(validated_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file {validated_path}: {e}")
        except UnicodeDecodeError as e:
            raise ValueError(f"Encoding error reading {validated_path}: {e}")
        except PermissionError:
            raise PermissionError(f"Permission denied reading {validated_path}")
        except Exception as e:
            raise IOError(f"Error reading configuration file {validated_path}: {e}")
        
        if not isinstance(config_dict, dict):
            raise ValueError(f"Configuration file must contain a JSON object, got {type(config_dict)}")
        
        return cls.from_dict(config_dict)


class FabricOntologyClient:
    """
    Client for interacting with Microsoft Fabric Ontology API.
    
    This client handles authentication and provides methods for:
    - Creating ontologies
    - Updating ontology definitions
    - Listing ontologies
    - Getting ontology details
    - Deleting ontologies
    """
    
    FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
    
    def __init__(self, config: FabricConfig):
        """
        Initialize the Fabric Ontology client.
        
        Args:
            config: FabricConfig instance with connection details
        """
        if not config:
            raise ValueError("config cannot be None")
        
        if not isinstance(config, FabricConfig):
            raise TypeError(f"config must be FabricConfig instance, got {type(config)}")
        
        if not config.workspace_id:
            raise ValueError("workspace_id is required in configuration")
        
        if config.workspace_id in ("YOUR_WORKSPACE_ID", ""):
            raise ValueError(
                "Invalid workspace_id. Please set your actual Fabric workspace ID in config.json"
            )
        
        # Validate workspace_id format (should be a GUID)
        import re
        guid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        if not re.match(guid_pattern, config.workspace_id):
            logger.warning(
                f"workspace_id '{config.workspace_id}' does not match expected GUID format. "
                "API calls may fail."
            )
        
        self.config = config
        self._credential: Optional[TokenCredential] = None
        self._access_token: Optional[str] = None
        self._token_expires: float = 0
        self._token_lock = threading.RLock()  # Thread-safe token caching
        
        # Initialize rate limiter
        if config.rate_limit.enabled:
            burst = config.rate_limit.burst or config.rate_limit.requests_per_minute
            self.rate_limiter: Union[TokenBucketRateLimiter, NoOpRateLimiter] = TokenBucketRateLimiter(
                rate=config.rate_limit.requests_per_minute,
                per=60,  # per minute
                burst=burst
            )
            logger.info(
                f"Rate limiting enabled: {config.rate_limit.requests_per_minute} requests/minute "
                f"(burst: {burst})"
            )
        else:
            self.rate_limiter = NoOpRateLimiter()
            logger.info("Rate limiting disabled")
        
        # Initialize circuit breaker
        if config.circuit_breaker.enabled:
            self.circuit_breaker: Optional[CircuitBreaker] = CircuitBreaker(
                failure_threshold=config.circuit_breaker.failure_threshold,
                recovery_timeout=config.circuit_breaker.recovery_timeout,
                success_threshold=config.circuit_breaker.success_threshold,
                monitored_exceptions={FabricAPIError, TransientAPIError, requests.exceptions.RequestException},
                name="fabric_api"
            )
            logger.info(
                f"Circuit breaker enabled: failure_threshold={config.circuit_breaker.failure_threshold}, "
                f"recovery_timeout={config.circuit_breaker.recovery_timeout}s"
            )
        else:
            self.circuit_breaker = None
            logger.info("Circuit breaker disabled")
    
    def _get_credential(self) -> TokenCredential:
        """Get the appropriate credential based on configuration.
        
        Returns:
            Azure TokenCredential instance for authentication
        """
        if self._credential is not None:
            return self._credential
        
        credentials: List[TokenCredential] = []
        
        # Service principal authentication
        if self.config.client_id and self.config.client_secret and self.config.tenant_id:
            logger.info("Using client secret credential for authentication")
            credentials.append(
                ClientSecretCredential(
                    tenant_id=self.config.tenant_id,
                    client_id=self.config.client_id,
                    client_secret=self.config.client_secret,
                )
            )
        
        # Interactive browser authentication
        if self.config.use_interactive_auth:
            logger.info("Interactive browser authentication enabled")
            credentials.append(
                InteractiveBrowserCredential(
                    tenant_id=self.config.tenant_id,
                    client_id=self.config.client_id,
                )
            )
        
        # Default Azure credential (for managed identities, etc.)
        credentials.append(DefaultAzureCredential())
        
        self._credential = ChainedTokenCredential(*credentials)
        return self._credential
    
    def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary (thread-safe).
        
        Uses a reentrant lock to ensure thread-safe token acquisition.
        Multiple threads requesting tokens concurrently will:
        1. All wait for the lock if token needs refresh
        2. Only one thread acquires the new token
        3. Subsequent threads use the cached token
        
        Returns:
            str: Valid access token
            
        Raises:
            FabricAPIError: If authentication fails
        """
        with self._token_lock:
            current_time = time.time()
            
            # Check if cached token is still valid (with 5-minute buffer)
            if self._access_token and current_time < self._token_expires - 300:
                logger.debug("Using cached access token")
                return self._access_token
            
            logger.info("Acquiring access token...")
            
            try:
                credential = self._get_credential()
                token = credential.get_token(self.FABRIC_SCOPE)
            except Exception as e:
                logger.error(f"Authentication failed: {e}")
                raise FabricAPIError(
                    status_code=401,
                    error_code='AuthenticationFailed',
                    message=f"Failed to acquire access token: {str(e)}. "
                           f"Please check your credentials and authentication settings."
                )
            
            if not token or not token.token:
                raise FabricAPIError(
                    status_code=401,
                    error_code='AuthenticationFailed',
                    message="Received empty token from credential provider"
                )
            
            # Atomic state update (within lock)
            self._access_token = token.token
            self._token_expires = token.expires_on
            
            logger.info("Access token acquired successfully")
            return self._access_token
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with authorization."""
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    def _make_request(
        self,
        method: HttpMethod,
        url: str,
        operation_name: str,
        timeout: int = 30,
        **kwargs: Any
    ) -> requests.Response:
        """
        Make HTTP request with consistent error handling, rate limiting, and circuit breaker.
        
        Centralizes request logic to ensure all API calls have uniform:
        - Circuit breaker (fail fast on repeated failures)
        - Rate limiting (token bucket algorithm)
        - Timeout handling
        - Connection error handling
        - Logging format
        - Error message structure
        
        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            url: URL to request
            operation_name: Description of operation (for logging)
            timeout: Request timeout in seconds (default: 30)
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            Response object
            
        Raises:
            FabricAPIError: On any request failure with consistent error codes
            CircuitBreakerOpenError: If circuit breaker is open (fail fast)
        """
        # Check circuit breaker first - fail fast if circuit is open
        if self.circuit_breaker:
            try:
                return self.circuit_breaker.call(
                    self._execute_request,
                    method, url, operation_name, timeout, **kwargs
                )
            except CircuitBreakerOpenError:
                remaining = self.circuit_breaker.get_remaining_timeout()
                logger.warning(
                    f"{operation_name}: Circuit breaker is OPEN. "
                    f"Failing fast to prevent cascading failures. "
                    f"Circuit will attempt recovery in {remaining:.1f}s"
                )
                raise FabricAPIError(
                    status_code=503,
                    error_code='CircuitBreakerOpen',
                    message=(
                        f'{operation_name} rejected: Circuit breaker is open due to repeated failures. '
                        f'The Fabric API appears to be experiencing issues. '
                        f'Automatic recovery will be attempted in {remaining:.1f} seconds.'
                    )
                )
        else:
            return self._execute_request(method, url, operation_name, timeout, **kwargs)
    
    def _execute_request(
        self,
        method: HttpMethod,
        url: str,
        operation_name: str,
        timeout: int,
        **kwargs: Any
    ) -> requests.Response:
        """
        Execute the actual HTTP request with rate limiting.
        
        This method is wrapped by the circuit breaker in _make_request.
        
        Args:
            method: HTTP method
            url: URL to request
            operation_name: Description of operation
            timeout: Request timeout in seconds
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
        """
        # Acquire rate limit token before making request
        wait_time = self.rate_limiter.get_wait_time()
        if wait_time > 0:
            logger.debug(f"Rate limit: waiting {wait_time:.2f}s before {operation_name}")
        self.rate_limiter.acquire()
        
        try:
            logger.debug(f"{operation_name}: {method} {url}")
            response = requests.request(method, url, timeout=timeout, **kwargs)
            return response
        
        except requests.exceptions.Timeout:
            logger.error(f"{operation_name}: Request timeout after {timeout}s")
            raise FabricAPIError(
                status_code=408,
                error_code='RequestTimeout',
                message=f'{operation_name} timed out after {timeout} seconds'
            )
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"{operation_name}: Connection error: {e}")
            raise FabricAPIError(
                status_code=503,
                error_code='ConnectionError',
                message=f'{operation_name} failed to connect to Fabric API: {e}'
            )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"{operation_name}: Request error: {e}")
            raise FabricAPIError(
                status_code=500,
                error_code='RequestError',
                message=f'{operation_name} request failed: {e}'
            )

    @staticmethod
    def _sanitize_display_name(name: str) -> str:
        """Sanitize names to meet Fabric item constraints (letters, numbers, underscores; starts with letter)."""
        if not name:
            return "Ontology"
        cleaned = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
        if not cleaned[0].isalpha():
            cleaned = 'O_' + cleaned
        # Fabric error message mentions < 90 chars
        return cleaned[:90]
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get the current circuit breaker status and metrics.
        
        Returns:
            Dictionary with circuit breaker state and metrics, or empty dict if disabled.
            
        Example return value:
            {
                'enabled': True,
                'state': 'CLOSED',
                'failure_count': 2,
                'success_count': 0,
                'total_calls': 150,
                'total_failures': 3,
                'time_until_recovery': None,  # Only set when OPEN
                'last_failure_time': 1699876543.21,
            }
        """
        if not self.circuit_breaker:
            return {'enabled': False}
        
        metrics = self.circuit_breaker.metrics
        time_until_recovery = self.circuit_breaker.get_remaining_timeout()
        
        return {
            'enabled': True,
            'state': self.circuit_breaker.state.name,
            'failure_count': self.circuit_breaker._failure_count,
            'success_count': self.circuit_breaker._success_count,
            'total_calls': metrics.total_calls,
            'total_failures': metrics.failed_calls,
            'total_successes': metrics.successful_calls,
            'time_until_recovery': time_until_recovery if time_until_recovery > 0 else None,
            'last_failure_time': metrics.last_failure_time,
        }
    
    def reset_circuit_breaker(self) -> bool:
        """Manually reset the circuit breaker to CLOSED state.
        
        This can be useful after fixing an issue to immediately resume operations
        instead of waiting for the recovery timeout.
        
        Returns:
            True if reset was performed, False if circuit breaker is disabled.
        """
        if not self.circuit_breaker:
            return False
        
        self.circuit_breaker.reset()
        logger.info("Circuit breaker manually reset to CLOSED state")
        return True
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate errors.
        
        Args:
            response: The HTTP response to handle
            
        Returns:
            Parsed JSON response as dictionary
            
        Raises:
            FabricAPIError: On error responses
            TransientAPIError: On retryable errors (429, 503)
        """
        if response.status_code in (200, 201):
            if response.text:
                try:
                    return response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.debug(f"Response text: {response.text[:500]}")
                    raise FabricAPIError(
                        status_code=response.status_code,
                        error_code='InvalidResponse',
                        message=f'Server returned invalid JSON: {e}'
                    )
            return {}
        
        if response.status_code == 202:
            # Long-running operation
            location = response.headers.get('Location')
            operation_id = response.headers.get('x-ms-operation-id')
            retry_after = int(response.headers.get('Retry-After', 30))
            
            return {
                '_lro': True,
                'location': location,
                'operation_id': operation_id,
                'retry_after': retry_after,
            }
        
        # Handle transient errors (429, 503) - raise special exception for retry
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 30))
            logger.warning(f"Rate limited (429). Retry after {retry_after}s")
            raise TransientAPIError(429, retry_after, "Rate limit exceeded")
        
        if response.status_code == 503:
            retry_after = int(response.headers.get('Retry-After', 10))
            logger.warning(f"Service unavailable (503). Retry after {retry_after}s")
            raise TransientAPIError(503, retry_after, "Service temporarily unavailable")
        
        # Error response
        try:
            error_data = response.json()
            error_message = error_data.get('message', response.text)
            error_code = error_data.get('errorCode', 'Unknown')
        except json.JSONDecodeError:
            error_message = response.text
            error_code = 'Unknown'
        
        raise FabricAPIError(
            status_code=response.status_code,
            error_code=error_code,
            message=error_message,
        )
    
    def _wait_for_operation(
        self, 
        operation_url: str, 
        retry_after: int = 30, 
        max_retries: int = 60,
        cancellation_token: Optional[CancellationToken] = None
    ) -> Dict[str, Any]:
        """Wait for a long-running operation to complete with progress reporting.
        
        Args:
            operation_url: URL to poll for operation status
            retry_after: Initial delay between polls in seconds
            max_retries: Maximum number of poll attempts
            cancellation_token: Optional token for cancellation support
            
        Returns:
            Operation result dictionary
            
        Raises:
            FabricAPIError: If operation fails or times out
            OperationCancelledException: If cancellation is requested
        """
        logger.info(f"Waiting for operation to complete... (polling every {retry_after}s)")
        
        # Create progress bar for LRO status
        with tqdm(total=100, desc="Operation progress", unit="%", 
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as pbar:
            last_progress = 0
            
            for attempt in range(max_retries):
                # Check for cancellation before sleeping
                if cancellation_token:
                    cancellation_token.throw_if_cancelled("waiting for operation")
                
                # Use interruptible sleep if cancellation token provided
                if cancellation_token:
                    # Sleep in smaller intervals to check for cancellation
                    for _ in range(retry_after):
                        if cancellation_token.is_cancelled():
                            cancellation_token.throw_if_cancelled("waiting for operation")
                        time.sleep(1)
                else:
                    time.sleep(retry_after)
                
                try:
                    response = requests.get(operation_url, headers=self._get_headers(), timeout=30)
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Operation polling request failed (attempt {attempt+1}/{max_retries}): {e}")
                    continue
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse operation status: {e}")
                        continue
                    
                    status = result.get('status', 'Unknown')
                    percent_complete = result.get('percentComplete', 0) or 0
                    
                    # Update progress bar
                    if percent_complete > last_progress:
                        pbar.update(percent_complete - last_progress)
                        last_progress = percent_complete
                    
                    pbar.set_postfix_str(f"Status: {status}")
                    logger.info(f"Operation status: {status} ({percent_complete}% complete)")
                    
                    if status == 'Succeeded':
                        pbar.update(100 - last_progress)  # Complete the bar
                        return result
                    elif status == 'Failed':
                        error_msg = result.get('error', {}).get('message', 'Unknown error')
                        raise FabricAPIError(
                            status_code=500,
                            error_code='OperationFailed',
                            message=f"Operation failed: {error_msg}",
                        )
                    # Still running, continue polling
                else:
                    logger.warning(f"Failed to check operation status: {response.status_code}")
        
        raise FabricAPIError(
            status_code=504,
            error_code='OperationTimeout',
            message='Operation timed out',
        )
    
    @retry(
        stop=stop_after_attempt(5),
        wait=_wait_for_retry_after,
        retry=retry_if_exception(_is_transient_error),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def list_ontologies(self) -> List[Dict[str, Any]]:
        """
        List all ontologies in the workspace.
        
        Returns:
            List of ontology objects
        """
        url = f"{self.config.api_base_url}/workspaces/{self.config.workspace_id}/ontologies"
        
        logger.info(f"Listing ontologies in workspace {self.config.workspace_id}")
        
        response = self._make_request(
            'GET', url, 'List ontologies',
            headers=self._get_headers()
        )
        
        result = self._handle_response(response)
        ontologies = result.get('value', [])
        
        logger.info(f"Found {len(ontologies)} ontologies")
        return ontologies
    
    @retry(
        stop=stop_after_attempt(5),
        wait=_wait_for_retry_after,
        retry=retry_if_exception(_is_transient_error),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def get_ontology(self, ontology_id: str) -> Dict[str, Any]:
        """
        Get details of a specific ontology.
        
        Args:
            ontology_id: The ontology ID
            
        Returns:
            Ontology object
        """
        url = f"{self.config.api_base_url}/workspaces/{self.config.workspace_id}/ontologies/{ontology_id}"
        
        logger.info(f"Getting ontology: {ontology_id}")
        
        response = self._make_request(
            'GET', url, f'Get ontology {ontology_id}',
            headers=self._get_headers()
        )
        
        return self._handle_response(response)
    
    @retry(
        stop=stop_after_attempt(15),
        wait=_wait_for_retry_after,
        retry=retry_if_exception(_is_transient_error),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def get_ontology_definition(self, ontology_id: str) -> Dict[str, Any]:
        """
        Get the definition of a specific ontology.
        
        Args:
            ontology_id: The ontology ID
            
        Returns:
            Ontology definition object with 'parts' containing entity and relationship types
        """
        url = f"{self.config.api_base_url}/workspaces/{self.config.workspace_id}/ontologies/{ontology_id}/getDefinition"
        
        logger.info(f"Getting ontology definition for {ontology_id}")
        
        response = self._make_request(
            'POST', url, f'Get ontology definition {ontology_id}',
            headers=self._get_headers()
        )
        
        # Check for 404 errors (newly created ontology may not be immediately available)
        if response.status_code == 404:
            logger.warning(f"Ontology definition not yet available (404), retrying... {ontology_id}")
            raise TransientAPIError(404, 2, "Ontology definition not yet available")
        
        result = self._handle_response(response)
        
        if result.get('_lro'):
            # For LRO, wait for completion and then fetch definition from result URL
            operation_url = result['location']
            operation_result = self._wait_for_operation_and_get_result(operation_url, result['retry_after'])
            
            # Log the operation result for debugging
            logger.debug(f"Operation result keys: {operation_result.keys() if operation_result else 'None'}")
            
            # The definition should be in the operation result
            if 'definition' in operation_result:
                return operation_result['definition']
            elif 'parts' in operation_result:
                return operation_result
            else:
                logger.warning(f"No definition found in operation result for {ontology_id}. Keys: {list(operation_result.keys()) if operation_result else 'None'}")
                return {'parts': []}
        
        return result
    
    def _wait_for_operation_and_get_result(
        self, 
        operation_url: str, 
        retry_after: int = 20, 
        max_retries: int = 60,
        cancellation_token: Optional[CancellationToken] = None
    ) -> Dict[str, Any]:
        """
        Wait for a long-running operation to complete and return the full result.
        
        After the operation succeeds, fetches the actual result from the result URL
        which is provided in the Location header of the success response.
        
        Args:
            operation_url: URL to poll for operation status
            retry_after: Initial delay between polls in seconds
            max_retries: Maximum number of poll attempts
            cancellation_token: Optional token for cancellation support
            
        Returns:
            Operation result dictionary
            
        Raises:
            FabricAPIError: If operation fails or times out
            OperationCancelledException: If cancellation is requested
        """
        logger.info(f"Waiting for operation to complete... (polling every {retry_after}s)")
        
        with tqdm(total=100, desc="Operation progress", unit="%", 
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as pbar:
            last_progress = 0
            
            for attempt in range(max_retries):
                # Check for cancellation before sleeping
                if cancellation_token:
                    cancellation_token.throw_if_cancelled("waiting for operation")
                
                # Use interruptible sleep if cancellation token provided
                if cancellation_token:
                    # Sleep in smaller intervals to check for cancellation
                    for _ in range(retry_after):
                        if cancellation_token.is_cancelled():
                            cancellation_token.throw_if_cancelled("waiting for operation")
                        time.sleep(1)
                else:
                    time.sleep(retry_after)
                
                try:
                    response = requests.get(operation_url, headers=self._get_headers(), timeout=30)
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Operation polling request failed (attempt {attempt+1}/{max_retries}): {e}")
                    continue
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse operation status: {e}")
                        continue
                    
                    status = result.get('status', 'Unknown')
                    percent_complete = result.get('percentComplete', 0) or 0
                    
                    # Update progress bar
                    if percent_complete > last_progress:
                        pbar.update(percent_complete - last_progress)
                        last_progress = percent_complete
                    
                    pbar.set_postfix_str(f"Status: {status}")
                    logger.info(f"Operation status: {status} ({percent_complete}% complete)")
                    
                    if status == 'Succeeded':
                        pbar.update(100 - last_progress)  # Complete the bar
                        
                        # Get the result URL from the Location header
                        result_url = response.headers.get('Location')
                        if result_url:
                            logger.info(f"Fetching result from: {result_url}")
                            try:
                                result_response = requests.get(result_url, headers=self._get_headers(), timeout=30)
                                if result_response.status_code == 200:
                                    return result_response.json()
                                else:
                                    logger.warning(f"Failed to fetch result from {result_url}: {result_response.status_code}")
                            except Exception as e:
                                logger.warning(f"Error fetching result: {e}")
                        
                        # Fallback: try appending /result to operation URL
                        result_url = f"{operation_url}/result"
                        logger.info(f"Trying fallback result URL: {result_url}")
                        try:
                            result_response = requests.get(result_url, headers=self._get_headers(), timeout=30)
                            if result_response.status_code == 200:
                                return result_response.json()
                        except Exception as e:
                            logger.warning(f"Error fetching fallback result: {e}")
                        
                        # Return the status response if no result URL found
                        return result
                        
                    elif status == 'Failed':
                        error_msg = result.get('error', {}).get('message', 'Unknown error')
                        raise FabricAPIError(
                            status_code=500,
                            error_code='OperationFailed',
                            message=f"Operation failed: {error_msg}",
                        )
                else:
                    logger.warning(f"Failed to check operation status: {response.status_code}")
        
        raise FabricAPIError(
            status_code=504,
            error_code='OperationTimeout',
            message='Operation timed out',
        )
    
    @retry(
        stop=stop_after_attempt(5),
        wait=_wait_for_retry_after,
        retry=retry_if_exception(_is_transient_error),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def create_ontology(
        self,
        display_name: str,
        description: str = "",
        definition: Optional[Dict[str, Any]] = None,
        wait_for_completion: bool = True,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        """
        Create a new ontology.
        
        Args:
            display_name: The ontology display name
            description: The ontology description
            definition: Optional ontology definition with parts
            wait_for_completion: Whether to wait for LRO to complete
            cancellation_token: Optional token for cancellation support
            
        Returns:
            Created ontology object
            
        Raises:
            OperationCancelledException: If cancellation is requested
        """
        # Check for cancellation before starting
        if cancellation_token:
            cancellation_token.throw_if_cancelled("create ontology")
        
        url = f"{self.config.api_base_url}/workspaces/{self.config.workspace_id}/ontologies"
        
        safe_name = self._sanitize_display_name(display_name)
        if safe_name != display_name:
            logger.info(f"Sanitized display name '{display_name}' -> '{safe_name}' to meet naming rules")

        payload: Dict[str, Any] = {
            "displayName": safe_name,
            "description": description,
        }
        
        if definition:
            payload["definition"] = definition
        
        logger.info(f"Creating ontology '{safe_name}'")
        logger.debug(f"Payload size: {len(json.dumps(payload))} bytes")
        
        response = self._make_request(
            'POST', url, f'Create ontology {safe_name}',
            timeout=60,
            headers=self._get_headers(),
            json=payload
        )
        
        result = self._handle_response(response)
        
        ontology_location = None
        if result.get('_lro'):
            ontology_location = result.get('location')
            if wait_for_completion:
                result = self._wait_for_operation(
                    result['location'], 
                    result['retry_after'],
                    cancellation_token=cancellation_token
                )
        
        # Extract ID from location header
        if ontology_location:
            # Extract ontology ID from location URL (e.g., /ontologies/{id})
            ontology_id = ontology_location.split('/')[-1]
            if ontology_id:
                logger.info(f"Ontology created: {ontology_id}")
                return {'id': ontology_id}
        
        logger.info(f"Ontology created: {result.get('id', 'Unknown ID')}")
        return result
    
    @retry(
        stop=stop_after_attempt(5),
        wait=_wait_for_retry_after,
        retry=retry_if_exception(_is_transient_error),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def update_ontology_definition(
        self,
        ontology_id: str,
        definition: Dict[str, Any],
        update_metadata: bool = True,
        wait_for_completion: bool = True,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        """
        Update the definition of an existing ontology.
        
        Args:
            ontology_id: The ontology ID
            definition: The new ontology definition
            update_metadata: Whether to update metadata from .platform file
            wait_for_completion: Whether to wait for LRO to complete
            cancellation_token: Optional token for cancellation support
            
        Returns:
            Updated ontology object
            
        Raises:
            OperationCancelledException: If cancellation is requested
        """
        # Check for cancellation before starting
        if cancellation_token:
            cancellation_token.throw_if_cancelled("update ontology definition")
        
        url = f"{self.config.api_base_url}/workspaces/{self.config.workspace_id}/ontologies/{ontology_id}/updateDefinition"
        
        if update_metadata:
            url += "?updateMetadata=True"
        
        payload = {
            "definition": definition,
        }
        
        logger.info(f"Updating ontology definition for {ontology_id}")
        logger.debug(f"Payload size: {len(json.dumps(payload))} bytes")
        
        response = self._make_request(
            'POST', url, f'Update ontology definition {ontology_id}',
            timeout=60,
            headers=self._get_headers(),
            json=payload
        )
        
        result = self._handle_response(response)
        
        if result.get('_lro') and wait_for_completion:
            result = self._wait_for_operation(
                result['location'], 
                result['retry_after'],
                cancellation_token=cancellation_token
            )
        
        logger.info(f"Ontology definition updated successfully")
        return result
    
    @retry(
        stop=stop_after_attempt(5),
        wait=_wait_for_retry_after,
        retry=retry_if_exception(_is_transient_error),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def update_ontology(
        self,
        ontology_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update ontology properties (name, description).
        
        Args:
            ontology_id: The ontology ID
            display_name: New display name (optional)
            description: New description (optional)
            
        Returns:
            Updated ontology object
        """
        url = f"{self.config.api_base_url}/workspaces/{self.config.workspace_id}/ontologies/{ontology_id}"
        
        payload = {}
        if display_name is not None:
            payload["displayName"] = display_name
        if description is not None:
            payload["description"] = description
        
        logger.info(f"Updating ontology {ontology_id}")
        
        response = self._make_request(
            'PATCH', url, f'Update ontology {ontology_id}',
            headers=self._get_headers(),
            json=payload
        )
        
        return self._handle_response(response)
    
    @retry(
        stop=stop_after_attempt(5),
        wait=_wait_for_retry_after,
        retry=retry_if_exception(_is_transient_error),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def delete_ontology(self, ontology_id: str) -> None:
        """
        Delete an ontology.
        
        Args:
            ontology_id: The ontology ID
        """
        url = f"{self.config.api_base_url}/workspaces/{self.config.workspace_id}/ontologies/{ontology_id}"
        
        logger.info(f"Deleting ontology {ontology_id}")
        
        response = self._make_request(
            'DELETE', url, f'Delete ontology {ontology_id}',
            headers=self._get_headers()
        )
        
        if response.status_code not in (200, 204):
            self._handle_response(response)
        
        logger.info(f"Ontology {ontology_id} deleted successfully")
    
    def find_ontology_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find an ontology by its display name.
        
        Args:
            name: The ontology display name
            
        Returns:
            Ontology object if found, None otherwise
        """
        ontologies = self.list_ontologies()
        
        for ontology in ontologies:
            if ontology.get('displayName') == name:
                return ontology
        
        return None
    
    def create_or_update_ontology(
        self,
        display_name: str,
        description: str = "",
        definition: Optional[Dict[str, Any]] = None,
        wait_for_completion: bool = True,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        """
        Create a new ontology or update an existing one.
        
        This method checks if an ontology with the given name exists:
        - If it exists, updates the definition
        - If it doesn't exist, creates a new one
        
        Args:
            display_name: The ontology display name
            description: The ontology description
            definition: Optional ontology definition with parts
            wait_for_completion: Whether to wait for LRO to complete
            cancellation_token: Optional token for cancellation support
            
        Returns:
            Created or updated ontology object
            
        Raises:
            OperationCancelledException: If cancellation is requested
        """
        # Check for cancellation before starting
        if cancellation_token:
            cancellation_token.throw_if_cancelled("create or update ontology")
        
        # Check if ontology exists
        safe_name = self._sanitize_display_name(display_name)
        existing = self.find_ontology_by_name(safe_name)
        
        if existing:
            logger.info(f"Ontology '{safe_name}' already exists. Updating definition...")
            ontology_id = existing['id']
            
            # Check for cancellation before updating
            if cancellation_token:
                cancellation_token.throw_if_cancelled("update ontology definition")
            
            # Update the definition if provided
            if definition:
                self.update_ontology_definition(
                    ontology_id=ontology_id,
                    definition=definition,
                    cancellation_token=cancellation_token
                )
            
            # Check for cancellation before updating properties
            if cancellation_token:
                cancellation_token.throw_if_cancelled("update ontology properties")
            
            # Update properties if changed
            if description != existing.get('description', ''):
                self.update_ontology(
                    ontology_id=ontology_id,
                    display_name=safe_name,
                    description=description
                )
            
            return self.get_ontology(ontology_id)
        else:
            logger.info(f"Ontology '{safe_name}' does not exist. Creating new...")
            return self.create_ontology(
                display_name=safe_name,
                description=description,
                definition=definition,
                wait_for_completion=wait_for_completion,
                cancellation_token=cancellation_token
            )
    
    def get_rate_limit_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about rate limiting.
        
        Returns:
            Dictionary with rate limit statistics including:
            - rate: requests allowed per time period
            - per_seconds: time period in seconds
            - burst_capacity: maximum burst size
            - current_tokens: current available tokens
            - total_requests: total requests made
            - times_waited: number of times rate limit caused waiting
            - total_wait_time_seconds: total time spent waiting
            - average_wait_time_seconds: average wait time per wait
        """
        return self.rate_limiter.get_statistics()


class FabricAPIError(Exception):
    """Exception raised for Fabric API errors."""
    
    def __init__(self, status_code: int, error_code: str, message: str):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(f"[{error_code}] {message} (HTTP {status_code})")
