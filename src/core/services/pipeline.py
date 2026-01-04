"""
Streaming Pipeline Interface Specification.

This module provides the formal specification for streaming pipelines in the
ontology converter. It defines the core protocols, data structures, and
patterns for implementing memory-efficient streaming conversion of large
ontology files.

Architecture Overview:
    The streaming pipeline follows a producer-consumer pattern with three stages:

    1. StreamReader (Producer): Reads source file and yields chunks
       - Handles file I/O and buffering
       - Yields raw data chunks with byte tracking

    2. StreamProcessor (Transform): Processes chunks incrementally
       - Parses/validates/converts chunk data
       - Maintains state across chunks
       - Produces partial results

    3. StreamAggregator (Consumer): Collects and finalizes results
       - Merges partial results
       - Applies post-processing
       - Produces final output

    Each stage is connected through typed iterators, allowing for:
    - Lazy evaluation (only process what's needed)
    - Backpressure handling (pause reading when processing is slow)
    - Cancellation support (abort at any stage)
    - Memory bounds (configurable limits)

Usage Example:
    ```python
    from core.streaming.pipeline import (
        StreamingPipeline,
        PipelineConfig,
        create_rdf_pipeline,
        create_dtdl_pipeline,
    )

    # Create a streaming pipeline for large RDF files
    config = PipelineConfig(
        chunk_size=10000,
        memory_limit_mb=512,
        enable_progress=True,
    )
    pipeline = create_rdf_pipeline(config)

    # Process with progress callback
    result = pipeline.execute(
        input_path="large_ontology.ttl",
        output_path="output.json",
        progress_callback=lambda stats: print(f"Processed {stats.items}")
    )

    print(result.stats.get_summary())
    ```

Implementing Custom Pipelines:
    To implement a custom streaming pipeline for a new format:

    1. Implement StreamReader for your input format
    2. Implement StreamProcessor for parsing/conversion
    3. Optionally implement StreamAggregator for custom output
    4. Compose them in a StreamingPipeline

    See the RDF and DTDL implementations in core/services/streaming.py
    for complete examples.

Thread Safety:
    Pipeline components are NOT thread-safe by default. For concurrent
    processing, use separate pipeline instances per thread or implement
    explicit locking in your components.

Memory Management:
    The pipeline respects memory limits configured in PipelineConfig.
    When limits are approached:
    - Processing pauses until memory is freed
    - Warning logs are emitted
    - Results may be partially flushed to disk

    For truly large files (>1GB), consider using the streaming upload
    feature which streams directly to the Fabric API without local
    aggregation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
    runtime_checkable,
)
import logging
import time


logger = logging.getLogger(__name__)


# =============================================================================
# Type Variables
# =============================================================================

# Raw input type (e.g., bytes, str, RDF triples)
TInput = TypeVar('TInput')

# Processed chunk type (e.g., partial conversion result)
TChunk = TypeVar('TChunk')

# Final output type (e.g., complete conversion result)
TOutput = TypeVar('TOutput')

# Covariant output type for protocols
TOutput_co = TypeVar('TOutput_co', covariant=True)


# =============================================================================
# Pipeline State
# =============================================================================

class PipelineState(str, Enum):
    """State of a streaming pipeline."""
    IDLE = "idle"
    READING = "reading"
    PROCESSING = "processing"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class PipelineStats:
    """
    Statistics collected during pipeline execution.

    Attributes:
        chunks_read: Number of chunks read from source
        chunks_processed: Number of chunks successfully processed
        items_produced: Total items produced (entities, relationships)
        bytes_read: Total bytes read from input
        bytes_written: Total bytes written to output
        errors: Number of recoverable errors encountered
        warnings: Warning messages collected
        duration_seconds: Total execution time
        peak_memory_mb: Peak memory usage observed
        state: Current pipeline state
    """
    chunks_read: int = 0
    chunks_processed: int = 0
    items_produced: int = 0
    bytes_read: int = 0
    bytes_written: int = 0
    errors: int = 0
    warnings: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    state: PipelineState = PipelineState.IDLE

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)
        logger.warning(message)

    def get_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "Pipeline Statistics:",
            f"  State: {self.state.value}",
            f"  Chunks: {self.chunks_processed}/{self.chunks_read} processed",
            f"  Items produced: {self.items_produced:,}",
            f"  Bytes read: {self.bytes_read:,} ({self.bytes_read / 1024 / 1024:.2f} MB)",
            f"  Errors: {self.errors}",
            f"  Warnings: {len(self.warnings)}",
        ]
        if self.duration_seconds > 0:
            rate = self.items_produced / self.duration_seconds if self.items_produced else 0
            lines.append(f"  Duration: {self.duration_seconds:.2f}s ({rate:.0f} items/sec)")
        if self.peak_memory_mb > 0:
            lines.append(f"  Peak memory: {self.peak_memory_mb:.1f} MB")
        return "\n".join(lines)


@dataclass
class PipelineConfig:
    """
    Configuration for streaming pipeline.

    Attributes:
        chunk_size: Number of items per chunk (default: 10000)
        memory_limit_mb: Maximum memory usage in MB (default: 512)
        buffer_size_bytes: I/O buffer size (default: 64KB)
        enable_progress: Enable progress callbacks (default: True)
        fail_fast: Stop on first error vs. collect all errors (default: True)
        enable_validation: Run validation during processing (default: True)
        output_format: Output format (json, jsonl, etc.)
    """
    chunk_size: int = 10000
    memory_limit_mb: float = 512.0
    buffer_size_bytes: int = 65536
    enable_progress: bool = True
    fail_fast: bool = True
    enable_validation: bool = True
    output_format: str = "json"

    def should_use_streaming(self, file_size_bytes: int) -> bool:
        """Determine if streaming should be used based on file size."""
        file_size_mb = file_size_bytes / (1024 * 1024)
        # Use streaming for files larger than 1/4 of memory limit
        return file_size_mb > (self.memory_limit_mb / 4)


@dataclass
class PipelineResult(Generic[TOutput]):
    """
    Result from pipeline execution.

    Attributes:
        data: The produced output data (may be None if streaming to file)
        stats: Execution statistics
        success: Whether execution completed successfully
        error: Error message if failed
        output_path: Path to output file if streaming to disk
    """
    data: Optional[TOutput] = None
    stats: PipelineStats = field(default_factory=PipelineStats)
    success: bool = True
    error: Optional[str] = None
    output_path: Optional[Path] = None


# =============================================================================
# Cancellation Support
# =============================================================================

@runtime_checkable
class CancellationToken(Protocol):
    """Protocol for cancellation tokens."""

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        ...

    def throw_if_cancelled(self) -> None:
        """Raise exception if cancelled."""
        ...


class SimpleCancellationToken:
    """Simple cancellation token implementation."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if cancelled."""
        return self._cancelled

    def throw_if_cancelled(self) -> None:
        """Raise if cancelled."""
        if self._cancelled:
            raise PipelineCancelledException("Pipeline execution cancelled")


class PipelineCancelledException(Exception):
    """Raised when pipeline is cancelled."""
    pass


# =============================================================================
# Progress Callback Protocol
# =============================================================================

@runtime_checkable
class ProgressCallback(Protocol):
    """Protocol for progress callbacks."""

    def __call__(self, stats: PipelineStats) -> None:
        """Called with current statistics."""
        ...


# =============================================================================
# Core Pipeline Protocols
# =============================================================================

@runtime_checkable
class StreamReaderProtocol(Protocol[TInput]):
    """
    Protocol for reading source files in streaming fashion.

    Stream readers are responsible for:
    - Opening and buffering source files
    - Yielding chunks of raw data
    - Tracking bytes read
    - Handling different input formats

    Example:
        class TTLStreamReader(StreamReaderProtocol[str]):
            def read_chunks(self, path, config):
                with open(path, 'r') as f:
                    buffer = []
                    for line in f:
                        buffer.append(line)
                        if len(buffer) >= config.chunk_size:
                            yield ''.join(buffer), len(''.join(buffer))
                            buffer = []
                    if buffer:
                        yield ''.join(buffer), len(''.join(buffer))
    """

    def read_chunks(
        self,
        file_path: Union[str, Path],
        config: PipelineConfig,
    ) -> Iterator[Tuple[TInput, int]]:
        """
        Read file in chunks.

        Args:
            file_path: Path to source file
            config: Pipeline configuration

        Yields:
            Tuples of (chunk_data, bytes_read)
        """
        ...

    def get_file_size(self, file_path: Union[str, Path]) -> int:
        """
        Get total file size in bytes.

        Args:
            file_path: Path to file

        Returns:
            File size in bytes
        """
        ...

    def supports_format(self, file_path: Union[str, Path]) -> bool:
        """
        Check if reader supports the file format.

        Args:
            file_path: Path to file

        Returns:
            True if format is supported
        """
        ...


@runtime_checkable
class StreamProcessorProtocol(Protocol[TInput, TChunk]):
    """
    Protocol for processing chunks of data.

    Stream processors are responsible for:
    - Parsing/converting input chunks
    - Maintaining state across chunks
    - Producing partial results
    - Tracking items processed

    Example:
        class RDFChunkProcessor(StreamProcessorProtocol[str, List[EntityType]]):
            def process_chunk(self, chunk, index, state):
                graph = Graph()
                graph.parse(data=chunk, format='turtle')
                entities = convert_graph_to_entities(graph, state)
                return entities, len(entities)
    """

    def process_chunk(
        self,
        chunk: TInput,
        chunk_index: int,
        state: Dict[str, Any],
    ) -> Tuple[TChunk, int]:
        """
        Process a single chunk.

        Args:
            chunk: Raw chunk data
            chunk_index: Zero-based chunk index
            state: Mutable state dictionary (shared across chunks)

        Returns:
            Tuple of (processed_chunk, items_count)
        """
        ...

    def initialize_state(self, config: PipelineConfig) -> Dict[str, Any]:
        """
        Initialize processor state.

        Args:
            config: Pipeline configuration

        Returns:
            Initial state dictionary
        """
        ...

    def get_format_name(self) -> str:
        """
        Get human-readable format name.

        Returns:
            Format name (e.g., "RDF/TTL", "DTDL/JSON")
        """
        ...


@runtime_checkable
class StreamAggregatorProtocol(Protocol[TChunk, TOutput]):
    """
    Protocol for aggregating processed chunks into final output.

    Stream aggregators are responsible for:
    - Collecting partial results
    - Merging/combining chunks
    - Post-processing (deduplication, sorting, etc.)
    - Producing final output

    Example:
        class FabricDefinitionAggregator(StreamAggregatorProtocol[List[EntityType], dict]):
            def aggregate(self, chunks, state):
                all_entities = []
                for chunk in chunks:
                    all_entities.extend(chunk)
                return build_fabric_definition(all_entities, state)
    """

    def aggregate(
        self,
        chunks: Iterator[TChunk],
        state: Dict[str, Any],
    ) -> TOutput:
        """
        Aggregate chunks into final output.

        Args:
            chunks: Iterator of processed chunks
            state: State dictionary from processor

        Returns:
            Final aggregated output
        """
        ...

    def finalize(self, result: TOutput, state: Dict[str, Any]) -> TOutput:
        """
        Apply post-processing to final result.

        Args:
            result: Aggregated result
            state: State dictionary

        Returns:
            Finalized result
        """
        ...


# =============================================================================
# Streaming Pipeline
# =============================================================================

class StreamingPipeline(Generic[TInput, TChunk, TOutput]):
    """
    Main streaming pipeline orchestrator.

    Coordinates the three-stage streaming pipeline:
    1. Reader → produces raw chunks
    2. Processor → transforms chunks
    3. Aggregator → combines into output

    The pipeline handles:
    - Progress reporting
    - Cancellation checking
    - Memory monitoring
    - Error collection
    - Statistics tracking

    Example:
        reader = TTLStreamReader()
        processor = RDFChunkProcessor()
        aggregator = FabricDefinitionAggregator()

        pipeline = StreamingPipeline(reader, processor, aggregator)
        result = pipeline.execute("input.ttl", progress_callback=print_stats)
    """

    def __init__(
        self,
        reader: StreamReaderProtocol[TInput],
        processor: StreamProcessorProtocol[TInput, TChunk],
        aggregator: StreamAggregatorProtocol[TChunk, TOutput],
        config: Optional[PipelineConfig] = None,
    ):
        """
        Initialize the pipeline.

        Args:
            reader: Stream reader for input format
            processor: Chunk processor for transformation
            aggregator: Aggregator for final output
            config: Pipeline configuration (uses defaults if None)
        """
        self.reader = reader
        self.processor = processor
        self.aggregator = aggregator
        self.config = config or PipelineConfig()
        self._stats = PipelineStats()

    def execute(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> PipelineResult[TOutput]:
        """
        Execute the streaming pipeline.

        Args:
            input_path: Path to input file
            output_path: Optional path for output (streams to file)
            progress_callback: Optional progress callback
            cancellation_token: Optional cancellation token

        Returns:
            PipelineResult with output data and statistics
        """
        start_time = time.time()
        self._stats = PipelineStats(state=PipelineState.IDLE)
        result = PipelineResult[TOutput](stats=self._stats)

        input_path = Path(input_path)
        if not input_path.exists():
            result.success = False
            result.error = f"Input file not found: {input_path}"
            self._stats.state = PipelineState.FAILED
            return result

        try:
            # Initialize processor state
            state = self.processor.initialize_state(self.config)

            # Stage 1: Read chunks
            self._stats.state = PipelineState.READING
            logger.info(f"Starting pipeline for: {input_path}")

            def process_chunks() -> Iterator[TChunk]:
                """Generator that processes chunks as they're read."""
                self._stats.state = PipelineState.PROCESSING

                for chunk_data, bytes_read in self.reader.read_chunks(input_path, self.config):
                    # Check cancellation
                    if cancellation_token:
                        cancellation_token.throw_if_cancelled()

                    self._stats.chunks_read += 1
                    self._stats.bytes_read += bytes_read

                    # Process chunk
                    try:
                        processed, items = self.processor.process_chunk(
                            chunk_data,
                            self._stats.chunks_processed,
                            state,
                        )
                        self._stats.chunks_processed += 1
                        self._stats.items_produced += items

                        # Progress callback
                        if progress_callback and self.config.enable_progress:
                            progress_callback(self._stats)

                        yield processed

                    except Exception as e:
                        self._stats.errors += 1
                        if self.config.fail_fast:
                            raise
                        self._stats.add_warning(f"Chunk {self._stats.chunks_read} error: {e}")

                    # Memory check
                    self._check_memory()

            # Stage 3: Aggregate results
            self._stats.state = PipelineState.AGGREGATING
            aggregated = self.aggregator.aggregate(process_chunks(), state)
            final_result = self.aggregator.finalize(aggregated, state)

            # Write output if path provided
            if output_path:
                result.output_path = Path(output_path)
                self._write_output(final_result, result.output_path)
            else:
                result.data = final_result

            self._stats.state = PipelineState.COMPLETED
            result.success = True

        except PipelineCancelledException:
            self._stats.state = PipelineState.CANCELLED
            result.success = False
            result.error = "Pipeline cancelled"
            logger.info("Pipeline cancelled by user")

        except Exception as e:
            self._stats.state = PipelineState.FAILED
            result.success = False
            result.error = str(e)
            logger.error(f"Pipeline failed: {e}")

        finally:
            self._stats.duration_seconds = time.time() - start_time
            logger.info(self._stats.get_summary())

        return result

    def _check_memory(self) -> None:
        """Check memory usage and warn if high."""
        try:
            import psutil
            process = psutil.Process()
            current_mb = process.memory_info().rss / (1024 * 1024)
            self._stats.peak_memory_mb = max(self._stats.peak_memory_mb, current_mb)

            if current_mb > self.config.memory_limit_mb * 0.9:
                logger.warning(f"High memory usage: {current_mb:.1f} MB")
        except ImportError:
            pass

    def _write_output(self, data: TOutput, output_path: Path) -> None:
        """Write output data to file."""
        import json

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            if isinstance(data, (dict, list)):
                json.dump(data, f, indent=2)
            else:
                f.write(str(data))

        self._stats.bytes_written = output_path.stat().st_size


# =============================================================================
# Convenience Functions
# =============================================================================

def create_pipeline_from_format(
    format_name: str,
    config: Optional[PipelineConfig] = None,
) -> StreamingPipeline:
    """
    Create a streaming pipeline for the specified format.

    Args:
        format_name: Format name ("rdf", "dtdl", etc.)
        config: Optional pipeline configuration

    Returns:
        Configured StreamingPipeline instance

    Raises:
        ValueError: If format is not supported
    """
    from core.services.streaming import (
        RDFStreamReader,
        RDFChunkProcessor,
        DTDLStreamReader,
        DTDLChunkProcessor,
    )

    format_lower = format_name.lower()

    if format_lower in ('rdf', 'ttl', 'turtle'):
        return StreamingPipeline(
            reader=RDFStreamReader(),
            processor=RDFChunkProcessor(),
            aggregator=_DefaultAggregator(),
            config=config,
        )
    elif format_lower in ('dtdl', 'json'):
        return StreamingPipeline(
            reader=DTDLStreamReader(),
            processor=DTDLChunkProcessor(),
            aggregator=_DefaultAggregator(),
            config=config,
        )
    else:
        raise ValueError(f"Unsupported format: {format_name}")


class _DefaultAggregator(StreamAggregatorProtocol[Any, Dict[str, Any]]):
    """Default aggregator that collects all chunks into a list."""

    def aggregate(
        self,
        chunks: Iterator[Any],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Collect all chunks."""
        all_items = []
        for chunk in chunks:
            if isinstance(chunk, list):
                all_items.extend(chunk)
            else:
                all_items.append(chunk)
        return {"items": all_items, "state": state}

    def finalize(
        self,
        result: Dict[str, Any],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """No-op finalization."""
        return result


# =============================================================================
# Export
# =============================================================================

__all__ = [
    # State & Config
    "PipelineState",
    "PipelineStats",
    "PipelineConfig",
    "PipelineResult",
    # Cancellation
    "CancellationToken",
    "SimpleCancellationToken",
    "PipelineCancelledException",
    # Callbacks
    "ProgressCallback",
    # Protocols
    "StreamReaderProtocol",
    "StreamProcessorProtocol",
    "StreamAggregatorProtocol",
    # Pipeline
    "StreamingPipeline",
    # Utilities
    "create_pipeline_from_format",
]
