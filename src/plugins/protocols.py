"""
Protocol Definitions for Plugin Components.

This module defines the protocols (interfaces) that plugin components
must implement. Using protocols allows for duck typing while still
providing type hints and documentation.

Protocols:
    ParserProtocol: Parse ontology content (generic over output type)
    ValidatorProtocol: Validate ontology content
    ConverterProtocol: Convert to Fabric format
    ExporterProtocol: Export from Fabric format
    StreamingParserProtocol: Stream large ontology files
    StreamingConverterProtocol: Stream conversion of large ontologies
"""

from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)

# Type variables for generic protocols
T = TypeVar('T')  # Parsed representation type (e.g., Graph, List[DTDLInterface])
T_co = TypeVar('T_co', covariant=True)  # Covariant for return types
ValidationResultT = TypeVar('ValidationResultT')  # Validation result type
ConversionResultT = TypeVar('ConversionResultT')  # Conversion result type


__all__ = [
    # Type variables
    "T",
    "T_co",
    "ValidationResultT",
    "ConversionResultT",
    # Core protocols
    "ParserProtocol",
    "ValidatorProtocol",
    "ConverterProtocol",
    "ExporterProtocol",
    # Streaming protocols
    "StreamingAdapterProtocol",
    "StreamingParserProtocol",
    "StreamingConverterProtocol",
    # Type checking utilities
    "is_parser",
    "is_validator",
    "is_converter",
    "is_exporter",
    "is_streaming_parser",
    "is_streaming_converter",
    "is_streaming_adapter",
]


@runtime_checkable
class ParserProtocol(Protocol[T_co]):
    """
    Protocol for parsing ontology content.
    
    Generic over the output type T_co, which is the format-specific
    internal representation:
    - RDF: rdflib.Graph
    - DTDL: List[DTDLInterface]
    - JSON-LD: Dict or rdflib.Graph
    
    Parsers are responsible for reading source content (strings or files)
    and converting them into an internal representation specific to the
    format.
    
    The internal representation is then used by validators and converters.
    
    Example implementation:
        class RDFParser(ParserProtocol[Graph]):
            def parse(self, content: str, file_path: Optional[str] = None) -> Graph:
                g = Graph()
                g.parse(data=content, format='turtle')
                return g
            
            def parse_file(self, file_path: str) -> Graph:
                g = Graph()
                g.parse(file_path)
                return g
        
        class DTDLParser(ParserProtocol[List[DTDLInterface]]):
            def parse(self, content: str, file_path: Optional[str] = None) -> List[DTDLInterface]:
                return parse_dtdl_json(content)
    """
    
    def parse(self, content: str, file_path: Optional[str] = None) -> T_co:
        """
        Parse content string.
        
        Args:
            content: Source content as string.
            file_path: Optional path for error messages.
        
        Returns:
            Format-specific internal representation (type T_co).
        
        Raises:
            ValueError: If content cannot be parsed.
        """
        ...
    
    def parse_file(self, file_path: str) -> T_co:
        """
        Parse a file.
        
        Args:
            file_path: Path to the file to parse.
        
        Returns:
            Format-specific internal representation (type T_co).
        
        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If content cannot be parsed.
        """
        ...


@runtime_checkable
class ValidatorProtocol(Protocol[ValidationResultT]):
    """
    Protocol for validating ontology content.
    
    Generic over ValidationResultT, the type of validation result returned.
    This allows format-specific validation results while maintaining
    a common interface.
    
    Validators check that content is well-formed and compatible with
    Fabric Ontology conversion. They produce ValidationResult with
    any issues found.
    
    Validators should check:
    - Syntax correctness
    - Required elements present
    - Valid references
    - Fabric compatibility (conversion limitations)
    
    Example implementation:
        class RDFValidator(ValidatorProtocol[ValidationResult]):
            def validate(self, content: str, file_path: Optional[str] = None) -> ValidationResult:
                result = ValidationResult(format_name="rdf", source_path=file_path)
                # ... validation logic ...
                return result
    """
    
    def validate(self, content: str, file_path: Optional[str] = None) -> ValidationResultT:
        """
        Validate content string.
        
        Args:
            content: Source content to validate.
            file_path: Optional path for error messages.
        
        Returns:
            ValidationResult with any issues found.
        """
        ...
    
    def validate_file(self, file_path: str) -> ValidationResultT:
        """
        Validate a file.
        
        Args:
            file_path: Path to the file to validate.
        
        Returns:
            ValidationResultT: Validation result with any issues found.
        """
        ...


@runtime_checkable
class ConverterProtocol(Protocol, Generic[ConversionResultT]):
    """
    Protocol for converting to Fabric Ontology format.
    
    Generic over ConversionResultT, the type of conversion result returned.
    This allows format-specific conversion results while maintaining
    a common interface.
    
    Converters transform source content into Fabric EntityType and
    RelationshipType objects, packaged in a ConversionResult.
    
    Converters should:
    - Map source types to Fabric types
    - Generate unique IDs for entities
    - Track skipped items and warnings
    - Handle inheritance and relationships
    
    Example implementation:
        class RDFConverter(ConverterProtocol[ConversionResult]):
            def convert(
                self,
                content: str,
                id_prefix: int = 1000000000000,
                **kwargs
            ) -> ConversionResult:
                # ... conversion logic ...
                return ConversionResult(...)
    """
    
    def convert(
        self,
        content: str,
        id_prefix: int = 1000000000000,
        **kwargs: Any,
    ) -> ConversionResultT:
        """
        Convert content to Fabric Ontology format.
        
        Args:
            content: Source content to convert.
            id_prefix: Starting ID for generated entities.
            **kwargs: Format-specific options.
        
        Returns:
            ConversionResultT: Conversion result with entities and relationships.
        """
        ...


@runtime_checkable
class ExporterProtocol(Protocol, Generic[T]):
    """
    Protocol for exporting from Fabric Ontology format.
    
    Generic over T, which represents the output format type (typically str
    or bytes, but could be a structured type for specific formats).
    
    Exporters transform Fabric EntityType and RelationshipType objects
    back into the plugin's format. This is optional - not all plugins
    need to support export.
    
    Example implementation:
        class RDFExporter(ExporterProtocol[str]):
            def export(
                self,
                entity_types: List[EntityType],
                relationship_types: List[RelationshipType],
                **kwargs
            ) -> str:
                # ... export logic ...
                return serialized_rdf
    """
    
    def export(
        self,
        entity_types: List[Any],
        relationship_types: List[Any],
        **kwargs: Any,
    ) -> T:
        """
        Export Fabric entities to this format.
        
        Args:
            entity_types: List of EntityType objects.
            relationship_types: List of RelationshipType objects.
            **kwargs: Format-specific options.
        
        Returns:
            T: Exported content in the target format.
        """
        ...
    
    def export_to_file(
        self,
        entity_types: List[Any],
        relationship_types: List[Any],
        file_path: str,
        **kwargs: Any,
    ) -> None:
        """
        Export Fabric entities to a file.
        
        Args:
            entity_types: List of EntityType objects.
            relationship_types: List of RelationshipType objects.
            file_path: Output file path.
            **kwargs: Format-specific options.
        """
        ...


@runtime_checkable
class StreamingAdapterProtocol(Protocol, Generic[T_co]):
    """
    Protocol for streaming large file processing.
    
    Generic over T_co, the type of items yielded during streaming conversion.
    
    Streaming adapters process large files incrementally to avoid
    loading the entire file into memory. This is optional and only
    needed for formats that may have very large files.
    
    Example implementation:
        class RDFStreamingAdapter(StreamingAdapterProtocol[ConversionResult]):
            def stream_convert(
                self,
                file_path: str,
                chunk_callback: Callable[[ConversionResult], None],
                id_prefix: int = 1000000000000,
                **kwargs
            ) -> ConversionResult:
                # ... streaming conversion logic ...
                return combined_result
    """
    
    def stream_convert(
        self,
        file_path: str,
        chunk_callback: Callable[[T_co], None],
        id_prefix: int = 1000000000000,
        **kwargs: Any,
    ) -> T_co:
        """
        Convert a file using streaming.
        
        Args:
            file_path: Path to the file to convert.
            chunk_callback: Called with each chunk's result (receives T_co).
            id_prefix: Starting ID for generated entities.
            **kwargs: Format-specific options.
        
        Returns:
            T_co: Combined result from all chunks.
        """
        ...
    
    def estimate_memory(self, file_path: str) -> int:
        """
        Estimate memory required to process a file.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            Estimated bytes of memory required.
        """
        ...
    
    def should_stream(self, file_path: str) -> bool:
        """
        Determine if streaming should be used for a file.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            True if streaming is recommended.
        """
        ...


# =============================================================================
# Streaming Pipeline Protocols (P3.3)
# =============================================================================


@runtime_checkable
class StreamingParserProtocol(Protocol, Generic[T_co]):
    """
    Protocol for streaming/iterative parsing of ontology content.
    
    Generic over T_co, the type of items yielded during parsing.
    Unlike ParserProtocol which returns a complete result, this protocol
    yields items one at a time for memory-efficient processing of large files.
    
    Example implementation:
        class RDFStreamingParser(StreamingParserProtocol[Triple]):
            def iter_parse(self, content: str) -> Iterator[Triple]:
                for line in content.splitlines():
                    if triple := parse_triple(line):
                        yield triple
            
            async def aiter_parse(self, content: str) -> AsyncIterator[Triple]:
                for line in content.splitlines():
                    if triple := parse_triple(line):
                        yield triple
                        await asyncio.sleep(0)  # Yield control
    """
    
    def iter_parse(self, content: str) -> Iterator[T_co]:
        """
        Iteratively parse ontology content.
        
        Args:
            content: The ontology content as a string.
            
        Yields:
            T_co: Parsed items one at a time.
        """
        ...
    
    def iter_parse_file(self, file_path: str) -> Iterator[T_co]:
        """
        Iteratively parse ontology content from a file.
        
        Args:
            file_path: Path to the ontology file.
            
        Yields:
            T_co: Parsed items one at a time.
        """
        ...
    
    async def aiter_parse(self, content: str) -> AsyncIterator[T_co]:
        """
        Asynchronously iterate over parsed ontology content.
        
        Args:
            content: The ontology content as a string.
            
        Yields:
            T_co: Parsed items one at a time.
        """
        ...
    
    async def aiter_parse_file(self, file_path: str) -> AsyncIterator[T_co]:
        """
        Asynchronously iterate over parsed ontology content from a file.
        
        Args:
            file_path: Path to the ontology file.
            
        Yields:
            T_co: Parsed items one at a time.
        """
        ...


@runtime_checkable
class StreamingConverterProtocol(Protocol, Generic[T, T_co]):
    """
    Protocol for streaming/iterative conversion to Fabric Ontology format.
    
    Generic over:
        T: The type of input items to convert (from streaming parser).
        T_co: The type of converted items yielded.
    
    Unlike ConverterProtocol which returns a complete ConversionResult,
    this protocol converts items one at a time for memory-efficient
    processing of large ontologies.
    
    Example implementation:
        class RDFStreamingConverter(StreamingConverterProtocol[Triple, EntityType]):
            def iter_convert(
                self,
                items: Iterator[Triple],
                id_prefix: int = 1000000000000,
                **kwargs
            ) -> Iterator[EntityType]:
                for idx, triple in enumerate(items):
                    yield convert_triple_to_entity(triple, id_prefix + idx)
            
            async def aiter_convert(
                self,
                items: AsyncIterator[Triple],
                id_prefix: int = 1000000000000,
                **kwargs
            ) -> AsyncIterator[EntityType]:
                idx = 0
                async for triple in items:
                    yield convert_triple_to_entity(triple, id_prefix + idx)
                    idx += 1
    """
    
    def iter_convert(
        self,
        items: Iterator[T],
        id_prefix: int = 1000000000000,
        **kwargs: Any,
    ) -> Iterator[T_co]:
        """
        Iteratively convert items to Fabric Ontology format.
        
        Args:
            items: Iterator of parsed items to convert.
            id_prefix: Starting ID for generated entities.
            **kwargs: Format-specific options.
            
        Yields:
            T_co: Converted items one at a time.
        """
        ...
    
    async def aiter_convert(
        self,
        items: AsyncIterator[T],
        id_prefix: int = 1000000000000,
        **kwargs: Any,
    ) -> AsyncIterator[T_co]:
        """
        Asynchronously convert items to Fabric Ontology format.
        
        Args:
            items: Async iterator of parsed items to convert.
            id_prefix: Starting ID for generated entities.
            **kwargs: Format-specific options.
            
        Yields:
            T_co: Converted items one at a time.
        """
        ...


# =============================================================================
# Type Checking Utilities
# =============================================================================

def is_parser(obj: Any) -> bool:
    """Check if object implements ParserProtocol."""
    return isinstance(obj, ParserProtocol)


def is_validator(obj: Any) -> bool:
    """Check if object implements ValidatorProtocol."""
    return isinstance(obj, ValidatorProtocol)


def is_converter(obj: Any) -> bool:
    """Check if object implements ConverterProtocol."""
    return isinstance(obj, ConverterProtocol)


def is_exporter(obj: Any) -> bool:
    """Check if object implements ExporterProtocol."""
    return isinstance(obj, ExporterProtocol)


def is_streaming_parser(obj: Any) -> bool:
    """Check if object implements StreamingParserProtocol."""
    return isinstance(obj, StreamingParserProtocol)


def is_streaming_converter(obj: Any) -> bool:
    """Check if object implements StreamingConverterProtocol."""
    return isinstance(obj, StreamingConverterProtocol)


def is_streaming_adapter(obj: Any) -> bool:
    """Check if object implements StreamingAdapterProtocol."""
    return isinstance(obj, StreamingAdapterProtocol)
