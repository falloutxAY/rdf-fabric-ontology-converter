"""
Base converter protocol and abstract types.

This module defines the common interface that all format converters
(RDF, DTDL, etc.) must implement for consistent behavior.

Note:
    The canonical ConverterProtocol definition is in plugins.protocols.
    This module re-exports it for backward compatibility and provides
    the BaseConverter abstract class.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .conversion import ConversionResult

# Import the canonical protocol definition from plugins
# This ensures a single source of truth for the protocol interface
from plugins.protocols import ConverterProtocol

# Re-export for backward compatibility
__all__ = ['ConverterProtocol', 'BaseConverter']


class BaseConverter(ABC):
    """
    Abstract base class for ontology format converters.
    
    Provides common functionality and enforces the converter interface.
    Subclasses must implement convert() and validate() methods.
    
    Attributes:
        default_namespace: Default namespace for generated entities.
        id_counter: Counter for generating unique IDs.
    """
    
    def __init__(
        self,
        default_namespace: str = "usertypes",
        id_prefix: int = 1000000000000,
    ) -> None:
        """
        Initialize the converter.
        
        Args:
            default_namespace: Namespace for generated entities.
            id_prefix: Starting ID for entity generation.
        """
        self.default_namespace = default_namespace
        self.id_counter = id_prefix
    
    def _next_id(self) -> str:
        """Generate the next unique ID."""
        current = self.id_counter
        self.id_counter += 1
        return str(current)
    
    @abstractmethod
    def convert(
        self,
        content: str,
        id_prefix: int = 1000000000000,
        **kwargs: Any,
    ) -> ConversionResult:
        """
        Convert content to Fabric Ontology format.
        
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    def validate(self, content: str) -> bool:
        """
        Validate source content.
        
        Must be implemented by subclasses.
        """
        pass
    
    def get_format_name(self) -> str:
        """
        Get the name of the source format this converter handles.
        
        Returns:
            Human-readable format name (e.g., "RDF/TTL", "DTDL v4").
        """
        return self.__class__.__name__.replace("Converter", "").replace("ToFabric", "")
