"""
Authentication helpers for Microsoft Fabric API.

This module provides authentication utilities for the Fabric API client,
supporting multiple credential types.

Classes:
    TokenManager: Thread-safe access token management with caching
    CredentialFactory: Factory for creating Azure credentials
"""

import time
import logging
import threading
from typing import Optional, List

from azure.identity import (
    InteractiveBrowserCredential,
    ClientSecretCredential,
    DefaultAzureCredential,
    ChainedTokenCredential,
)
from azure.core.credentials import TokenCredential

logger = logging.getLogger(__name__)

# Fabric API scope
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


class CredentialFactory:
    """Factory for creating Azure credentials based on configuration.
    
    Creates appropriate credential chain based on available authentication
    options (service principal, interactive browser, managed identity).
    
    Example:
        >>> config = FabricConfig(workspace_id="...", client_id="...", client_secret="...")
        >>> credential = CredentialFactory.create_credential(config)
    """
    
    @staticmethod
    def create_credential(
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        use_interactive_auth: bool = True,
    ) -> TokenCredential:
        """Create a chained token credential based on configuration.
        
        The credential chain tries authentication methods in order:
        1. Service principal (if client_id and client_secret provided)
        2. Interactive browser (if enabled)
        3. Default Azure credential (managed identity, environment vars, etc.)
        
        Args:
            tenant_id: Azure AD tenant ID
            client_id: Service principal client ID
            client_secret: Service principal client secret
            use_interactive_auth: Whether to enable interactive browser auth
            
        Returns:
            TokenCredential: Chained credential for authentication
        """
        credentials: List[TokenCredential] = []
        
        # Service principal authentication
        if client_id and client_secret and tenant_id:
            logger.info("Adding client secret credential to auth chain")
            credentials.append(
                ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                )
            )
        
        # Interactive browser authentication
        if use_interactive_auth:
            logger.info("Adding interactive browser credential to auth chain")
            # Only pass tenant_id/client_id if they have non-empty values
            # Empty strings cause Azure Identity to fail validation
            interactive_kwargs = {}
            if tenant_id:
                interactive_kwargs['tenant_id'] = tenant_id
            if client_id:
                interactive_kwargs['client_id'] = client_id
            credentials.append(
                InteractiveBrowserCredential(**interactive_kwargs)
            )
        
        # Default Azure credential (for managed identities, etc.)
        credentials.append(DefaultAzureCredential())
        
        return ChainedTokenCredential(*credentials)


class TokenManager:
    """Thread-safe access token manager with caching.
    
    Manages acquisition and caching of access tokens for the Fabric API.
    Uses a reentrant lock to ensure thread-safe token acquisition.
    
    Attributes:
        scope: The OAuth scope to request tokens for
        token_buffer_seconds: Buffer time before token expiry to refresh
        
    Example:
        >>> manager = TokenManager(credential)
        >>> token = manager.get_access_token()
        >>> headers = {"Authorization": f"Bearer {token}"}
    """
    
    def __init__(
        self,
        credential: TokenCredential,
        scope: str = FABRIC_SCOPE,
        token_buffer_seconds: int = 300,
    ):
        """Initialize the token manager.
        
        Args:
            credential: Azure TokenCredential for authentication
            scope: OAuth scope to request (defaults to Fabric API)
            token_buffer_seconds: Refresh token this many seconds before expiry
        """
        self._credential = credential
        self._scope = scope
        self._token_buffer_seconds = token_buffer_seconds
        self._access_token: Optional[str] = None
        self._token_expires: float = 0
        self._token_lock = threading.RLock()
    
    def get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary (thread-safe).
        
        Uses a reentrant lock to ensure thread-safe token acquisition.
        Multiple threads requesting tokens concurrently will:
        1. All wait for the lock if token needs refresh
        2. Only one thread acquires the new token
        3. Subsequent threads use the cached token
        
        Returns:
            Valid access token string
            
        Raises:
            AuthenticationError: If token acquisition fails
        """
        with self._token_lock:
            current_time = time.time()
            
            # Check if cached token is still valid (with buffer)
            if self._access_token and current_time < self._token_expires - self._token_buffer_seconds:
                logger.debug("Using cached access token")
                return self._access_token
            
            logger.info("Acquiring access token...")
            
            try:
                token = self._credential.get_token(self._scope)
            except Exception as e:
                logger.error(f"Authentication failed: {e}")
                raise AuthenticationError(f"Failed to acquire access token: {e}")
            
            if not token or not token.token:
                raise AuthenticationError("Received empty token from credential provider")
            
            # Atomic state update (within lock)
            self._access_token = token.token
            self._token_expires = token.expires_on
            
            logger.info("Access token acquired successfully")
            return self._access_token
    
    def invalidate_token(self) -> None:
        """Invalidate the cached token to force refresh on next request."""
        with self._token_lock:
            self._access_token = None
            self._token_expires = 0
            logger.debug("Token cache invalidated")
    
    @property
    def is_token_valid(self) -> bool:
        """Check if the cached token is still valid."""
        with self._token_lock:
            if not self._access_token:
                return False
            return time.time() < self._token_expires - self._token_buffer_seconds


class AuthenticationError(Exception):
    """Exception raised for authentication failures."""
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
