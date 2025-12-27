"""
Fabric Ontology API Client

This module provides functionality to interact with the Microsoft Fabric
Ontology API for creating, updating, and managing ontologies.
"""

import json
import time
import logging
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import requests
from azure.identity import (
    InteractiveBrowserCredential,
    ClientSecretCredential,
    DefaultAzureCredential,
    ChainedTokenCredential,
)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
    before_sleep_log,
)
from tqdm import tqdm

logger = logging.getLogger(__name__)


class TransientAPIError(Exception):
    """Exception for transient API errors (429, 503) that should be retried."""
    def __init__(self, status_code: int, retry_after: int = 5, message: str = ""):
        self.status_code = status_code
        self.retry_after = retry_after
        self.message = message
        super().__init__(f"Transient error (HTTP {status_code}): {message}")


def _is_transient_error(exception: Exception) -> bool:
    """Check if exception is a transient error that should be retried."""
    if isinstance(exception, TransientAPIError):
        return True
    if isinstance(exception, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    return False


@dataclass
class FabricConfig:
    """Configuration for Fabric API access."""
    workspace_id: str
    api_base_url: str = "https://api.fabric.microsoft.com/v1"
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    use_interactive_auth: bool = True
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'FabricConfig':
        """Create FabricConfig from a dictionary."""
        fabric_config = config_dict.get('fabric', config_dict)
        return cls(
            workspace_id=fabric_config.get('workspace_id', ''),
            api_base_url=fabric_config.get('api_base_url', 'https://api.fabric.microsoft.com/v1'),
            tenant_id=fabric_config.get('tenant_id'),
            client_id=fabric_config.get('client_id'),
            client_secret=fabric_config.get('client_secret'),
            use_interactive_auth=fabric_config.get('use_interactive_auth', True),
        )
    
    @classmethod
    def from_file(cls, config_path: str) -> 'FabricConfig':
        """Load configuration from a JSON file."""
        if not config_path:
            raise ValueError("config_path cannot be empty")
        
        if not isinstance(config_path, str):
            raise TypeError(f"config_path must be string, got {type(config_path)}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}. "
                f"Please create a config.json file with your Fabric workspace settings."
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file {config_path}: {e}")
        except UnicodeDecodeError as e:
            raise ValueError(f"Encoding error reading {config_path}: {e}")
        except PermissionError:
            raise PermissionError(f"Permission denied reading {config_path}")
        except Exception as e:
            raise IOError(f"Error reading configuration file {config_path}: {e}")
        
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
        self._credential = None
        self._access_token = None
        self._token_expires = 0
        self._token_lock = threading.RLock()  # Thread-safe token caching
    
    def _get_credential(self):
        """Get the appropriate credential based on configuration."""
        if self._credential is not None:
            return self._credential
        
        credentials = []
        
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
        method: str,
        url: str,
        operation_name: str,
        timeout: int = 30,
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with consistent error handling.
        
        Centralizes request logic to ensure all API calls have uniform:
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
        """
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
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate errors."""
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
    
    def _wait_for_operation(self, operation_url: str, retry_after: int = 30, max_retries: int = 60) -> Dict[str, Any]:
        """Wait for a long-running operation to complete with progress reporting."""
        logger.info(f"Waiting for operation to complete... (polling every {retry_after}s)")
        
        # Create progress bar for LRO status
        with tqdm(total=100, desc="Operation progress", unit="%", 
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as pbar:
            last_progress = 0
            
            for attempt in range(max_retries):
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
                    percent_complete = result.get('percentComplete', 0)
                    
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
        wait=wait_exponential(multiplier=2, min=2, max=60),
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
        wait=wait_exponential(multiplier=2, min=2, max=60),
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
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(_is_transient_error),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def get_ontology_definition(self, ontology_id: str) -> Dict[str, Any]:
        """
        Get the definition of a specific ontology.
        
        Args:
            ontology_id: The ontology ID
            
        Returns:
            Ontology definition object
        """
        url = f"{self.config.api_base_url}/workspaces/{self.config.workspace_id}/ontologies/{ontology_id}/getDefinition"
        
        logger.info(f"Getting ontology definition for {ontology_id}")
        
        response = self._make_request(
            'POST', url, f'Get ontology definition {ontology_id}',
            headers=self._get_headers()
        )
        
        result = self._handle_response(response)
        
        if result.get('_lro'):
            result = self._wait_for_operation(result['location'], result['retry_after'])
        
        return result
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(_is_transient_error),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def create_ontology(
        self,
        display_name: str,
        description: str = "",
        definition: Optional[Dict[str, Any]] = None,
        wait_for_completion: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new ontology.
        
        Args:
            display_name: The ontology display name
            description: The ontology description
            definition: Optional ontology definition with parts
            wait_for_completion: Whether to wait for LRO to complete
            
        Returns:
            Created ontology object
        """
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
        
        if result.get('_lro') and wait_for_completion:
            result = self._wait_for_operation(result['location'], result['retry_after'])
            # After LRO completes, fetch the created ontology
            if 'id' in result:
                return self.get_ontology(result['id'])
        
        logger.info(f"Ontology created: {result.get('id', 'Unknown ID')}")
        return result
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(_is_transient_error),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def update_ontology_definition(
        self,
        ontology_id: str,
        definition: Dict[str, Any],
        update_metadata: bool = True,
        wait_for_completion: bool = True,
    ) -> Dict[str, Any]:
        """
        Update the definition of an existing ontology.
        
        Args:
            ontology_id: The ontology ID
            definition: The new ontology definition
            update_metadata: Whether to update metadata from .platform file
            wait_for_completion: Whether to wait for LRO to complete
            
        Returns:
            Updated ontology object
        """
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
            result = self._wait_for_operation(result['location'], result['retry_after'])
        
        logger.info(f"Ontology definition updated successfully")
        return result
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
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
        wait=wait_exponential(multiplier=2, min=2, max=60),
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
            
        Returns:
            Created or updated ontology object
        """
        # Check if ontology exists
        safe_name = self._sanitize_display_name(display_name)
        existing = self.find_ontology_by_name(safe_name)
        
        if existing:
            logger.info(f"Ontology '{safe_name}' already exists. Updating definition...")
            ontology_id = existing['id']
            
            # Update the definition if provided
            if definition:
                self.update_ontology_definition(
                    ontology_id=ontology_id,
                    definition=definition
                )
            
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
                wait_for_completion=wait_for_completion
            )


class FabricAPIError(Exception):
    """Exception raised for Fabric API errors."""
    
    def __init__(self, status_code: int, error_code: str, message: str):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(f"[{error_code}] {message} (HTTP {status_code})")
