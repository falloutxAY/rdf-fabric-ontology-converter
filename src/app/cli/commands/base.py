"""
Base command class and protocols.

This module contains the base command class that all CLI commands inherit from,
as well as protocol definitions for dependency injection.
"""

import argparse
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from ..helpers import (
    load_config,
    get_default_config_path,
    setup_logging,
    print_header,
    print_footer,
    confirm_action,
)
from shared.models import ConversionResult
from plugins.protocols import ConverterProtocol
from constants import ExitCode


logger = logging.getLogger(__name__)


# ============================================================================
# Helper Utilities
# ============================================================================

def print_conversion_summary(result: ConversionResult, heading: Optional[str] = None) -> None:
    """Print a consistent summary for any converter result."""
    if heading:
        print_header(heading)
    print(result.get_summary())
    if heading:
        print_footer()


# ============================================================================
# Protocols for Dependency Injection
# ============================================================================

class IValidator(Protocol):
    """Protocol for TTL validation."""
    
    def validate(self, content: str, file_path: str) -> Any:
        """Validate TTL content."""
        ...


class IConverter(ConverterProtocol, Protocol):
    """Alias for the shared converter protocol."""
    ...


class IFabricClient(Protocol):
    """Protocol for Fabric API operations."""
    
    def list_ontologies(self) -> list:
        """List all ontologies."""
        ...
    
    def get_ontology(self, ontology_id: str) -> dict:
        """Get ontology by ID."""
        ...
    
    def get_ontology_definition(self, ontology_id: str) -> dict:
        """Get ontology definition."""
        ...
    
    def create_or_update_ontology(
        self,
        display_name: str,
        description: str,
        definition: dict,
        wait_for_completion: bool = True,
        cancellation_token: Any = None
    ) -> dict:
        """Create or update an ontology."""
        ...
    
    def delete_ontology(self, ontology_id: str) -> None:
        """Delete an ontology."""
        ...


# ============================================================================
# Base Command Class
# ============================================================================

class BaseCommand(ABC):
    """
    Base class for CLI commands.
    
    Provides common functionality like configuration loading and logging setup.
    Subclasses should implement the execute() method.
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        validator: Optional[IValidator] = None,
        converter: Optional[IConverter] = None,
        client: Optional[IFabricClient] = None,
    ):
        """
        Initialize the command.
        
        Args:
            config_path: Path to configuration file.
            validator: Optional validator instance (for dependency injection).
            converter: Optional converter instance (for dependency injection).
            client: Optional Fabric client instance (for dependency injection).
        """
        self.config_path = config_path or get_default_config_path()
        self._validator = validator
        self._converter = converter
        self._client = client
        self._config: Optional[Dict[str, Any]] = None
    
    @property
    def config(self) -> Dict[str, Any]:
        """Lazy-load configuration."""
        if self._config is None:
            self._config = load_config(self.config_path)
        return self._config
    
    def get_validator(self) -> IValidator:
        """Get or create validator instance."""
        if self._validator is None:
            from rdf import PreflightValidator
            self._validator = PreflightValidator()
        return self._validator
    
    def get_client(self) -> IFabricClient:
        """Get or create Fabric client instance."""
        if self._client is None:
            from core import FabricConfig, FabricOntologyClient
            fabric_config = FabricConfig.from_dict(self.config)
            self._client = FabricOntologyClient(fabric_config)
        return self._client
    
    def setup_logging_from_config(self, allow_missing: bool = True) -> None:
        """Setup logging configuration, falling back gracefully if config is absent."""
        log_config: Dict[str, Any] = {}

        if self._config is not None:
            log_config = self._config.get('logging', {})
        else:
            config_path = Path(self.config_path)
            if config_path.exists() or not allow_missing:
                try:
                    config_data = load_config(self.config_path)
                    self._config = config_data
                    log_config = config_data.get('logging', {})
                except FileNotFoundError:
                    if not allow_missing:
                        raise
                except Exception as exc:
                    if not allow_missing:
                        raise
                    print(f"Warning: Could not load logging configuration: {exc}")

        setup_logging(config=log_config)
    
    @abstractmethod
    def execute(self, args: argparse.Namespace) -> int:
        """
        Execute the command.
        
        Args:
            args: Parsed command-line arguments.
            
        Returns:
            Exit code (0 for success, non-zero for error).
        """
        pass
