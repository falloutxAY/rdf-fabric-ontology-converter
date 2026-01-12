"""
SDK Adapter for Fabric Ontology SDK integration.

This module provides an adapter layer that bridges the converter's existing interface
to the official Fabric Ontology SDK. It allows incremental migration from the legacy
FabricOntologyClient to the SDK's FabricClient.

The adapter:
1. Wraps SDK's FabricClient with converter-compatible interface
2. Maps converter's FabricConfig to SDK configuration
3. Preserves resilience features (rate limiting, circuit breaker) from legacy client
4. Provides feature flags to switch between SDK and legacy implementations

Migration Strategy:
    Phase 1: Add SDK as dependency, create adapter (this file)
    Phase 2: New code uses SDK via adapter
    Phase 3: Migrate existing callers incrementally
    Phase 4: Remove legacy FabricOntologyClient after full migration

Usage:
    from core.platform.sdk_adapter import create_sdk_client, SDKClientAdapter
    
    # Create adapter from existing config
    adapter = create_sdk_client(fabric_config)
    
    # Use SDK methods via adapter
    ontology = adapter.create_ontology("MyOntology", "Description")
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# SDK imports
try:
    from fabric_ontology import FabricClient, OntologyBuilder
    from fabric_ontology.models import OntologyDefinition, EntityType, RelationshipType
    from fabric_ontology.exceptions import (
        FabricOntologyError,
        AuthenticationError as SDKAuthenticationError,
        ValidationError as SDKValidationError,
        ApiError as SDKApiError,
    )
    from fabric_ontology.resilience import (
        RateLimiter as SDKRateLimiter,
        CircuitBreaker as SDKCircuitBreaker,
        CircuitBreakerOpenError as SDKCircuitBreakerOpenError,
    )
    from fabric_ontology.validation import NAME_PATTERN as SDK_NAME_PATTERN
    from fabric_ontology.models import PropertyDataType as SDKPropertyDataType
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    FabricClient = None  # type: ignore
    OntologyBuilder = None  # type: ignore
    SDKRateLimiter = None  # type: ignore
    SDKCircuitBreaker = None  # type: ignore
    SDKCircuitBreakerOpenError = None  # type: ignore
    SDK_NAME_PATTERN = None  # type: ignore
    SDKPropertyDataType = None  # type: ignore

# Local imports for legacy client compatibility
from .fabric_client import FabricConfig, FabricOntologyClient, FabricAPIError

logger = logging.getLogger(__name__)

# Feature flag for SDK usage (can be overridden by environment variable)
USE_SDK = os.environ.get("FABRIC_USE_SDK", "false").lower() == "true"


@dataclass
class SDKConfig:
    """Configuration mapped from FabricConfig to SDK format."""
    workspace_id: str
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    use_interactive_auth: bool = True
    
    @classmethod
    def from_fabric_config(cls, config: FabricConfig) -> "SDKConfig":
        """Create SDK config from legacy FabricConfig."""
        return cls(
            workspace_id=config.workspace_id,
            tenant_id=config.tenant_id,
            client_id=config.client_id,
            client_secret=config.client_secret,
            use_interactive_auth=config.use_interactive_auth,
        )


class SDKClientAdapter:
    """
    Adapter that wraps SDK's FabricClient with converter-compatible interface.
    
    This adapter provides the same method signatures as FabricOntologyClient
    but delegates to the SDK internally. This allows gradual migration without
    changing caller code.
    
    Attributes:
        sdk_client: The underlying SDK FabricClient
        workspace_id: The Fabric workspace ID
        config: The original FabricConfig for compatibility
    """
    
    def __init__(self, config: FabricConfig):
        """
        Initialize the SDK adapter.
        
        Args:
            config: FabricConfig with connection details
            
        Raises:
            ImportError: If SDK is not installed
            ValueError: If configuration is invalid
        """
        if not SDK_AVAILABLE:
            raise ImportError(
                "fabric-ontology-sdk is not installed. "
                "Install with: pip install fabric-ontology-sdk @ git+https://github.com/falloutxAY/Unofficial-Fabric-Ontology-SDK.git@v0.4.0"
            )
        
        self.config = config
        self.workspace_id = config.workspace_id
        
        # Create SDK client based on auth method
        if config.client_id and config.client_secret and config.tenant_id:
            logger.info("Creating SDK client with service principal authentication")
            self.sdk_client = FabricClient.from_service_principal(
                tenant_id=config.tenant_id,
                client_id=config.client_id,
                client_secret=config.client_secret,
            )
        else:
            logger.info("Creating SDK client with interactive authentication")
            self.sdk_client = FabricClient.from_interactive(
                tenant_id=config.tenant_id,
            )
        
        # Note: SDK doesn't have built-in rate limiting or circuit breaker yet
        # These features remain in the legacy client for now
        if config.rate_limit.enabled:
            logger.warning(
                "Rate limiting is enabled in config but SDK doesn't support it yet. "
                "Consider using legacy client for rate-limited operations."
            )
        
        if config.circuit_breaker.enabled:
            logger.warning(
                "Circuit breaker is enabled in config but SDK doesn't support it yet. "
                "Consider using legacy client for circuit-breaker protected operations."
            )
    
    def create_ontology(
        self,
        display_name: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new ontology in the workspace.
        
        Args:
            display_name: Display name for the ontology
            description: Optional description
            
        Returns:
            Dict with ontology metadata including 'id'
        """
        try:
            result = self.sdk_client.ontologies.create(
                workspace_id=self.workspace_id,
                display_name=display_name,
                description=description,
            )
            # Convert SDK response to legacy format for compatibility
            return {
                "id": result.get("id"),
                "displayName": result.get("displayName", display_name),
                "description": result.get("description", description),
                "type": "Ontology",
            }
        except SDKApiError as e:
            # Re-raise as legacy FabricAPIError for compatibility
            raise FabricAPIError(
                status_code=getattr(e, "status_code", 500),
                error_code=getattr(e, "error_code", "SDKError"),
                message=str(e),
            )
    
    def get_ontology(self, ontology_id: str) -> Dict[str, Any]:
        """
        Get ontology metadata by ID.
        
        Args:
            ontology_id: The ontology ID
            
        Returns:
            Dict with ontology metadata
        """
        try:
            return self.sdk_client.ontologies.get(
                workspace_id=self.workspace_id,
                ontology_id=ontology_id,
            )
        except SDKApiError as e:
            raise FabricAPIError(
                status_code=getattr(e, "status_code", 500),
                error_code=getattr(e, "error_code", "SDKError"),
                message=str(e),
            )
    
    def list_ontologies(self) -> List[Dict[str, Any]]:
        """
        List all ontologies in the workspace.
        
        Returns:
            List of ontology metadata dicts
        """
        try:
            return self.sdk_client.ontologies.list(workspace_id=self.workspace_id)
        except SDKApiError as e:
            raise FabricAPIError(
                status_code=getattr(e, "status_code", 500),
                error_code=getattr(e, "error_code", "SDKError"),
                message=str(e),
            )
    
    def delete_ontology(self, ontology_id: str) -> None:
        """
        Delete an ontology.
        
        Args:
            ontology_id: The ontology ID to delete
        """
        try:
            self.sdk_client.ontologies.delete(
                workspace_id=self.workspace_id,
                ontology_id=ontology_id,
            )
        except SDKApiError as e:
            raise FabricAPIError(
                status_code=getattr(e, "status_code", 500),
                error_code=getattr(e, "error_code", "SDKError"),
                message=str(e),
            )
    
    def update_ontology_definition(
        self,
        ontology_id: str,
        definition: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an ontology's definition.
        
        Args:
            ontology_id: The ontology ID
            definition: The ontology definition dict
            
        Returns:
            Updated definition
        """
        try:
            return self.sdk_client.ontologies.update_definition(
                workspace_id=self.workspace_id,
                ontology_id=ontology_id,
                definition=definition,
            )
        except SDKApiError as e:
            raise FabricAPIError(
                status_code=getattr(e, "status_code", 500),
                error_code=getattr(e, "error_code", "SDKError"),
                message=str(e),
            )
    
    def get_ontology_definition(self, ontology_id: str) -> Dict[str, Any]:
        """
        Get an ontology's definition.
        
        Args:
            ontology_id: The ontology ID
            
        Returns:
            The ontology definition dict
        """
        try:
            return self.sdk_client.ontologies.get_definition(
                workspace_id=self.workspace_id,
                ontology_id=ontology_id,
            )
        except SDKApiError as e:
            raise FabricAPIError(
                status_code=getattr(e, "status_code", 500),
                error_code=getattr(e, "error_code", "SDKError"),
                message=str(e),
            )
    
    def get_builder(self) -> "OntologyBuilder":
        """
        Get an OntologyBuilder instance for fluent ontology construction.
        
        Returns:
            OntologyBuilder from the SDK
        """
        return OntologyBuilder()


def create_sdk_client(config: FabricConfig) -> SDKClientAdapter:
    """
    Factory function to create an SDK adapter from FabricConfig.
    
    Args:
        config: FabricConfig with connection details
        
    Returns:
        SDKClientAdapter instance
    """
    return SDKClientAdapter(config)


def create_client(
    config: FabricConfig,
    use_sdk: Optional[bool] = None,
) -> "FabricOntologyClient | SDKClientAdapter":
    """
    Factory function to create either SDK adapter or legacy client.
    
    This function respects the USE_SDK feature flag and allows explicit override.
    Use this for gradual migration - callers don't need to change.
    
    Args:
        config: FabricConfig with connection details
        use_sdk: Optional override for SDK usage. If None, uses USE_SDK flag.
        
    Returns:
        Either SDKClientAdapter or FabricOntologyClient
    """
    should_use_sdk = use_sdk if use_sdk is not None else USE_SDK
    
    if should_use_sdk:
        if not SDK_AVAILABLE:
            logger.warning(
                "SDK requested but not available. Falling back to legacy client."
            )
            return FabricOntologyClient(config)
        
        logger.info("Using SDK client via adapter")
        return SDKClientAdapter(config)
    else:
        logger.info("Using legacy FabricOntologyClient")
        return FabricOntologyClient(config)


def is_sdk_available() -> bool:
    """Check if the SDK is installed and available."""
    return SDK_AVAILABLE
